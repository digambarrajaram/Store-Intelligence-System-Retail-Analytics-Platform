import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.zone_manager import ZoneManager


def test_point_in_polygon_inside():
    manager = ZoneManager()
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert manager.point_in_polygon((5, 5), polygon) is True


def test_point_in_polygon_outside():
    manager = ZoneManager()
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert manager.point_in_polygon((15, 5), polygon) is False


def test_zone_lookup_returns_named_zone():
    manager = ZoneManager()
    # Pick a point inside the configured entry zone
    point = (100, 900)
    zone = manager.zone_lookup(point)
    assert zone is not None
    assert zone['zone_id'] == 'entry_zone'
    assert zone['zone_meta']['category'] == 'entry'


def test_zone_lookup_returns_none_for_outside_point():
    manager = ZoneManager()
    point = (960, 1075)
    assert manager.zone_lookup(point) is None


def test_get_active_zone_returns_zone_id():
    manager = ZoneManager()
    point = (100, 900)
    assert manager.get_active_zone(point) == 'entry_zone'


def test_zone_transition_detection_entry_exit_and_transition():
    manager = ZoneManager()
    timestamp = datetime.utcnow().timestamp()

    entry_event = manager.zone_transition_detection(None, 'entry_zone', timestamp)
    assert entry_event is not None
    assert entry_event['event'] == 'entry'
    assert entry_event['from_zone'] is None
    assert entry_event['to_zone'] == 'entry_zone'

    exit_event = manager.zone_transition_detection('exit_zone', None, timestamp)
    assert exit_event is not None
    assert exit_event['event'] == 'exit'
    assert exit_event['from_zone'] == 'exit_zone'
    assert exit_event['to_zone'] is None

    transition_event = manager.zone_transition_detection('browsing_zone', 'checkout_zone', timestamp)
    assert transition_event is not None
    assert transition_event['event'] == 'zone_transition'
    assert transition_event['from_zone'] == 'browsing_zone'
    assert transition_event['to_zone'] == 'checkout_zone'
