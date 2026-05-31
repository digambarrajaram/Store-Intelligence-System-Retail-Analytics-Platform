import time
from typing import Dict, Optional


class ReentryTracker:
    """Track exits to prevent counting re-entries within a cooldown period as new entries."""

    def __init__(self, cooldown_seconds: int = 300):
        """
        Args:
            cooldown_seconds: Time in seconds after exit within which a re-entry
                              should be ignored (default 300 seconds = 5 minutes).
        """
        self.exit_log: Dict[int, float] = {}  # track_id -> exit_timestamp
        self.cooldown_seconds = cooldown_seconds

    def record_exit(self, track_id: int, timestamp: float) -> None:
        """Record the exit time for a track_id."""
        self.exit_log[track_id] = timestamp

    def is_reentry(self, track_id: int, current_time: float) -> bool:
        """
        Check if a track_id represents a re-entry within the cooldown period.

        If it is a re-entry, the exit log entry is removed to avoid double counting.

        Returns:
            True if track_id is a re-entry (should not count as new entry), False otherwise.
        """
        exit_time = self.exit_log.get(track_id)
        if exit_time is None:
            return False
        if current_time - exit_time < self.cooldown_seconds:
            # It's a re-entry within cooldown; remove the exit log.
            del self.exit_log[track_id]
            return True
        # If outside cooldown, keep the exit log? Actually if they haven't re-entered,
        # we might want to keep it? But if they are seen again after cooldown,
        # it should be considered a new entry. We can keep the exit log; next call
        # will see it's older than cooldown and return False, but we should clean up.
        # For simplicity, we remove it anyway because if they are seen again after
        # cooldown, it's a new entry and we don't need the old exit time.
        del self.exit_log[track_id]
        return False


class StaffFilter:
    """Filter tracks that likely correspond to staff based on behavioral heuristics."""

    def __init__(self):
        # track_id -> {
        #   'first_seen': float,
        #   'total_dwell': float,
        #   'last_zone': str,
        #   'last_timestamp': float,
        #   'zone_transitions': int  # transitions between ENTRY_ZONE and BACK_ZONE
        # }
        self._data: Dict[int, dict] = {}

    def update(self, track_id: int, zone: str, timestamp: float) -> None:
        """
        Update tracking information for a track_id.

        Args:
            track_id: Identifier of the tracked person.
            zone: Current zone (e.g., "ENTRY_ZONE", "BACK_ZONE", "OTHER").
            timestamp: Current timestamp in seconds.
        """
        if track_id not in self._data:
            self._data[track_id] = {
                'first_seen': timestamp,
                'total_dwell': 0.0,
                'last_zone': zone,
                'last_timestamp': timestamp,
                'zone_transitions': 0
            }
            return

        data = self._data[track_id]
        # Accumulate dwell time since last update
        if data['last_timestamp'] is not None:
            data['total_dwell'] += timestamp - data['last_timestamp']
        # Check for zone transition between ENTRY_ZONE and BACK_ZONE
        last_zone = data['last_zone']
        if ((last_zone == "ENTRY_ZONE" and zone == "BACK_ZONE") or
            (last_zone == "BACK_ZONE" and zone == "ENTRY_ZONE")):
            data['zone_transitions'] += 1
        # Update last zone and timestamp
        data['last_zone'] = zone
        data['last_timestamp'] = timestamp

    def is_staff(self, track_id: int) -> bool:
        """
        Determine if a track_id likely corresponds to staff.

        Returns:
            True if either heuristic is met:
                - Total dwell time > 30 minutes (1800 seconds)
                - Zone transitions between ENTRY_ZONE and BACK_ZONE > 5
            False otherwise or if track_id unknown.
        """
        data = self._data.get(track_id)
        if data is None:
            return False
        if data['total_dwell'] > 30 * 60:  # 30 minutes in seconds
            return True
        if data['zone_transitions'] > 5:
            return True
        return False


# -------------------- Unit Tests --------------------
def test_reentry_tracker():
    tracker = ReentryTracker(cooldown_seconds=300)  # 5 minutes
    base_time = 1000.0

    # Case 1: First appearance, not a re-entry
    assert not tracker.is_reentry(1, base_time)
    # Record exit at time 1000
    tracker.record_exit(1, base_time)
    # Re-entry within cooldown (e.g., 200 seconds later)
    assert tracker.is_reentry(1, base_time + 200)
    # After re-entry, exit log cleared; another check should be False
    assert not tracker.is_reentry(1, base_time + 200)
    # Record another exit
    tracker.record_exit(1, base_time + 200)
    # Re-entry after cooldown (e.g., 400 seconds later, total 600 > 300)
    assert not tracker.is_reentry(1, base_time + 200 + 400)
    # Ensure exit log cleared after check
    assert not tracker.is_reentry(1, base_time + 200 + 400)


