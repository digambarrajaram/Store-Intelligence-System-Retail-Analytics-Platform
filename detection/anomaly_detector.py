import os
import time
import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import redis
from kafka import KafkaProducer
from fastapi import FastAPI, HTTPException, Query

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables with defaults
DWELL_THRESHOLD_SECONDS = int(os.getenv("DWELL_THRESHOLD_SECONDS", "300"))
CROWD_THRESHOLD = int(os.getenv("CROWD_THRESHOLD", "8"))
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

@dataclass
class AnomalyEvent:
    anomaly_id: str
    anomaly_type: str  # "dwell", "crowd", "loitering"
    severity: str      # "low", "medium", "high"
    person_id: Optional[str] = None
    zone_id: Optional[str] = None
    timestamp: float = None
    description: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class AnomalyDetector:
    def __init__(self):
        # State for dwell: person_id -> zone_id -> enter_timestamp
        self.person_zone_enter_time: Dict[str, Dict[str, float]] = {}
        # State for loitering: (person_id, zone_id) -> list of entry timestamps (we'll keep only last 10 minutes)
        self.person_zone_entries: Dict[tuple, List[float]] = {}
        # Deduplication cache: anomaly_key -> last_emission_timestamp
        self.last_emitted: Dict[str, float] = {}
        # Thresholds
        self.dwell_threshold = DWELL_THRESHOLD_SECONDS
        self.crowd_threshold = CROWD_THRESHOLD
        # Kafka producer
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        # Redis client
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    def _get_anomaly_key(self, anomaly_type: str, person_id: Optional[str], zone_id: Optional[str]) -> str:
        # For crowd, person_id is None
        if person_id is None:
            return f"{anomaly_type}:{zone_id}"
        else:
            return f"{anomaly_type}:{person_id}:{zone_id}"

    def _should_emit(self, anomaly_key: str) -> bool:
        now = time.time()
        last_emitted = self.last_emitted.get(anomaly_key, 0)
        if now - last_emitted > 60:  # 60 seconds
            self.last_emitted[anomaly_key] = now
            return True
        return False

    def _emit_anomaly(self, anomaly: AnomalyEvent):
        # Emit to Kafka
        try:
            self.kafka_producer.send("cv.anomalies", value=asdict(anomaly))
            self.kafka_producer.flush()
        except Exception as e:
            logger.error(f"Failed to send anomaly to Kafka: {e}")

        # Store in Redis
        try:
            anomaly_json = json.dumps(asdict(anomaly))
            self.redis_client.hset(f"anomaly:{anomaly.anomaly_id}", mapping={"data": anomaly_json})
            # Also add to sorted set for recent anomalies
            self.redis_client.zadd("anomalies:recent", {anomaly.anomaly_id: anomaly.timestamp})
        except Exception as e:
            logger.error(f"Failed to store anomaly in Redis: {e}")

    def check_dwell(self, track_states: List[Dict], now: float) -> List[AnomalyEvent]:
        anomalies = []
        # We'll update the enter_time state from the track_states
        # We assume track_states events are either enter or exit
        for event in track_states:
            person_id = event.get("person_id")
            zone_id = event.get("zone_id")
            event_type = event.get("event_type")
            timestamp = event.get("timestamp", now)

            if event_type == "enter":
                # Record enter time
                if person_id not in self.person_zone_enter_time:
                    self.person_zone_enter_time[person_id] = {}
                self.person_zone_enter_time[person_id][zone_id] = timestamp
            elif event_type == "exit":
                # If we have an enter time for this person in this zone, compute duration
                if person_id in self.person_zone_enter_time and zone_id in self.person_zone_enter_time[person_id]:
                    enter_time = self.person_zone_enter_time[person_id][zone_id]
                    duration = timestamp - enter_time
                    if duration > self.dwell_threshold:
                        # Determine severity
                        if duration < 300:  # 5 min
                            severity = "low"
                        elif duration < 600:  # 10 min
                            severity = "medium"
                        else:
                            severity = "high"
                        anomaly_key = self._get_anomaly_key("dwell", person_id, zone_id)
                        if self._should_emit(anomaly_key):
                            anomaly = AnomalyEvent(
                                anomaly_id=str(uuid.uuid4()),
                                anomaly_type="dwell",
                                severity=severity,
                                person_id=person_id,
                                zone_id=zone_id,
                                timestamp=now,
                                description=f"Person {person_id} dwelled in zone {zone_id} for {duration:.2f} seconds"
                            )
                            anomalies.append(anomaly)
                            self._emit_anomaly(anomaly)
                    # Remove the enter time since they exited
                    del self.person_zone_enter_time[person_id][zone_id]
                    if not self.person_zone_enter_time[person_id]:
                        del self.person_zone_enter_time[person_id]

        # Also check for persons who are still in a zone (no exit event yet) and have exceeded dwell threshold
        for person_id, zones in self.person_zone_enter_time.items():
            for zone_id, enter_time in zones.items():
                duration = now - enter_time
                if duration > self.dwell_threshold:
                    if duration < 300:
                        severity = "low"
                    elif duration < 600:
                        severity = "medium"
                    else:
                        severity = "high"
                    anomaly_key = self._get_anomaly_key("dwell", person_id, zone_id)
                    if self._should_emit(anomaly_key):
                        anomaly = AnomalyEvent(
                            anomaly_id=str(uuid.uuid4()),
                            anomaly_type="dwell",
                            severity=severity,
                            person_id=person_id,
                            zone_id=zone_id,
                            timestamp=now,
                            description=f"Person {person_id} dwelled in zone {zone_id} for {duration:.2f} seconds (ongoing)"
                        )
                        anomalies.append(anomaly)
                        self._emit_anomaly(anomaly)
        return anomalies

    def check_loitering(self, track_states: List[Dict], now: float) -> List[AnomalyEvent]:
        anomalies = []
        # We are only interested in enter events for loitering
        for event in track_states:
            if event.get("event_type") == "enter":
                person_id = event.get("person_id")
                zone_id = event.get("zone_id")
                timestamp = event.get("timestamp", now)
                key = (person_id, zone_id)
                if key not in self.person_zone_entries:
                    self.person_zone_entries[key] = []
                # Add this entry timestamp
                self.person_zone_entries[key].append(timestamp)
                # Remove entries older than 10 minutes (600 seconds)
                cutoff = now - 600
                self.person_zone_entries[key] = [ts for ts in self.person_zone_entries[key] if ts >= cutoff]
                # Count the number of entries in the last 10 minutes
                count = len(self.person_zone_entries[key])
                if count > 3:  # more than 3 times
                    anomaly_key = self._get_anomaly_key("loitering", person_id, zone_id)
                    if self._should_emit(anomaly_key):
                        anomaly = AnomalyEvent(
                            anomaly_id=str(uuid.uuid4()),
                            anomaly_type="loitering",
                            severity="medium",  # The problem doesn't specify severity for loitering, but we can set a default. Let's say medium.
                            person_id=person_id,
                            zone_id=zone_id,
                            timestamp=now,
                            description=f"Person {person_id} entered zone {zone_id} {count} times in the last 10 minutes"
                        )
                        anomalies.append(anomaly)
                        self._emit_anomaly(anomaly)
        return anomalies

    def check_crowd(self, zone_counts: Dict[str, int], now: float) -> List[AnomalyEvent]:
        anomalies = []
        for zone_id, count in zone_counts.items():
            if count > self.crowd_threshold:
                ratio = count / self.crowd_threshold
                if ratio < 1.5:
                    severity = "low"
                elif ratio < 2.0:
                    severity = "medium"
                else:
                    severity = "high"
                anomaly_key = self._get_anomaly_key("crowd", None, zone_id)
                if self._should_emit(anomaly_key):
                    anomaly = AnomalyEvent(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type="crowd",
                        severity=severity,
                        person_id=None,
                        zone_id=zone_id,
                        timestamp=now,
                        description=f"Zone {zone_id} has {count} people, exceeding threshold of {self.crowd_threshold}"
                    )
                    anomalies.append(anomaly)
                    self._emit_anomaly(anomaly)
        return anomalies

    def check(self, track_states: List[Dict], zone_counts: Dict[str, int]) -> List[AnomalyEvent]:
        now = time.time()
        anomalies = []
        anomalies.extend(self.check_dwell(track_states, now))
        anomalies.extend(self.check_loitering(track_states, now))
        anomalies.extend(self.check_crowd(zone_counts, now))
        return anomalies

# FastAPI app
app = FastAPI()

# We'll create a global detector instance (in practice, you might want to use dependency injection)
detector = AnomalyDetector()

@app.get("/api/v1/anomalies")
async def get_anomalies(
    N: int = Query(10, gt=0, le=100),
    severity: Optional[str] = Query(None, regex="^(low|medium|high)$")
):
    try:
        # Get the top N anomaly IDs from the sorted set (most recent first)
        anomaly_ids = detector.redis_client.zrevrange("anomalies:recent", 0, N-1)
        anomalies = []
        for anomaly_id in anomaly_ids:
            anomaly_id_str = anomaly_id.decode('utf-8') if isinstance(anomaly_id, bytes) else anomaly_id
            anomaly_data = detector.redis_client.hget(f"anomaly:{anomaly_id_str}", "data")
            if anomaly_data:
                anomaly_json = anomaly_data.decode('utf-8') if isinstance(anomaly_data, bytes) else anomaly_data
                anomaly_dict = json.loads(anomaly_json)
                if severity is None or anomaly_dict.get("severity") == severity:
                    anomalies.append(anomaly_dict)
        return anomalies
    except Exception as e:
        logger.error(f"Error retrieving anomalies: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")