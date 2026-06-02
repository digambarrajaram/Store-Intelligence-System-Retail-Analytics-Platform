import json
import time

from services.alert_engine import AlertEngine


class FakeRedis:
    def __init__(self):
        self.storage = {}
        self.sets = {}
        self.sorted_sets = {}
        self.published = []

    def zadd(self, name, mapping):
        store = self.sorted_sets.setdefault(name, {})
        for member, score in mapping.items():
            store[member] = float(score)

    def zcount(self, name, min_score, max_score):
        store = self.sorted_sets.get(name, {})
        return sum(1 for score in store.values() if float(min_score) <= score <= float(max_score))

    def zremrangebyscore(self, name, min_score, max_score):
        store = self.sorted_sets.get(name, {})
        if not store:
            return
        self.sorted_sets[name] = {
            member: score
            for member, score in store.items()
            if not (float(min_score) <= score <= float(max_score))
        }

    def scard(self, name):
        return len(self.sets.get(name, set()))

    def smembers(self, name):
        return self.sets.get(name, set())

    def sadd(self, name, *values):
        self.sets.setdefault(name, set()).update(values)

    def publish(self, channel, message):
        self.published.append((channel, message))

    def lpush(self, name, value):
        self.storage.setdefault(name, []).insert(0, value)

    def ltrim(self, name, start, end):
        self.storage[name] = self.storage.get(name, [])[start:end+1]


class FakeZoneManager:
    def get_active_zone(self, point):
        return 'checkout_zone' if point[0] > 100 else 'browsing_zone'


def test_alert_engine_triggers_overcrowding_and_checkout():
    redis = FakeRedis()
    zone_manager = FakeZoneManager()
    alert_engine = AlertEngine(redis, zone_manager, thresholds={
        'overcrowding': 2,
        'queue_congestion': 1,
        'long_dwell_seconds': 30,
        'traffic_spike_factor': 1.5,
        'traffic_spike_window_sec': 120,
        'checkout_bottleneck_min_visits': 1,
        'checkout_conversion_rate': 1.0,
    })

    detections = [
        {'track_id': 1, 'bbox': [150.0, 100.0, 170.0, 180.0]},
        {'track_id': 2, 'bbox': [160.0, 110.0, 180.0, 190.0]},
        {'track_id': 3, 'bbox': [170.0, 120.0, 190.0, 200.0]},
    ]
    event_time = time.time()

    alert_engine.process_frame(
        customer_events=[
            {'event': 'entry', 'customer_id': '1', 'timestamp': event_time},
            {'event': 'checkout_visit', 'customer_id': '1', 'zone': 'checkout_zone', 'timestamp': event_time + 5},
            {'event': 'dwell_time', 'customer_id': '2', 'zone': 'browsing_zone', 'dwell_seconds': 40, 'timestamp': event_time + 10},
        ],
        detections=detections,
        timestamp=event_time + 10,
        camera_id='camera_1',
    )

    published_alerts = [json.loads(message) for _, message in redis.published]
    assert any(alert.get('type') == 'Overcrowding' for alert in published_alerts)
    assert any(alert.get('type') == 'Queue Congestion' for alert in published_alerts)
    assert any(alert.get('type') == 'Long Dwell' for alert in published_alerts)
    assert any(alert.get('type') == 'Checkout Bottleneck' for alert in published_alerts)
