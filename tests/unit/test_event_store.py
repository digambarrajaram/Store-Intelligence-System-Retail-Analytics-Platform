import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.event_store import EventStore


class SimpleRedisStub:
    def __init__(self):
        self.storage = {}
        self.sorted_sets = {}

    def pipeline(self):
        return self

    def set(self, key, value):
        self.storage[key] = value
        return self

    def zadd(self, key, mapping):
        if key not in self.sorted_sets:
            self.sorted_sets[key] = {}
        self.sorted_sets[key].update(mapping)
        return self

    def execute(self):
        return []

    def get(self, key):
        return self.storage.get(key)

    def zrange(self, key, start, end):
        if key not in self.sorted_sets:
            return []
        ids = sorted(self.sorted_sets[key].items(), key=lambda item: item[1])
        return [item[0] for item in ids][start:end+1]

    def zrevrange(self, key, start, end):
        if key not in self.sorted_sets:
            return []
        ids = sorted(self.sorted_sets[key].items(), key=lambda item: item[1], reverse=True)
        return [item[0] for item in ids][start:end+1]


def test_event_store_save_and_query_by_customer():
    redis = SimpleRedisStub()
    store = EventStore(redis)

    event = {
        'customer_id': 'cust1',
        'event': 'entry',
        'zone': 'entry_zone',
        'timestamp': 1710000000.0,
    }
    event_id = store.save_event(event)
    assert isinstance(event_id, str)

    results = store.get_events(customer_id='cust1')
    assert len(results) == 1
    assert results[0]['event_id'] == event_id
    assert results[0]['zone'] == 'entry_zone'


def test_event_store_query_by_date_zone_and_type():
    redis = SimpleRedisStub()
    store = EventStore(redis)
    event = {
        'customer_id': 'cust2',
        'event': 'checkout_visit',
        'zone': 'checkout_zone',
        'timestamp': 1710000000.0,
    }
    store.save_event(event)

    date_results = store.get_events(date='2024-03-09')
    assert len(date_results) == 1
    zone_results = store.get_events(zone='checkout_zone')
    assert len(zone_results) == 1
    type_results = store.get_events(event_type='checkout_visit')
    assert len(type_results) == 1


def test_get_customer_journey_returns_ordered_events():
    redis = SimpleRedisStub()
    store = EventStore(redis)
    events = [
        {'customer_id': 'cust3', 'event': 'entry', 'zone': 'entry_zone', 'timestamp': 1710000000.0},
        {'customer_id': 'cust3', 'event': 'checkout_visit', 'zone': 'checkout_zone', 'timestamp': 1710000030.0},
    ]
    store.save_events(events)

    journey = store.get_customer_journey('cust3')
    assert len(journey) == 2
    assert journey[0]['event'] == 'entry'
    assert journey[1]['event'] == 'checkout_visit'
