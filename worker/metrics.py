from prometheus_client import Counter, Gauge, Histogram

# Define custom metrics (same as in api/metrics.py)
store_entries_total = Counter(
    'store_entries_total',
    'Total number of store entries',
    ['camera_id', 'is_reentry']
)

store_exits_total = Counter(
    'store_exits_total',
    'Total number of store exits',
    ['camera_id']
)

store_current_occupancy = Gauge(
    'store_current_occupancy',
    'Current number of people in the store',
    ['camera_id']
)

frame_processing_seconds = Histogram(
    'frame_processing_seconds',
    'Time spent processing a frame',
    ['camera_id'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0]
)

anomalies_total = Counter(
    'anomalies_total',
    'Total number of anomalies detected',
    ['anomaly_type', 'severity']
)

kafka_publish_errors_total = Counter(
    'kafka_publish_errors_total',
    'Total number of Kafka publish errors',
    ['topic']
)