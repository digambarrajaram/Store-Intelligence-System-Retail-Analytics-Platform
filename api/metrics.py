"""Compatibility shim for metrics.

This module used to define Prometheus metrics directly. To avoid duplicate
registrations when the same process imports both the API and worker code we
centralised metric definitions in ``worker/metrics.py``. Importing this module
ensures the shared metrics are available for legacy imports (``import api.metrics``)
without redefining them.
"""

from typing import Any  # keep lint happy for imports below

# Re-export the shared metrics from the worker package. The definitions live in
# ``worker/metrics.py`` and use a get-or-create helper to avoid duplicate
# registrations when the module is imported multiple times in the same process.
from worker.metrics import (  # noqa: F401
    store_entries_total,
    store_exits_total,
    store_current_occupancy,
    frame_processing_seconds,
    anomalies_total,
    kafka_publish_errors_total,
    alerts_generated_total,
    zone_transitions_total,
    conversion_events_total,
    occupancy_threshold_breaches_total,
)


def instrument_app(app: Any) -> None:
    """No-op shim. Instrumentation is configured in ``main.py`` to avoid
    double-instrumenting the FastAPI app.
    """
    return