def test_reentry_tracker_custom_cooldown():
    tracker = ReentryTracker(cooldown_seconds=60)  # 1 minute
    base_time = 2000.0
    tracker.record_exit(42, base_time)
    # Within 30 seconds -> re-entry
    assert tracker.is_reentry(42, base_time + 30)
    # After 90 seconds -> not re-entry
    tracker.record_exit(42, base_time + 30)  # re-entered, but we need to record exit again? Actually after re-entry we would record exit later.
    # Simpler: after first re-entry, we need a new exit.
    tracker.record_exit(42, base_time + 30)
    assert not tracker.is_reentry(42, base_time + 30 + 90)


def test_staff_filter():
    sf = StaffFilter()
    base = 5000.0
    tid = 99

    # Initially not staff
    assert not sf.is_staff(tid)

    # Simulate staying in store for 31 minutes without zone changes
    # We'll update every minute with same zone to accumulate dwell.
    zone = "OTHER"
    for i in range(31):
        sf.update(tid, zone, base + i * 60)  # each minute
    # After 31 minutes, total dwell should be > 30*60
    assert sf.is_staff(tid)

    # Reset for second heuristic
    sf2 = StaffFilter()
    tid2 = 100
    # Simulate oscillating between ENTRY_ZONE and BACK_ZONE
    # Each oscillation (back and forth) counts as 2 transitions? Actually each change from ENTRY to BACK or BACK to ENTRY counts.
    # We need >5 transitions, so at least 6 transitions.
    timestamp = base
    zone_seq = ["ENTRY_ZONE", "BACK_ZONE"] * 3  # ENTRY, BACK, ENTRY, BACK, ENTRY, BACK -> 5 changes? Let's count:
    # Starting with ENTRY_ZONE (first update sets last_zone)
    # Then BACK_ZONE -> transition 1
    # ENTRY_ZONE -> transition 2
    # BACK_ZONE -> transition 3
    # ENTRY_ZONE -> transition 4
    # BACK_ZONE -> transition 5
    # Need >5, so add one more pair.
    zone_seq = ["ENTRY_ZONE", "BACK_ZONE"] * 4  # 8 zones, 7 transitions
    for z in zone_seq:
        sf2.update(tid2, z, timestamp)
        timestamp += 10  # small increments
    # After updates, zone_transitions should be 7
    assert sf2.is_staff(tid2)


def test_staff_filter_edge_cases():
    sf = StaffFilter()
    tid = 555
    # Not enough dwell time
    base = 0.0
    sf.update(tid, "ENTRY_ZONE", base)
    sf.update(tid, "ENTRY_ZONE", base + 29*60)  # 29 minutes
    assert not sf.is_staff(tid)
    sf.update(tid, "ENTRY_ZONE", base + 30*60 + 1)  # 30 minutes + 1 second
    assert sf.is_staff(tid)

    # Zone transitions with other zones should not count
    sf2 = StaffFilter()
    tid2 = 666
    base2 = 100.0
    sf2.update(tid2, "ENTRY_ZONE", base2)
    sf2.update(tid2, "OTHER_ZONE", base2 + 1)
    sf2.update(tid2, "BACK_ZONE", base2 + 2)
    sf2.update(tid2, "OTHER_ZONE", base2 + 3)
    sf2.update(tid2, "ENTRY_ZONE", base2 + 4)
    sf2.update(tid2, "BACK_ZONE", base2 + 5)
    # Only transitions ENTRY<->BACK count: we have ENTRY->OTHER (no), OTHER->BACK (no), BACK->OTHER (no), OTHER->ENTRY (no), ENTRY->BACK (yes) => 1 transition
    assert not sf2.is_staff(tid2)


if __name__ == "__main__":
    # Run tests if executed directly
    test_reentry_tracker()
    test_reentry_tracker_custom_cooldown()
    test_staff_filter()
    test_staff_filter_edge_cases()
    print("All tests passed.")