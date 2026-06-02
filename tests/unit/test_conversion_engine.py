import time
from datetime import datetime

import pandas as pd

from services.conversion_engine import ConversionEngine


class FakeRedis:
    def __init__(self):
        self.storage = {}
        self.sets = {}
        self.hashes = {}
        self.sorted_sets = {}

    def get(self, key):
        return self.storage.get(key)

    def set(self, key, value):
        self.storage[key] = value

    def delete(self, key):
        self.storage.pop(key, None)

    def hset(self, name, mapping=None, **kwargs):
        if mapping is None:
            mapping = kwargs
        self.hashes.setdefault(name, {}).update(mapping)

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)

    def sadd(self, name, *values):
        self.sets.setdefault(name, set()).update(values)

    def smembers(self, name):
        return self.sets.get(name, set())

    def scard(self, name):
        return len(self.sets.get(name, set()))

    def sismember(self, name, value):
        return value in self.sets.get(name, set())

    def zadd(self, name, mapping):
        store = self.sorted_sets.setdefault(name, {})
        for member, score in mapping.items():
            store[member] = float(score)

    def zcount(self, name, min_score, max_score):
        store = self.sorted_sets.get(name, {})
        return sum(1 for score in store.values() if float(min_score) <= score <= float(max_score))

    def lpush(self, name, value):
        self.storage.setdefault(name, []).insert(0, value)

    def ltrim(self, name, start, end):
        self.storage[name] = self.storage.get(name, [])[start:end+1]

    def publish(self, channel, message):
        self.storage.setdefault(f'pubsub:{channel}', []).append(message)


def test_conversion_engine_flows():
    redis = FakeRedis()
    engine = ConversionEngine(redis)
    now = time.time()
    events = [
        {'event': 'entry', 'customer_id': '100', 'timestamp': now},
        {'event': 'browse', 'customer_id': '100', 'timestamp': now + 130},
        {'event': 'checkout_visit', 'customer_id': '100', 'timestamp': now + 140},
        {'event': 'exit', 'customer_id': '100', 'timestamp': now + 200},
        {'event': 'staff_ignore', 'customer_id': '100', 'timestamp': now + 210},
    ]

    engine.process_customer_events(events)
    assert redis.scard('funnel:entered_store') == 1
    assert redis.scard('funnel:browsed_gt_2min') == 1
    assert redis.scard('funnel:reached_checkout_zone') == 1

    df = pd.DataFrame([
        {'order_id': 'O-1', 'order_date': '2026-06-02', 'salesperson_name': 'Alice', 'qty': 1, 'GMV': 100.0, 'NMV': 90.0, 'sub_category': 'Beauty', 'brand_name': 'Acme', 'dep_name': 'Cosmetics'}
    ])
    engine.record_conversions(df)
    assert redis.scard('funnel:converted') == 1

    funnel = engine.get_funnel_metrics()
    assert funnel[0]['step'] == 'Entered Store'
    assert funnel[0]['value'] == 1
    assert funnel[-1]['step'] == 'Converted'
    assert funnel[-1]['value'] == 1
