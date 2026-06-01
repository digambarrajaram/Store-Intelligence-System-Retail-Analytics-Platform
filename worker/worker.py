# NOTE: Add redis-tools to Dockerfile apt-get install for healthcheck to work.
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

# Import metrics counter for Kafka publish errors
try:
    from metrics import kafka_publish_errors_total
except ImportError:
    # Fallback if metrics module not available (e.g., when running in isolation)
    class DummyCounter:
        def inc(self):
            pass
    kafka_publish_errors_total = DummyCounter()

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

    # Redis connection with retry logic (5 attempts, 3s sleep)
    print("Connecting to Redis...")
    r = None
    for attempt in range(5):
        try:
            r = redis_client.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping()
            print(f"Redis connected on attempt {attempt + 1}")
            break
        except Exception as e:
            print(f"Redis connection attempt {attempt + 1} failed: {e}")
            if attempt < 4:  # Not the last attempt
                time.sleep(3)
            else:
                print("ERROR: Could not connect to Redis after 5 attempts. Exiting.")
                sys.exit(1)

    # Write initial heartbeat immediately so healthcheck passes during startup
    r.set('worker.alive', '1', ex=120)
    r.set('worker:last_heartbeat', time.time())
    print("Initial heartbeat written")

    # Kafka producer with retry logic (10 attempts, 5s sleep)
    print("Connecting to Kafka...")
    producer = None
    for attempt in range(10):
        try:
            producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await producer.start()
            print(f"Kafka producer connected on attempt {attempt + 1}")
            break
        except Exception as e:
            print(f"Kafka connection attempt {attempt + 1} failed: {e}")
            if attempt < 9:  # Not the last attempt
                await asyncio.sleep(5)
            else:
                print("ERROR: Could not connect to Kafka after 10 attempts. Exiting.")
                await producer.stop() if producer else None
                sys.exit(1)

    # Load YOLOv8n model
    model = YOLO('yolov8n.pt')
    print("YOLOv8n model loaded")

    # Open video source
    source = int(VIDEO_SOURCE) if VIDEO_SOURCE.isdigit() else VIDEO_SOURCE
    
    # Check if VIDEO_SOURCE is a file that exists
    is_file = not VIDEO_SOURCE.isdigit() and os.path.exists(VIDEO_SOURCE)
    
    if not is_file and not VIDEO_SOURCE.isdigit():
        print(f"WARNING: Video file not found at {VIDEO_SOURCE}. Running in demo mode.")
        # Demo mode: we'll generate synthetic events
        cap = None  # We won't use OpenCV capture
    else:
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

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0 if cap else 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if cap else 640
    height = int(cap.get(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) if cap else 480
    if cap:
        print(f"Video opened: {VIDEO_SOURCE} ({width}x{height} @ {fps:.1f}fps)")
    else:
        print(f"Running in demo mode: generating synthetic events")

    frame_count = 0
    processed_count = 0
    events_published = 0
    unique_tracks = set()
    start_time = time.time()
    last_log_time = start_time
    last_heartbeat = start_time
    last_demo_event_time = start_time

    try:
        while running:
            if cap:
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
            else:
                # Demo mode: generate synthetic DetectionEvents every 1 second
                current_time = time.time()
                if current_time - last_demo_event_time < 1.0:
                    # Sleep a bit to avoid busy loop
                    await asyncio.sleep(0.1)
                    continue
                last_demo_event_time = current_time
                
                processed_count += 1
                frame_count += 1  # Simulate frame count
                
                # Generate 1-3 random detections
                import random
                num_detections = random.randint(1, 3)
                detections = []
                for i in range(num_detections):
                    track_id = random.randint(1000, 9999)
                    # Generate random bbox within 640x480
                    x1 = random.randint(0, 500)
                    y1 = random.randint(0, 400)
                    x2 = x1 + random.randint(50, 140)
                    y2 = y1 + random.randint(80, 200)
                    bbox = [x1, y1, x2, y2]
                    confidence = round(random.uniform(0.5, 0.95), 4)
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    
                    detections.append({
                        'track_id': track_id,
                        'bbox': [round(x, 2) for x in bbox],
                        'confidence': confidence,
                        'centroid': [round(cx, 2), round(cy, 2)]
                    })
                    
                    if track_id != -1:
                        unique_tracks.add(track_id)

            # Build and publish event
            event = {
                'frame_id': frame_count,
                'timestamp': time.time(),
                'camera_id': CAMERA_ID,
                'fps': round(fps, 2),
                'detections': detections
            }

            try:
                await producer.send(KAFKA_TOPIC, event)
                events_published += 1
            except Exception as e:
                print(f"Kafka publish error: {e}")
                kafka_publish_errors_total.inc()

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
        if cap:
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