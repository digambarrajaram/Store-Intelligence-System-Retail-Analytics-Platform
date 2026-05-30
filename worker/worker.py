"""
CV Pipeline — YOLOv8 Detection Worker
Reads .mp4 → detects people → publishes events to Kafka → updates Redis
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import redis
from aiokafka import AIOKafkaProducer
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker")

# ── Config ─────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
TOPIC_DETECTIONS = os.getenv("KAFKA_TOPIC_DETECTIONS", "cv.detections")
TOPIC_ANOMALIES = os.getenv("KAFKA_TOPIC_ANOMALIES", "cv.anomalies")
TOPIC_HEARTBEATS = os.getenv("KAFKA_TOPIC_HEARTBEATS", "cv.heartbeats")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_PUBSUB = os.getenv("REDIS_PUBSUB_CHANNEL", "cv:alerts")

MODEL_PATH = os.getenv("YOLO_MODEL", "yolov8n.pt")
CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.4"))
YOLO_CLASSES = [int(c) for c in os.getenv("YOLO_CLASSES", "0").split(",")]
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "/videos/input.mp4")
VIDEO_LOOP = os.getenv("VIDEO_LOOP", "true").lower() == "true"
FRAME_SKIP = int(os.getenv("FRAME_SKIP", "3"))

DWELL_THRESHOLD = int(os.getenv("DWELL_THRESHOLD_SEC", "30"))
CROWD_THRESHOLD = int(os.getenv("CROWD_THRESHOLD_COUNT", "10"))

CAMERA_ID = os.getenv("CAMERA_ID", "cam-01")


# ── Heatmap ────────────────────────────────────────────────────────

class HeatmapGrid:
    """10×10 grid accumulating centroid hits for Redis storage."""

    GRID = 10

    def __init__(self, frame_w: int, frame_h: int):
        self.fw = frame_w
        self.fh = frame_h
        self.grid: np.ndarray = np.zeros((self.GRID, self.GRID), dtype=np.int32)

    def update(self, cx: float, cy: float):
        col = min(int(cx / self.fw * self.GRID), self.GRID - 1)
        row = min(int(cy / self.fh * self.GRID), self.GRID - 1)
        self.grid[row][col] += 1

    def to_list(self) -> list[list[int]]:
        return self.grid.tolist()


# ── Dwell / Crowd Anomaly Detector ────────────────────────────────

class AnomalyDetector:
    def __init__(self):
        self._track_first_seen: dict[int, float] = {}
        self._track_last_seen: dict[int, float] = {}
        self._fired_dwell: set[int] = set()

    def update(self, track_ids: list[int], now: float) -> list[dict]:
        anomalies = []

        # Crowd check
        if len(track_ids) >= CROWD_THRESHOLD:
            anomalies.append({
                "anomaly_id": str(uuid.uuid4()),
                "anomaly_type": "crowd",
                "camera_id": CAMERA_ID,
                "timestamp": now,
                "severity": "high" if len(track_ids) >= CROWD_THRESHOLD * 1.5 else "medium",
                "metadata": {"count": len(track_ids), "threshold": CROWD_THRESHOLD},
            })

        # Dwell check
        for tid in track_ids:
            if tid not in self._track_first_seen:
                self._track_first_seen[tid] = now
            self._track_last_seen[tid] = now
            dwell = now - self._track_first_seen[tid]
            if dwell >= DWELL_THRESHOLD and tid not in self._fired_dwell:
                self._fired_dwell.add(tid)
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "anomaly_type": "dwell",
                    "camera_id": CAMERA_ID,
                    "timestamp": now,
                    "severity": "medium",
                    "metadata": {"track_id": tid, "dwell_sec": round(dwell, 1)},
                })

        # Evict stale tracks (not seen for 5 s)
        stale = [tid for tid, ts in self._track_last_seen.items() if now - ts > 5]
        for tid in stale:
            self._track_first_seen.pop(tid, None)
            self._track_last_seen.pop(tid, None)
            self._fired_dwell.discard(tid)

        return anomalies


# ── Main pipeline ──────────────────────────────────────────────────

async def run():
    log.info("Loading YOLOv8 model: %s", MODEL_PATH)
    model = YOLO(MODEL_PATH)

    log.info("Connecting to Kafka: %s", KAFKA_BOOTSTRAP)
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()

    log.info("Connecting to Redis: %s", REDIS_URL)
    r = redis.from_url(REDIS_URL, decode_responses=True)

    anomaly_detector = AnomalyDetector()
    heatmap: HeatmapGrid | None = None
    frame_count = 0

    while True:
        if not Path(VIDEO_SOURCE).exists():
            log.warning("Video not found at %s — retrying in 5 s", VIDEO_SOURCE)
            await asyncio.sleep(5)
            continue

        cap = cv2.VideoCapture(VIDEO_SOURCE)
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_source = cap.get(cv2.CAP_PROP_FPS) or 25
        heatmap = HeatmapGrid(fw, fh)
        log.info("Opened %s  (%dx%d @ %.1f fps)", VIDEO_SOURCE, fw, fh, fps_source)

        t_start = time.time()
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % FRAME_SKIP != 0:
                continue

            t_frame = time.time()

            # YOLOv8 inference with ByteTrack
            results = model.track(
                frame,
                persist=True,
                conf=CONF_THRESHOLD,
                classes=YOLO_CLASSES,
                verbose=False,
            )

            detections = []
            track_ids: list[int] = []

            for box in results[0].boxes:
                if box.id is None:
                    continue
                tid = int(box.id.item())
                track_ids.append(tid)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                heatmap.update(cx, cy)
                detections.append({
                    "track_id": tid,
                    "bbox": [round(x1), round(y1), round(x2), round(y2)],
                    "conf": round(float(box.conf.item()), 3),
                    "class_id": int(box.cls.item()),
                    "centroid": [round(cx), round(cy)],
                })

            elapsed = time.time() - t_frame
            fps = round(1 / max(elapsed, 0.001), 1)

            # ── Publish to Kafka: cv.detections ──
            detection_event = {
                "frame_id": frame_count,
                "timestamp": t_frame,
                "camera_id": CAMERA_ID,
                "detections": detections,
                "fps": fps,
            }
            await producer.send(TOPIC_DETECTIONS, value=detection_event)

            # ── Update Redis counters ──
            pipe = r.pipeline()
            pipe.incrby("cv:stats:detections", len(detections))
            pipe.sadd("cv:tracks", *([str(tid) for tid in track_ids] or ["__noop__"]))
            pipe.set("cv:stats:avg_fps", fps)
            pipe.set("cv:heatmap:10x10", json.dumps(heatmap.to_list()))
            if len(detections) > int(r.get("cv:stats:peak_crowd") or 0):
                pipe.set("cv:stats:peak_crowd", len(detections))
            pipe.execute()

            # ── Anomaly detection + publish ──
            anomalies = anomaly_detector.update(track_ids, t_frame)
            for anom in anomalies:
                await producer.send(TOPIC_ANOMALIES, value=anom)
                r.incrby("cv:stats:anomalies", 1)
                r.publish(REDIS_PUBSUB, json.dumps(anom))
                log.warning("🚨 Anomaly: %s  camera=%s", anom["anomaly_type"], CAMERA_ID)

            # ── Heartbeat every 100 frames ──
            if frame_count % 100 == 0:
                await producer.send(TOPIC_HEARTBEATS, value={
                    "worker": "yolo-worker",
                    "ts": time.time(),
                    "frame": frame_count,
                    "fps": fps,
                })
                log.info("Frame %d | %d detections | fps=%.1f", frame_count, len(detections), fps)

        cap.release()
        if VIDEO_LOOP:
            log.info("Video ended — looping.")
            await asyncio.sleep(1)
        else:
            log.info("Video ended — worker done.")
            break

    await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
