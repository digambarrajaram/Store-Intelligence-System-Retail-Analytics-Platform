from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Gauge, Histogram

# Define custom metrics
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

alerts_generated_total = Counter(
    'alerts_generated_total',
    'Total number of alerts generated',
    ['alert_type', 'severity']
)

zone_transitions_total = Counter(
    'zone_transitions_total',
    'Total number of zone transitions detected',
    ['zone']
)

conversion_events_total = Counter(
    'conversion_events_total',
    'Total number of conversion funnel events processed',
    ['stage']
)

occupancy_threshold_breaches_total = Counter(
    'occupancy_threshold_breaches_total',
    'Total number of occupancy threshold breaches detected',
    ['condition']
)


def instrument_app(app):
    """
    Instruments the FastAPI app with Prometheus metrics.
    This includes the default metrics from instrumentator and our custom metrics.
    """
    Instrumentator().instrument(app).expose(app)
    # Note: The custom metrics are already defined above and can be used in the app.
    # We don't need to do anything else to expose them because they are registered with the Prometheus client.
    # However, we must ensure that the metrics are updated in the application code.