import cv2
import numpy as np
from typing import List, Dict, Any, Tuple


class ZoneDetector:
    """
    Detects entry and exit events based on predefined zones in a video frame.
    
    Attributes:
        frame_width (int): Width of the video frame in pixels.
        frame_height (int): Height of the video frame in pixels.
        ENTRY_ZONE (List[Tuple[float, float]]): Normalized coordinates (0-1) defining the entry zone polygon.
        EXIT_ZONE (List[Tuple[float, float]]): Normalized coordinates (0-1) defining the exit zone polygon.
        zone_state (Dict[int, str]): Tracks state of each person relative to ENTRY_ZONE: "inside", "outside", or "unknown".
        _exit_zone_state (Dict[int, str]): Internal state tracking for EXIT_ZONE.
    """
    
    def __init__(self, frame_width: int, frame_height: int, 
                 entry_zone: List[Tuple[float, float]], 
                 exit_zone: List[Tuple[float, float]]):
        """
        Initialize the ZoneDetector.
        
        Args:
            frame_width: Width of video frame in pixels.
            frame_height: Height of video frame in pixels.
            entry_zone: List of (x, y) tuples defining entry zone polygon in normalized coordinates (0-1).
            exit_zone: List of (x, y) tuples defining exit zone polygon in normalized coordinates (0-1).
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.ENTRY_ZONE = entry_zone
        self.EXIT_ZONE = exit_zone
        self.zone_state: Dict[int, str] = {}  # For ENTRY_ZONE: track_id -> "inside"/"outside"/"unknown"
        self._exit_zone_state: Dict[int, str] = {}  # For EXIT_ZONE: track_id -> "inside"/"outside"/"unknown"
    
    def _normalize_to_pixel(self, point: Tuple[float, float]) -> Tuple[int, int]:
        """Convert normalized coordinates (0-1) to pixel coordinates."""
        x, y = point
        return (int(x * self.frame_width), int(y * self.frame_height))
    
    def _point_in_polygon(self, point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """
        Check if a point is inside a polygon using cv2.pointPolygonTest.
        
        Args:
            point: (x, y) coordinates in pixel space.
            polygon: List of (x, y) tuples defining polygon vertices in pixel space.
            
        Returns:
            True if point is inside or on the edge of polygon, False otherwise.
        """
        # Convert polygon to numpy array of integers
        polygon_np = np.array(polygon, dtype=np.int32)
        # Use cv2.pointPolygonTest: returns positive if inside, negative if outside, zero on edge
        dist = cv2.pointPolygonTest(polygon_np, point, False)
        return dist >= 0
    
    def process_frame(self, detections: List[Dict[str, Any]], 
                      frame_id: int, timestamp: float) -> List[Dict[str, Any]]:
        """
        Process a frame of detections to detect entry and exit events.
        
        Args:
            detections: List of detection dictionaries. Each dict must contain:
                - 'track_id': int unique identifier for the tracked person.
                - 'bbox': List [x1, y1, x2, y2] representing bounding box in pixel coordinates.
            frame_id: Integer identifier for the current frame.
            timestamp: Float timestamp for the current frame.
            
        Returns:
            List of event dictionaries. Each dict contains:
                - 'event': Either "entry" or "exit".
                - 'track_id': The track ID of the person.
                - 'timestamp': The frame timestamp.
                - 'frame_id': The frame identifier.
        """
        events = []
        current_track_ids = set()
        
        # Precompute pixel coordinates for zones
        entry_zone_pix = [self._normalize_to_pixel(p) for p in self.ENTRY_ZONE]
        exit_zone_pix = [self._normalize_to_pixel(p) for p in self.EXIT_ZONE]
        
        for det in detections:
            track_id = det['track_id']
            bbox = det['bbox']
            # Calculate centroid of bounding box
            x1, y1, x2, y2 = bbox
            centroid = ((x1 + x2) / 2, (y1 + y2) / 2)
            
            current_track_ids.add(track_id)
            
            # Check zone membership
            in_entry = self._point_in_polygon(centroid, entry_zone_pix)
            in_exit = self._point_in_polygon(centroid, exit_zone_pix)
            
            # Get previous states (default to 'unknown' if not seen before)
            prev_entry_state = self.zone_state.get(track_id, 'unknown')
            prev_exit_state = self._exit_zone_state.get(track_id, 'unknown')
            
            # Determine current states
            curr_entry_state = 'inside' if in_entry else 'outside'
            curr_exit_state = 'inside' if in_exit else 'outside'
            
            # Detect entry event: transition from outside to inside ENTRY_ZONE
            # Skip if previous state was 'unknown' (to avoid counting mid-frame appearances)
            if prev_entry_state == 'outside' and curr_entry_state == 'inside':
                events.append({
                    "event": "entry",
                    "track_id": track_id,
                    "timestamp": timestamp,
                    "frame_id": frame_id
                })
            
            # Detect exit event: transition from inside to outside EXIT_ZONE
            # Skip if previous state was 'unknown'
            if prev_exit_state == 'inside' and curr_exit_state == 'outside':
                events.append({
                    "event": "exit",
                    "track_id": track_id,
                    "timestamp": timestamp,
                    "frame_id": frame_id
                })
            
            # Update state trackers
            self.zone_state[track_id] = curr_entry_state
            self._exit_zone_state[track_id] = curr_exit_state
        
        # Remove states for tracks not seen in current frame
        to_remove_entry = [tid for tid in self.zone_state if tid not in current_track_ids]
        to_remove_exit = [tid for tid in self._exit_zone_state if tid not in current_track_ids]
        for tid in to_remove_entry:
            del self.zone_state[tid]
        for tid in to_remove_exit:
            del self._exit_zone_state[tid]
        
        return events