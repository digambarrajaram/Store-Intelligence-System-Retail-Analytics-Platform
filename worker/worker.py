import os
import cv2
import json
import time
import signal
import sys
from kafka import KafkaProducer
from ultralytics import YOLO
import numpy as np

# Environment variables with defaults
MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '0.4'))
FRAME_SKIP = int(os.getenv('FRAME_SKIP', '3'))
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'cv.detections')
VIDEO_SOURCE = os.getenv('VIDEO_SOURCE', '0')  # Can be file path, RTSP URL, or camera index
CAMERA_ID = os.getenv('CAMERA_ID', 'camera_0')

# Global flag for running state
running = True

def signal_handler(sig, frame):
    global running
    print('Received shutdown signal. Stopping gracefully...')
    running = False

def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Load YOLOv8n model with ByteTrack tracker
    model = YOLO('yolov8n.pt')  # Will download if not present
    # Note: The tracker config file 'bytetrack.yaml' is expected to be in the same directory or accessible via ultralytics
    # We'll use the built-in ByteTrack tracker by name
    
    # Open video source
    if VIDEO_SOURCE.isdigit():
        cap = cv2.VideoCapture(int(VIDEO_SOURCE))
    else:
        cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    if not cap.isOpened():
        print(f"Error: Could not open video source {VIDEO_SOURCE}")
        sys.exit(1)
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video source opened: {VIDEO_SOURCE} ({width}x{height} @ {fps}fps)")
    
    frame_count = 0
    processed_count = 0
    start_time = time.time()
    last_log_time = start_time
    
    try:
        while running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("End of video stream or failed to read frame")
                break
            
            frame_count += 1
            
            # Skip frames based on FRAME_SKIP
            if frame_count % (FRAME_SKIP + 1) != 0:
                continue
            
            processed_count += 1
            
            # Run YOLO tracking with ByteTrack
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], conf=MIN_CONFIDENCE, verbose=False)
            
            detections = []
            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                for i in range(len(boxes)):
                    # Extract box data
                    box = boxes[i]
                    track_id = int(box.id.item()) if box.id is not None else -1
                    bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    confidence = float(box.conf.item())
                    class_id = int(box.cls.item())
                    
                    # Calculate centroid
                    x1, y1, x2, y2 = bbox
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    
                    detections.append({
                        'track_id': track_id,
                        'bbox': [round(x, 2) for x in bbox],
                        'confidence': round(confidence, 4),
                        'centroid': [round(cx, 2), round(cy, 2)]
                    })
            
            # Prepare event
            event = {
                'frame_id': frame_count,
                'timestamp': time.time(),
                'camera_id': CAMERA_ID,
                'fps': round(fps, 2),
                'detections': detections
            }
            
            # Send to Kafka
            producer.send(KAFKA_TOPIC, event)
            
            # Log processing FPS every 30 seconds
            current_time = time.time()
            if current_time - last_log_time >= 30:
                elapsed = current_time - start_time
                if elapsed > 0:
                    processing_fps = processed_count / elapsed
                    print(f"Processed {processed_count} frames in {elapsed:.2f}s - {processing_fps:.2f} FPS")
                last_log_time = current_time
                
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        # Clean up
        cap.release()
        producer.flush()
        producer.close()
        print("Worker stopped.")

if __name__ == "__main__":
    main()