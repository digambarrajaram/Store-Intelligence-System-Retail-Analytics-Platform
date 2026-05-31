import pytest
import asyncio
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as FakeAsyncRedis
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def fake_redis():
    """Fixture providing a fake Redis instance."""
    return FakeRedis()


@pytest.fixture
def fake_async_redis():
    """Fixture providing a fake async Redis instance."""
    return FakeAsyncRedis()


@pytest.fixture
def sample_detections():
    """Fixture providing sample detection data with 5 tracks."""
    base_time = datetime.now()
    detections = []
    for i in range(5):
        detections.append({
            'track_id': f'track_{i}',
            'bbox': [100 + i*20, 100 + i*10, 150 + i*20, 150 + i*10],  # x1, y1, x2, y2
            'confidence': 0.9 - i*0.1,
            'class_id': 0,  # person
            'timestamp': base_time + timedelta(seconds=i*2),
            'zone_id': 'zone_A' if i < 3 else 'zone_B'
        })
    return detections


@pytest.fixture
def sample_pos_data():
    """Fixture providing sample POS data in Brigade store CSV structure."""
    # Brigade store CSV structure: transaction_id, timestamp, amount, items, store_id, register_id
    data = {
        'transaction_id': ['txn_001', 'txn_002', 'txn_003', 'txn_004', 'txn_005'],
        'timestamp': [
            '2026-05-31 10:00:00',
            '2026-05-31 10:05:00',
            '2026-05-31 10:10:00',
            '2026-05-31 10:15:00',
            '2026-05-31 10:20:00'
        ],
        'amount': [25.50, 15.75, 42.00, 8.99, 33.50],
        'items': [2, 1, 3, 1, 2],
        'store_id': ['store_01'] * 5,
        'register_id': ['reg_01', 'reg_02', 'reg_01', 'reg_02', 'reg_01']
    }
    return pd.DataFrame(data)