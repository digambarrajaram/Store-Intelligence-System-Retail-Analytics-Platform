from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, confloat, conlist, Literal


class Detection(BaseModel):
    track_id: int
    bbox: conlist(float, min_length=4, max_length=4) = Field(..., description="Bounding box [x_min, y_min, x_max, y_max]")
    confidence: confloat(ge=0, le=1) = Field(..., description="Detection confidence score between 0 and 1")
    centroid: Tuple[float, float] = Field(..., description="Center point of the bounding box (x, y)")
    zone: Optional[str] = Field(None, description="Zone identifier where detection occurred")


class DetectionEvent(BaseModel):
    frame_id: int = Field(..., description="Frame identifier from video stream")
    timestamp: datetime = Field(..., description="Timestamp of the frame capture")
    camera_id: str = Field(..., description="Unique identifier for the camera")
    fps: float = Field(..., description="Frames per second of the video stream")
    detections: List[Detection] = Field(..., description="List of detections in the frame")


class FootfallEvent(BaseModel):
    event_type: Literal["entry", "exit"] = Field(..., description="Type of footfall event")
    track_id: int = Field(..., description="Track ID of the person")
    timestamp: datetime = Field(..., description="Timestamp of the event")
    camera_id: str = Field(..., description="Camera where the event occurred")
    is_reentry: bool = Field(False, description="Whether this is a re-entry of a previously tracked person")
    is_staff: bool = Field(False, description="Whether the person is identified as staff")


class AnomalyEvent(BaseModel):
    anomaly_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the anomaly")
    anomaly_type: Literal["dwell", "crowd", "loitering"] = Field(..., description="Type of anomaly detected")
    camera_id: str = Field(..., description="Camera where the anomaly was detected")
    timestamp: datetime = Field(..., description="Timestamp of the anomaly detection")
    severity: Literal["low", "medium", "high"] = Field(..., description="Severity level of the anomaly")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context-specific metadata")