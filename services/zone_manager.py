import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PathLike = str
Point = Tuple[float, float]
Polygon = List[Point]

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / 'config'


def _load_json(path: PathLike) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = DEFAULT_CONFIG_DIR / path
    with config_path.open('r', encoding='utf-8') as stream:
        return json.load(stream)


class ZoneManager:
    def __init__(self, layout_path: PathLike = 'store_layout.json', zones_path: PathLike = 'zones.json'):
        self.layout = _load_json(layout_path)
        self.zone_meta = _load_json(zones_path)
        self.zones = self._parse_zones(self.layout)

    def _parse_zones(self, layout: Dict[str, Any]) -> Dict[str, Polygon]:
        raw_zones = layout.get('zones', {})
        parsed: Dict[str, Polygon] = {}
        for zone_id, polygon in raw_zones.items():
            if not isinstance(polygon, list) or len(polygon) < 3:
                raise ValueError(f'Zone {zone_id} must contain at least 3 points')
            parsed[zone_id] = [tuple(point) for point in polygon]
        return parsed

    def point_in_polygon(self, point: Point, polygon: Polygon) -> bool:
        x, y = point
        inside = False
        n = len(polygon)
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            intersects = ((y1 > y) != (y2 > y)) and (
                x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            )
            if intersects:
                inside = not inside
        return inside

    def zone_lookup(self, point: Point) -> Optional[Dict[str, Any]]:
        for zone_id, polygon in self.zones.items():
            if self.point_in_polygon(point, polygon):
                return {
                    'zone_id': zone_id,
                    'zone_meta': self.zone_meta.get(zone_id, {}),
                    'polygon': polygon
                }
        return None

    def get_active_zone(self, point: Point) -> Optional[str]:
        zone_info = self.zone_lookup(point)
        return zone_info['zone_id'] if zone_info else None

    def zone_transition_detection(
        self,
        previous_zone_id: Optional[str],
        current_zone_id: Optional[str],
        timestamp: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        if previous_zone_id == current_zone_id:
            return None

        if previous_zone_id is None and current_zone_id is not None:
            event_type = 'entry'
        elif previous_zone_id is not None and current_zone_id is None:
            event_type = 'exit'
        else:
            event_type = 'zone_transition'

        return {
            'event': event_type,
            'from_zone': previous_zone_id,
            'to_zone': current_zone_id,
            'timestamp': timestamp,
            'details': {
                'from_meta': self.zone_meta.get(previous_zone_id, {}) if previous_zone_id else None,
                'to_meta': self.zone_meta.get(current_zone_id, {}) if current_zone_id else None
            }
        }

    def get_zone_info(self, zone_id: str) -> Dict[str, Any]:
        return {
            'zone_id': zone_id,
            'zone_meta': self.zone_meta.get(zone_id, {}),
            'polygon': self.zones.get(zone_id)
        }

    def available_zones(self) -> List[str]:
        return list(self.zones.keys())


def load_zone_manager() -> ZoneManager:
    return ZoneManager()
