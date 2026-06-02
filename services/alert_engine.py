import json
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

from worker.metrics import (
    alerts_generated_total,
    occupancy_threshold_breaches_total,
    zone_transitions_total,
)


class AlertEngine:
    def __init__(
        self,
        redis_client: Any,
        zone_manager: Any,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.redis = redis_client
        self.zone_manager = zone_manager
        self.thresholds = {
            'overcrowding': 10,
            'queue_congestion': 4,
            'long_dwell_seconds': 120,
            'traffic_spike_factor': 2.0,
            'traffic_spike_window_sec': 300,
            'checkout_bottleneck_min_visits': 5,
            'checkout_conversion_rate': 0.35,
            **(thresholds or {}),
        }

    def _now(self) -> float:
        return time.time()

    def _alert_id(self) -> str:
        return uuid.uuid4().hex

    def _publish_alert(self, alert: Dict[str, Any]) -> None:
        payload = json.dumps(alert)
        try:
            self.redis.publish('anomaly_alerts', payload)
            self.redis.lpush('recent_anomalies', payload)
            self.redis.ltrim('recent_anomalies', 0, 9)
            alerts_generated_total.labels(alert_type=alert['type'], severity=alert['severity']).inc()
        except Exception as exc:
            print(f'Alert publish failed: {exc}')

    def _record_entry(self, timestamp: float, track_id: str) -> None:
        self.redis.zadd('alerts:entry_timestamps', {f'{track_id}:{timestamp}': timestamp})
        window = self.thresholds['traffic_spike_window_sec']
        self.redis.zremrangebyscore('alerts:entry_timestamps', 0, timestamp - window)

    def _record_checkout_visit(self, timestamp: float, track_id: str) -> None:
        self.redis.zadd('alerts:checkout_visits', {f'{track_id}:{timestamp}': timestamp})
        window = self.thresholds['traffic_spike_window_sec']
        self.redis.zremrangebyscore('alerts:checkout_visits', 0, timestamp - window)

    def process_frame(
        self,
        customer_events: Optional[List[Dict[str, Any]]] = None,
        detections: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[float] = None,
        camera_id: str = 'unknown',
    ) -> None:
        timestamp = timestamp or self._now()
        customer_events = customer_events or []

        for event in customer_events:
            if event.get('event') == 'staff_ignore':
                continue

            if event.get('event') == 'entry':
                self._record_entry(timestamp, str(event.get('customer_id', 'unknown')))
                zone_transitions_total.labels(zone=str(event.get('zone', 'unknown'))).inc()
            elif event.get('event') == 'checkout_visit':
                self._record_checkout_visit(timestamp, str(event.get('customer_id', 'unknown')))
                zone_transitions_total.labels(zone=str(event.get('zone', 'unknown'))).inc()
                self._check_checkout_bottleneck(timestamp)
            elif event.get('event') == 'dwell_time':
                if event.get('zone') == 'browsing_zone':
                    dwell_seconds = float(event.get('dwell_seconds', 0))
                    if dwell_seconds >= self.thresholds['long_dwell_seconds']:
                        self._generate_alert(
                            'Long Dwell',
                            'warning',
                            'Browsing',
                            {
                                'track_id': event.get('customer_id'),
                                'dwell_seconds': dwell_seconds,
                            },
                        )
            elif event.get('event') in ('entry', 'exit'):
                zone_transitions_total.labels(zone=str(event.get('zone', 'unknown'))).inc()

        self._check_overcrowding(detections, camera_id, timestamp)
        self._check_queue_congestion(detections, camera_id, timestamp)
        self._check_traffic_spike(timestamp)

    def _generate_alert(
        self,
        alert_type: str,
        severity: str,
        zone: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        alert = {
            'id': self._alert_id(),
            'severity': severity,
            'type': alert_type,
            'zone': zone,
            'timestamp': self._now(),
            'metadata': metadata or {},
        }
        self._publish_alert(alert)

    def _check_overcrowding(
        self,
        detections: Optional[List[Dict[str, Any]]],
        camera_id: str,
        timestamp: float,
    ) -> None:
        if not detections:
            return
        occupancy = len(detections)
        threshold = int(self.thresholds['overcrowding'])
        if occupancy > threshold:
            occupancy_threshold_breaches_total.labels(condition='overcrowding').inc()
            self._generate_alert(
                'Overcrowding',
                'critical' if occupancy > threshold * 1.5 else 'warning',
                'Store',
                {'camera_id': camera_id, 'occupancy': occupancy, 'threshold': threshold},
            )

    def _check_queue_congestion(
        self,
        detections: Optional[List[Dict[str, Any]]],
        camera_id: str,
        timestamp: float,
    ) -> None:
        if not detections or not self.zone_manager:
            return

        checkout_count = 0
        for detection in detections:
            bbox = detection.get('bbox')
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
            active_zone = self.zone_manager.get_active_zone(centroid)
            if active_zone == 'checkout_zone':
                checkout_count += 1

        threshold = int(self.thresholds['queue_congestion'])
        if checkout_count > threshold:
            occupancy_threshold_breaches_total.labels(condition='checkout_queue').inc()
            self._generate_alert(
                'Queue Congestion',
                'warning' if checkout_count <= threshold * 1.5 else 'critical',
                'Checkout',
                {'camera_id': camera_id, 'checkout_count': checkout_count, 'threshold': threshold},
            )

    def _check_traffic_spike(self, timestamp: float) -> None:
        window = self.thresholds['traffic_spike_window_sec']
        current_minute_count = self.redis.zcount('alerts:entry_timestamps', timestamp - 60, timestamp)
        historical_count = self.redis.zcount('alerts:entry_timestamps', timestamp - window, timestamp - 60)
        historical_avg = historical_count / max(1, window / 60)
        if historical_avg > 0 and current_minute_count > historical_avg * self.thresholds['traffic_spike_factor']:
            self._generate_alert(
                'Traffic Spike',
                'warning',
                'Entry',
                {
                    'rate_per_minute': current_minute_count,
                    'historical_avg': round(historical_avg, 2),
                },
            )

    def _check_checkout_bottleneck(self, timestamp: float) -> None:
        checkout_visits = self.redis.scard('funnel:reached_checkout_zone') or 0
        converted = self.redis.scard('funnel:converted') or 0
        threshold = int(self.thresholds['checkout_bottleneck_min_visits'])
        if checkout_visits < threshold:
            return

        conversion_rate = converted / checkout_visits if checkout_visits > 0 else 0.0
        if conversion_rate < float(self.thresholds['checkout_conversion_rate']):
            self._generate_alert(
                'Checkout Bottleneck',
                'warning' if conversion_rate >= 0.2 else 'critical',
                'Checkout',
                {
                    'checkout_visits': checkout_visits,
                    'converted': converted,
                    'conversion_rate': round(conversion_rate, 2),
                },
            )
