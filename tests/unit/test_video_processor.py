import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.video_processor import VideoProcessor


def test_video_processor_generates_entry_and_exit_events():
    processor = VideoProcessor()
    track_id = '1001'
    now = time.time()

    entry_bbox = [50.0, 900.0, 100.0, 950.0]
    events = processor.process_frame(1, now, 'camera_1', [
        {'track_id': track_id, 'bbox': entry_bbox, 'confidence': 0.95}
    ])

    assert len(events) == 1
    assert events[0]['event'] == 'entry'
    assert events[0]['zone'] == 'entry_zone'

    # Move into browsing zone and then exit to simulate dwell
    browse_bbox = [500.0, 500.0, 540.0, 540.0]
    processor.process_frame(2, now + 1.0, 'camera_1', [
        {'track_id': track_id, 'bbox': browse_bbox, 'confidence': 0.95}
    ])

    # Stay in browsing zone beyond threshold to produce browse and dwell_time events
    threshold_time = now + 121.0
    events = processor.process_frame(3, threshold_time, 'camera_1', [
        {'track_id': track_id, 'bbox': browse_bbox, 'confidence': 0.95}
    ])

    assert any(event['event'] == 'browse' for event in events)
    assert any(event['event'] == 'dwell_time' for event in events)

    # Move to checkout zone
    checkout_bbox = [1100.0, 600.0, 1140.0, 640.0]
    events = processor.process_frame(4, threshold_time + 1.0, 'camera_1', [
        {'track_id': track_id, 'bbox': checkout_bbox, 'confidence': 0.95}
    ])

    assert any(event['event'] == 'checkout_visit' for event in events)
    assert any(event['event'] == 'dwell_time' for event in events)

    # Exit store
    events = processor.process_frame(5, threshold_time + 10.0, 'camera_1', [
        {'track_id': track_id, 'bbox': [0.0, 0.0, 0.0, 0.0], 'confidence': 0.95}]
    )
    assert any(event['event'] == 'exit' for event in events)


def test_video_processor_generates_staff_ignore_event():
    processor = VideoProcessor()
    track_id = '2002'
    now = time.time()

    staff_bbox = [60.0, 60.0, 100.0, 100.0]
    events = processor.process_frame(1, now, 'camera_1', [
        {'track_id': track_id, 'bbox': staff_bbox, 'confidence': 0.95}
    ])

    assert any(event['event'] == 'staff_ignore' for event in events)
    assert any(event['zone'] == 'staff_zone' for event in events)


def test_video_processor_handles_unknown_track_geometry():
    processor = VideoProcessor()
    now = time.time()
    events = processor.process_frame(1, now, 'camera_1', [
        {'track_id': 'bad', 'bbox': [1.0, 2.0], 'confidence': 0.5}
    ])
    assert events == []
