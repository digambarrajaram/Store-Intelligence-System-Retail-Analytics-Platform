from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypeVar, Type

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from .schema import BaseModel  # Assuming all events inherit from BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class KafkaPublisher:
    """
    Async Kafka publisher for CV pipeline events with retry logic and dead letter queue.
    Supports multi-store, multi-camera partitioning via store_id:camera_id key.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        dlq_topic: str = "cv.dlq",
        max_retries: int = 3,
        retry_backoff_ms: int = 100,
    ):
        """
        Initialize the Kafka publisher.

        Args:
            bootstrap_servers: Kafka bootstrap servers comma-separated string
            topic: Target topic for publishing events
            dlq_topic: Dead letter queue topic for failed events
            max_retries: Maximum number of retry attempts
            retry_backoff_ms: Initial backoff in milliseconds for retries (exponential)
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.dlq_topic = dlq_topic
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start the Kafka producer."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
            logger.info(f"Kafka producer started for topic {self.topic}")

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    def _get_partition_key(self, event: BaseModel) -> bytes | None:
        """
        Derive partition key from store_id:camera_id for ordered processing per camera.
        """
        payload = event.model_dump()
        store_id = payload.get("store_id", "unknown")
        camera_id = payload.get("camera_id", "unknown")
        return f"{store_id}:{camera_id}".encode("utf-8")

    async def publish(self, event: BaseModel) -> None:
        """
        Publish an event to the Kafka topic with retry logic.
        Uses store_id:camera_id as the partition key for ordered per-camera processing.

        Args:
            event: Pydantic model instance to publish

        Raises:
            KafkaError: If publishing fails after all retries
        """
        if not self._producer:
            raise RuntimeError("Producer not started. Call start() before publishing.")

        payload = event.model_dump()
        event_type = event.__class__.__name__
        partition_key = self._get_partition_key(event)

        for attempt in range(self.max_retries + 1):
            try:
                await self._producer.send_and_wait(
                    self.topic,
                    payload,
                    key=partition_key,
                )
                logger.debug(f"Published {event_type} to {self.topic} with key={partition_key}")
                return
            except KafkaError as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries + 1} failed to publish {event_type}: {e}"
                )
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = self.retry_backoff_ms * (2**attempt) / 1000.0
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted, send to DLQ
                    await self._send_to_dlq(event, str(e))
                    logger.error(
                        f"Failed to publish {event_type} after {self.max_retries + 1} attempts. Sent to DLQ."
                    )
                    raise

    async def _send_to_dlq(self, event: BaseModel, error: str) -> None:
        """
        Send failed event to dead letter queue with error metadata.

        Args:
            event: Original event that failed to publish
            error: Error message from the publishing failure
        """
        if not self._producer:
            logger.error("Cannot send to DLQ: producer not started")
            return

        dlq_payload = {
            "original_event": event.model_dump(),
            "error": error,
            "failed_topic": self.topic,
            "timestamp": event.model_dump().get("timestamp"),
        }

        try:
            await self._producer.send_and_wait(self.dlq_topic, dlq_payload)
            logger.debug(f"Sent failed event to DLQ {self.dlq_topic}")
        except KafkaError as dlq_e:
            logger.error(f"Failed to send to DLQ: {dlq_e}")
