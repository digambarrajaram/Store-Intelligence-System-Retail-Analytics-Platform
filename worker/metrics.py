from prometheus_client import Counter, Gauge, Histogram, REGISTRY

def _get_or_create(metric_class, name, documentation, labelnames=None, **kwargs):
    """Get existing metric or create new one — prevents duplicate registration errors."""
    labelnames = labelnames or []
    try:
        return metric_class(name, documentation, labelnames, **kwargs)
    except ValueError:
        # Already registered — return the existing one from the registry
        return REGISTRY._names_to_collectors.get(name)


store_entries_total = _get_or_create(
    Counter,
    'store_entries_total',
    'Total number of store entries',
    ['camera_id', 'is_reentry']
)

store_exits_total = _get_or_create(
    Counter,
    'store_exits_total',
    'Total number of store exits',
    ['camera_id']
)

store_current_occupancy = _get_or_create(
    Gauge,
    'store_current_occupancy',
    'Current number of people in the store',
    ['camera_id']
)

frame_processing_seconds = _get_or_create(
    Histogram,
    'frame_processing_seconds',
    'Time spent processing a frame',
    ['camera_id'],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0]
)

anomalies_total = _get_or_create(
    Counter,
    'anomalies_total',
    'Total number of anomalies detected',
    ['anomaly_type', 'severity']
)

kafka_publish_errors_total = _get_or_create(
    Counter,
    'kafka_publish_errors_total',
    'Total number of Kafka publish errors',
    ['topic']
)