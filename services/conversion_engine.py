import time
from typing import Any, Dict, List

import pandas as pd
from worker.metrics import conversion_events_total


class ConversionEngine:
    def __init__(self, redis_client: Any, session_timeout_seconds: int = 600, camera_id: str = None, store_id: str = 'store_1'):
        self.redis = redis_client
        self.session_timeout_seconds = session_timeout_seconds
        self.camera_id = camera_id or "store"
        self.store_id = store_id

    def _normalize_track_id(self, customer_id: Any) -> str:
        return str(customer_id or 'unknown')

    def _funnel_prefix(self) -> str:
        return f'funnel:store:{self.store_id}:camera:{self.camera_id}'

    def _store_funnel_prefix(self) -> str:
        return f'funnel:store:{self.store_id}'

    def _active_session_key(self, track_id: str) -> str:
        return f'{self._funnel_prefix()}:active_session:{track_id}'

    def _session_hash_key(self, session_id: str) -> str:
        return f'{self._funnel_prefix()}:session:{session_id}'

    def _session_id(self, track_id: str, timestamp: float) -> str:
        return f'{track_id}:{int(timestamp)}'

    def _ensure_active_session(self, track_id: str, timestamp: float) -> str:
        session_id = self.redis.get(self._active_session_key(track_id))
        if session_id:
            return session_id

        session_id = self._session_id(track_id, timestamp)
        self.redis.set(self._active_session_key(track_id), session_id)
        self.redis.hset(
            self._session_hash_key(session_id),
            mapping={
                'track_id': track_id,
                'entered_at': timestamp,
                'has_browsed': 0,
                'reached_checkout': 0,
                'converted': 0,
            }
        )
        self.redis.sadd(f'{self._funnel_prefix()}:entered_store', session_id)
        self.redis.zadd(f'{self._funnel_prefix()}:entry_timestamps', {session_id: timestamp})
        # Also add to store-wide aggregation
        self.redis.sadd(f'{self._store_funnel_prefix()}:entered_store', session_id)
        return session_id

    def _close_session(self, track_id: str) -> None:
        session_id = self.redis.get(self._active_session_key(track_id))
        if session_id:
            self.redis.delete(self._active_session_key(track_id))
            self.redis.set(f'{self._funnel_prefix()}:last_exit:{track_id}', time.time())

    def process_customer_events(self, events: List[Dict[str, Any]]) -> None:
        try:
            for event in events:
                event_type = event.get('event')
                if event_type == 'staff_ignore':
                    continue

                customer_id = self._normalize_track_id(event.get('customer_id'))
                timestamp = float(event.get('timestamp', time.time()))

                if event_type == 'entry':
                    self._ensure_active_session(customer_id, timestamp)
                    conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='entry').inc()
                elif event_type == 'browse':
                    session_id = self._ensure_active_session(customer_id, timestamp)
                    if not self.redis.sismember(f'{self._funnel_prefix()}:browsed_gt_2min', session_id):
                        self.redis.sadd(f'{self._funnel_prefix()}:browsed_gt_2min', session_id)
                        self.redis.hset(self._session_hash_key(session_id), mapping={'has_browsed': 1})
                        # Also add to store-wide aggregation
                        self.redis.sadd(f'{self._store_funnel_prefix()}:browsed_gt_2min', session_id)
                        conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='browse').inc()
                elif event_type == 'checkout_visit':
                    session_id = self._ensure_active_session(customer_id, timestamp)
                    if not self.redis.sismember(f'{self._funnel_prefix()}:reached_checkout_zone', session_id):
                        self.redis.sadd(f'{self._funnel_prefix()}:reached_checkout_zone', session_id)
                        self.redis.hset(self._session_hash_key(session_id), mapping={'reached_checkout': 1})
                        # Also add to store-wide aggregation
                        self.redis.sadd(f'{self._store_funnel_prefix()}:reached_checkout_zone', session_id)
                        conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='checkout').inc()
                elif event_type == 'exit':
                    self._close_session(customer_id)
                    conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='exit').inc()
        except Exception:
            import traceback
            print(f"ConversionEngine.process_customer_events ERROR: {traceback.format_exc()}")

    def record_conversions(self, df: pd.DataFrame) -> None:
        if df.empty:
            return

        order_ids = [str(value) for value in df['order_id'].tolist()]
        if not order_ids:
            return

        self.redis.sadd(f'{self._store_funnel_prefix()}:converted', *order_ids)
        timestamp = time.time()
        for order_id in order_ids:
            self.redis.zadd(f'{self._store_funnel_prefix()}:converted_timestamps', {order_id: timestamp})
        conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='converted').inc(len(order_ids))

    async def record_conversions_async(self, df: pd.DataFrame) -> None:
        if df.empty:
            return

        order_ids = [str(value) for value in df['order_id'].tolist()]
        if not order_ids:
            return

        await self.redis.sadd(f'{self._store_funnel_prefix()}:converted', *order_ids)
        timestamp = time.time()
        for order_id in order_ids:
            await self.redis.zadd(f'{self._store_funnel_prefix()}:converted_timestamps', {order_id: timestamp})
        conversion_events_total.labels(store_id=self.store_id, camera_id=self.camera_id, stage='converted').inc(len(order_ids))

    def get_funnel_metrics(self) -> List[Dict[str, int]]:
        entered_store = self.redis.smembers(f'{self._funnel_prefix()}:entered_store') or set()
        browsed_gt_2min = self.redis.smembers(f'{self._funnel_prefix()}:browsed_gt_2min') or set()
        reached_checkout_zone = self.redis.smembers(f'{self._funnel_prefix()}:reached_checkout_zone') or set()
        converted = self.redis.smembers(f'{self._store_funnel_prefix()}:converted') or set()

        return [
            {'step': 'Entered Store', 'value': len(entered_store)},
            {'step': 'Browsed > 2 min', 'value': len(browsed_gt_2min)},
            {'step': 'Reached Checkout', 'value': len(reached_checkout_zone)},
            {'step': 'Converted', 'value': len(converted)},
        ]
