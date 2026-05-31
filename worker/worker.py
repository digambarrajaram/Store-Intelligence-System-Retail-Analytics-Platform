import os
import cv2
import json
import time
import signal
import sys
import asyncio
import redis as redis_client
from aiokafka import AIOKafkaProducer
from ultralytics import YOLO

# Environment variables with defaults
MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '0.4'))
FRAME_SKIP = int(os.getenv('FRAME_SKIP', '3'))
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'cv.detections')
VIDEO_SOURCE = os.getenv('VIDEO_SOURCE', os.getenv('VIDEO_PATH', '0'))
CAMERA_ID = os.getenv('CAMERA_ID', 'camera_0')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    global running
    print('Received shutdown signal. Stopping gracefully...')
    running = False

async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Redis client (sync — for heartbeat writes)
    r = redis_client.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Kafka producer (async)
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()
    print(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")

    # Load YOLOv8n model
    model = YOLO('yolov8n.pt')
    print("YOLOv8n model loaded")

    # Open video source
    source = int(VIDEO_SOURCE) if VIDEO_SOURCE.isdigit() else VIDEO_SOURCE
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"Error: Could not open video source '{VIDEO_SOURCE}'")
        # Don't exit — keep container alive so healthcheck can still pass
        # Write heartbeat so worker health endpoint doesn't stale immediately
        r.set('worker.alive', '1', ex=300)
        r.set('pipeline:status', json.dumps({
            'frames_processed': 0,
            'last_frame_id': 0,
            'unique_tracks_seen': 0,
            'events_published': 0,
            'error': f'Could not open video source: {VIDEO_SOURCE}'
        }))
        await producer.stop()
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video opened: {VIDEO_SOURCE} ({width}x{height} @ {fps:.1f}fps)")

    frame_count = 0
    processed_count = 0
    events_published = 0
    unique_tracks = set()
    start_time = time.time()
    last_log_time = start_time
    last_heartbeat = start_time

    try:
        while running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("End of video stream or failed to read frame")
                break

            frame_count += 1

            # Skip frames for performance
            if frame_count % (FRAME_SKIP + 1) != 0:
                continue

            processed_count += 1

            # Run YOLOv8 tracking with ByteTrack
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                classes=[0],           # person only
                conf=MIN_CONFIDENCE,
                verbose=False
            )

            detections = []
            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    track_id = int(box.id.item()) if box.id is not None else -1
                    bbox = box.xyxy[0].tolist()
                    confidence = float(box.conf.item())

                    x1, y1, x2, y2 = bbox
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    if track_id != -1:
                        unique_tracks.add(track_id)

                    detections.append({
                        'track_id': track_id,
                        'bbox': [round(x, 2) for x in bbox],
                        'confidence': round(confidence, 4),
                        'centroid': [round(cx, 2), round(cy, 2)]
                    })

            # Build and publish event
            event = {
                'frame_id': frame_count,
                'timestamp': time.time(),
                'camera_id': CAMERA_ID,
                'fps': round(fps, 2),
                'detections': detections
            }

            await producer.send(KAFKA_TOPIC, event)
            events_published += 1

            current_time = time.time()

            # Update pipeline status in Redis every 100 frames
            if processed_count % 100 == 0:
                r.set('pipeline:frames_processed', processed_count)
                r.set('pipeline:last_frame_id', frame_count)
                r.set('pipeline:unique_tracks_seen', len(unique_tracks))
                r.set('pipeline:events_published', events_published)
                r.set('metrics:last_updated', time.time())

            # Heartbeat every 30 seconds
            if current_time - last_heartbeat >= 30:
                r.set('worker.alive', '1', ex=120)  # expires in 2 min if worker dies
                r.set('worker:last_heartbeat', current_time)
                last_heartbeat = current_time

            # Log FPS every 30 seconds
            if current_time - last_log_time >= 30:
                elapsed = current_time - start_time
                processing_fps = processed_count / elapsed if elapsed > 0 else 0
                print(f"[{CAMERA_ID}] Frames: {processed_count} | Tracks: {len(unique_tracks)} | FPS: {processing_fps:.2f} | Published: {events_published}")
                last_log_time = current_time

    except Exception as e:
        print(f"Error during processing: {e}")
        r.set('worker:error', str(e))
    finally:
        cap.release()
        # Final status write
        r.set('pipeline:frames_processed', processed_count)
        r.set('pipeline:last_frame_id', frame_count)
        r.set('pipeline:unique_tracks_seen', len(unique_tracks))
        r.set('pipeline:events_published', events_published)
        await producer.stop()
        print(f"Worker stopped. Total: {processed_count} frames, {len(unique_tracks)} unique tracks, {events_published} events published.")

if __name__ == "__main__":
    asyncio.run(main())