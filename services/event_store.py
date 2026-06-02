import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def _to_timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                raise ValueError('Invalid timestamp string')
    if isinstance(value, datetime):
        return value.timestamp()
    raise ValueError('Unsupported timestamp type')


def _date_string(timestamp: float) -> str:
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')


class EventStore:
    def __init__(self, redis_client, namespace: str = 'customer_events'):
        self.redis = redis_client
        self.namespace = namespace

    def _event_key(self, event_id: str) -> str:
        return f'{self.namespace}:event:{event_id}'

    def _index_key(self, index_name: str, index_value: str) -> str:
        return f'{self.namespace}:{index_name}:{index_value}'

    def _global_index_key(self) -> str:
        return f'{self.namespace}:all'

    def save_event(self, event: Dict[str, Any]) -> str:
        timestamp = _to_timestamp(event.get('timestamp', time.time()))
        event_id = event.get('event_id') or uuid.uuid4().hex
        customer_id = str(event.get('customer_id', 'unknown'))
        event_type = str(event.get('event', 'unknown'))
        zone = event.get('zone') or 'unknown'
        event_date = _date_string(timestamp)

        event_record = dict(event)
        event_record['event_id'] = event_id
        event_record['customer_id'] = customer_id
        event_record['event'] = event_type
        event_record['zone'] = zone
        event_record['timestamp'] = timestamp
        event_record['date'] = event_date

        serialized = json.dumps(event_record)

        pipe = self.redis.pipeline()
        pipe.set(self._event_key(event_id), serialized)
        pipe.zadd(self._global_index_key(), {event_id: timestamp})
        pipe.zadd(self._index_key('by_customer', customer_id), {event_id: timestamp})
        pipe.zadd(self._index_key('by_date', event_date), {event_id: timestamp})
        pipe.zadd(self._index_key('by_zone', zone), {event_id: timestamp})
        pipe.zadd(self._index_key('by_event', event_type), {event_id: timestamp})
        pipe.execute()

        return event_id

    def save_events(self, events: Iterable[Dict[str, Any]]) -> List[str]:
        ids = []
        for event in events:
            ids.append(self.save_event(event))
        return ids

    def _load_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        payload = self.redis.get(self._event_key(event_id))
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def get_events(
        self,
        customer_id: Optional[str] = None,
        date: Optional[str] = None,
        zone: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        # Choose primary index for retrieval
        index_key = None
        if customer_id:
            index_key = self._index_key('by_customer', customer_id)
        elif date:
            index_key = self._index_key('by_date', date)
        elif zone:
            index_key = self._index_key('by_zone', zone)
        elif event_type:
            index_key = self._index_key('by_event', event_type)
        else:
            index_key = self._global_index_key()

        range_fn = self.redis.zrange if ascending else self.redis.zrevrange
        event_ids = range_fn(index_key, 0, limit - 1)

        results = []
        for event_id in event_ids:
            event = self._load_event(event_id)
            if not event:
                continue
            if customer_id and event.get('customer_id') != customer_id:
                continue
            if date and event.get('date') != date:
                continue
            if zone and event.get('zone') != zone:
                continue
            if event_type and event.get('event') != event_type:
                continue
            results.append(event)

        return results

    def get_customer_journey(
        self,
        customer_id: str,
        date: Optional[str] = None,
        limit: int = 100,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        return self.get_events(
            customer_id=customer_id,
            date=date,
            limit=limit,
            ascending=ascending,
        )
