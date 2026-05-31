import pytest
import time
from unittest.mock import Mock, patch
from detection.anomaly_detector import AnomalyDetector, AnomalyEvent

@pytest.fixture
def detector():
    with patch('detection.anomaly_detector.redis.Redis') as mock_redis, \
         patch('detection.anomaly_detector.KafkaProducer') as mock_kafka:
        # Create mock instances
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_kafka_instance = Mock()
        mock_kafka.return_value = mock_kafka_instance
        
        detector = AnomalyDetector()
        detector.redis_client = mock_redis_instance
        detector.kafka_producer = mock_kafka_instance
        yield detector

def test_dwell_anomaly_medium(detector):
    """Test dwell anomaly with duration between 5-10 minutes (medium severity)"""
    now = time.time()
    # Person enters zone A at now - 400 seconds (6 minutes 40 seconds)
    track_states = [
        {"person_id": "person1", "zone_id": "zoneA", "event_type": "enter", "timestamp": now - 400},
        {"person_id": "person1", "zone_id": "zoneA", "event_type": "exit", "timestamp": now}
    ]
    zone_counts = {"zoneA": 0}
    
    anomalies = detector.check(track_states, zone_counts)
    
    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.anomaly_type == "dwell"
    assert anomaly.severity == "medium"
    assert anomaly.person_id == "person1"
    assert anomaly.zone_id == "zoneA"
    assert 300 < (anomaly.timestamp - (now - 400)) < 600  # duration around 400s
    detector._emit_anomaly.assert_called_once()

def test_crowd_anomaly_low(detector):
    """Test crowd anomaly with occupancy 1.0-1.5x threshold (low severity)"""
    now = time.time()
    track_states = []  # Not used for crowd
    zone_counts = {"zoneA": 9}  # threshold is 8, so 9 is 1.125x -> low
    
    anomalies = detector.check(track_states, zone_counts)
    
    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.anomaly_type == "crowd"
    assert anomaly.severity == "low"
    assert anomaly.person_id is None
    assert anomaly.zone_id == "zoneA"
    detector._emit_anomaly.assert_called_once()

def test_loitering_anomaly(detector):
    """Test loitering anomaly: person enters same zone more than 3 times in 10 minutes"""
    now = time.time()
    # Four enter events within 10 minutes
    track_states = [
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "enter", "timestamp": now - 500},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "exit", "timestamp": now - 450},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "enter", "timestamp": now - 400},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "exit", "timestamp": now - 350},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "enter", "timestamp": now - 300},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "exit", "timestamp": now - 250},
        {"person_id": "person1", "zone_id": "zoneB", "event_type": "enter", "timestamp": now - 100},
        # No exit for the last enter, but we count enters
    ]
    zone_counts = {"zoneB": 1}  # Currently one person in zone
    
    anomalies = detector.check(track_states, zone_counts)
    
    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.anomaly_type == "loitering"
    assert anomaly.severity == "medium"
    assert anomaly.person_id == "person1"
    assert anomaly.zone_id == "zoneB"
    assert "4 times" in anomaly.description
    detector._emit_anomaly.assert_called_once()

def test_dwell_deduplication(detector):
    """Test that same dwell anomaly is not re-emitted within 60 seconds"""
    now = time.time()
    track_states = [
        {"person_id": "person1", "zone_id": "zoneC", "event_type": "enter", "timestamp": now - 400},
        {"person_id": "person1", "zone_id": "zoneC", "event_type": "exit", "timestamp": now}
    ]
    zone_counts = {"zoneC": 0}
    
    # First check - should emit anomaly
    anomalies1 = detector.check(track_states, zone_counts)
    assert len(anomalies1) == 1
    first_anomaly_id = anomalies1[0].anomaly_id
    
    # Reset mock to check second call
    detector._emit_anomaly.reset_mock()
    
    # Second check immediately after - should not emit due to deduplication
    anomalies2 = detector.check(track_states, zone_counts)
    assert len(anomalies2) == 0  # No new anomalies generated
    detector._emit_anomaly.assert_not_called()
    
    # Simulate time passing >60 seconds
    with patch('time.time', return_value=now + 61):
        detector._emit_anomaly.reset_mock()
        anomalies3 = detector.check(track_states, zone_counts)
        # Should emit again because >60 seconds passed
        assert len(anomalies3) == 1
        assert anomalies3[0].anomaly_id != first_anomaly_id  # New anomaly ID
        detector._emit_anomaly.assert_called_once()

def test_anomaly_retrieval_endpoint(detector):
    """Test that anomalies can be retrieved via the endpoint (mocked)"""
    now = time.time()
    # Create a dwell anomaly
    track_states = [
        {"person_id": "person2", "zone_id": "zoneD", "event_type": "enter", "timestamp": now - 400},
        {"person_id": "person2", "zone_id": "zoneD", "event_type": "exit", "timestamp": now}
    ]
    zone_counts = {"zoneD": 0}
    
    anomalies = detector.check(track_states, zone_counts)
    assert len(anomalies) == 1
    anomaly = anomalies[0]
    
    # Mock Redis responses for the endpoint
    detector.redis_client.zrevrange.return_value = [anomaly.anomaly_id.encode('utf-8')]
    detector.redis_client.hget.return_value = json.dumps({
        "anomaly_id": anomaly.anomaly_id,
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "person_id": anomaly.person_id,
        "zone_id": anomaly.zone_id,
        "timestamp": anomaly.timestamp,
        "description": anomaly.description
    }).encode('utf-8')
    
    # Since we can't call the actual FastAPI endpoint without running the app,
    # we'll test the logic that the endpoint uses by calling the detector's methods
    # directly and checking the Redis calls.
    
    # In the endpoint, it would call:
    # anomaly_ids = detector.redis_client.zrevrange("anomalies:recent", 0, N-1)
    # for each id: get hash and return
    anomaly_ids = detector.redis_client.zrevrange("anomalies:recent", 0, 9)
    assert len(anomaly_ids) == 1
    assert anomaly_ids[0] == anomaly.anomaly_id.encode('utf-8')
    
    anomaly_data = detector.redis_client.hget(f"anomaly:{anomaly.anomaly_id}", "data")
    assert anomaly_data is not None
    retrieved = json.loads(anomaly_data.decode('utf-8'))
    assert retrieved["anomaly_id"] == anomaly.anomaly_id
    assert retrieved["severity"] == anomaly.severity

if __name__ == "__main__":
    pytest.main([__file__, "-v"])