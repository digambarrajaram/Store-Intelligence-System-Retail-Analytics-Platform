import time
from typing import Dict, List, Optional, Tuple

from services.zone_manager import ZoneManager

Point = Tuple[float, float]
Detection = Dict[str, object]
Event = Dict[str, object]


class VideoProcessor:
    def __init__(
        self,
        layout_path: str = 'store_layout.json',
        zones_path: str = 'zones.json',
        browse_threshold_seconds: int = 120,
    ):
        self.zone_manager = ZoneManager(layout_path=layout_path, zones_path=zones_path)
        self.browse_threshold_seconds = browse_threshold_seconds
        self.track_states: Dict[str, Dict[str, object]] = {}

    @staticmethod
    def _compute_centroid(bbox: List[float]) -> Point:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _get_state(self, track_id: str) -> Dict[str, object]:
        return self.track_states.setdefault(
            track_id,
            {
                'previous_zone_id': None,
                'zone_entered_at': None,
                'browsing_started_at': None,
                'browse_reported': False,
                'last_zone_id': None,
                'last_timestamp': None,
            }
        )

    def _create_event(
        self,
        customer_id: str,
        event_name: str,
        zone: Optional[str],
        timestamp: float,
        extra: Optional[Dict[str, object]] = None,
    ) -> Event:
        payload: Event = {
            'customer_id': customer_id,
            'event': event_name,
            'zone': zone,
            'timestamp': timestamp,
        }
        if extra:
            payload.update(extra)
        return payload

    def _build_dwell_event(
        self,
        track_id: str,
        zone_id: Optional[str],
        entered_at: Optional[float],
        timestamp: float,
    ) -> Optional[Event]:
        if zone_id is None or entered_at is None:
            return None
        dwell_seconds = max(0, timestamp - entered_at)
        return self._create_event(
            customer_id=track_id,
            event_name='dwell_time',
            zone=zone_id,
            timestamp=timestamp,
            extra={'dwell_seconds': round(dwell_seconds, 2)}
        )

    def _build_browse_event(
        self,
        track_id: str,
        timestamp: float,
        dwell_seconds: float,
    ) -> Event:
        return self._create_event(
            customer_id=track_id,
            event_name='browse',
            zone='browsing_zone',
            timestamp=timestamp,
            extra={'dwell_seconds': round(dwell_seconds, 2)}
        )

    def process_frame(
        self,
        frame_id: int,
        timestamp: float,
        camera_id: str,
        detections: List[Detection],
    ) -> List[Event]:
        customer_events: List[Event] = []
        for detection in detections:
            track_id = str(detection.get('track_id', 'unknown'))
            bbox = detection.get('bbox')
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            centroid = self._compute_centroid([float(coord) for coord in bbox])
            zone_info = self.zone_manager.zone_lookup(centroid)
            current_zone_id = zone_info['zone_id'] if zone_info else None

            state = self._get_state(track_id)
            previous_zone_id = state.get('previous_zone_id')
            zone_entered_at = state.get('zone_entered_at')
            browsing_started_at = state.get('browsing_started_at')
            browse_reported = state.get('browse_reported', False)

            transition = self.zone_manager.zone_transition_detection(
                previous_zone_id,
                current_zone_id,
                timestamp
            )

            if transition:
                if current_zone_id == 'staff_zone' and previous_zone_id != 'staff_zone':
                    customer_events.append(
                        self._create_event(
                            track_id,
                            'staff_ignore',
                            current_zone_id,
                            timestamp,
                            extra={'from_zone': previous_zone_id}
                        )
                    )

                if transition['event'] == 'entry':
                    customer_events.append(
                        self._create_event(track_id, 'entry', current_zone_id, timestamp)
                    )
                    state['zone_entered_at'] = timestamp
                    state['browsing_started_at'] = timestamp if current_zone_id == 'browsing_zone' else None
                    state['browse_reported'] = False

                elif transition['event'] == 'exit':
                    dwell_event = self._build_dwell_event(track_id, previous_zone_id, zone_entered_at, timestamp)
                    if dwell_event:
                        customer_events.append(dwell_event)
                    customer_events.append(
                        self._create_event(track_id, 'exit', previous_zone_id, timestamp)
                    )
                    state['zone_entered_at'] = None
                    state['browsing_started_at'] = None
                    state['browse_reported'] = False

                elif transition['event'] == 'zone_transition':
                    if current_zone_id == 'checkout_zone':
                        customer_events.append(
                            self._create_event(track_id, 'checkout_visit', current_zone_id, timestamp, extra={'from_zone': previous_zone_id})
                        )
                    if previous_zone_id == 'browsing_zone' and zone_entered_at is not None:
                        dwell_event = self._build_dwell_event(track_id, previous_zone_id, zone_entered_at, timestamp)
                        if dwell_event:
                            customer_events.append(dwell_event)
                        state['browsing_started_at'] = None
                        state['browse_reported'] = False
                    state['zone_entered_at'] = timestamp
                    state['browsing_started_at'] = timestamp if current_zone_id == 'browsing_zone' else None

                state['previous_zone_id'] = current_zone_id
                state['last_zone_id'] = current_zone_id
                state['last_timestamp'] = timestamp
                continue

            if current_zone_id == 'browsing_zone' and browsing_started_at is not None and not browse_reported:
                dwell_seconds = timestamp - browsing_started_at
                if dwell_seconds >= self.browse_threshold_seconds:
                    customer_events.append(
                        self._build_browse_event(track_id, timestamp, dwell_seconds)
                    )
                    customer_events.append(
                        self._create_event(track_id, 'dwell_time', 'browsing_zone', timestamp, extra={'dwell_seconds': round(dwell_seconds, 2)})
                    )
                    state['browse_reported'] = True

            state['previous_zone_id'] = current_zone_id
            state['last_zone_id'] = current_zone_id
            state['last_timestamp'] = timestamp

        return customer_events
