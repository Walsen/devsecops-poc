"""
Kinesis stream consumer for the worker service.

This module handles consuming messages from Kinesis and delegating
to the MessageProcessor for actual processing.

Following hexagonal architecture, dependencies are injected via constructor.
"""

import asyncio
import json
from typing import Any

import structlog
from aiobotocore.session import get_session

from .config import settings
from .domain.ports import IdempotencyPort
from .infrastructure.logging import set_correlation_id
from .processor import MessageProcessor

logger = structlog.get_logger()


class KinesisConsumer:
    """
    Kinesis stream consumer for processing message events.

    Following hexagonal architecture:
    - MessageProcessor is injected (not created internally)
    - IdempotencyPort is injected (not fetched from global)
    """

    def __init__(
        self,
        processor: MessageProcessor,
        idempotency: IdempotencyPort,
    ) -> None:
        """
        Initialize with injected dependencies.

        Args:
            processor: MessageProcessor instance
            idempotency: IdempotencyPort implementation
        """
        self._processor = processor
        self._idempotency = idempotency
        self._session = get_session()
        self._running = False

    async def start(self) -> None:
        """Start consuming from Kinesis stream."""
        self._running = True
        logger.info(
            "Starting Kinesis consumer",
            stream=settings.kinesis_stream_name,
            region=settings.aws_region,
        )

        client_kwargs = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        async with self._session.create_client("kinesis", **client_kwargs) as client:
            stream_desc = await client.describe_stream(StreamName=settings.kinesis_stream_name)
            shards = stream_desc["StreamDescription"]["Shards"]

            tasks = [self._process_shard(client, shard["ShardId"]) for shard in shards]
            await asyncio.gather(*tasks)

    async def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        logger.info("Stopping Kinesis consumer")

    async def _process_shard(self, client: Any, shard_id: str) -> None:
        """Process records from a single shard."""
        logger.info("Processing shard", shard_id=shard_id)

        iterator_response = await client.get_shard_iterator(
            StreamName=settings.kinesis_stream_name,
            ShardId=shard_id,
            ShardIteratorType="LATEST",
        )
        shard_iterator = iterator_response["ShardIterator"]

        while self._running and shard_iterator:
            try:
                response = await client.get_records(
                    ShardIterator=shard_iterator,
                    Limit=100,
                )

                for record in response.get("Records", []):
                    await self._process_record(record)

                shard_iterator = response.get("NextShardIterator")

                if not response.get("Records"):
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error("Error processing shard", shard_id=shard_id, error=str(e))
                await asyncio.sleep(5)

    async def _process_record(self, record: dict) -> None:
        """Process a single Kinesis record with idempotency."""
        try:
            data = json.loads(record["Data"].decode("utf-8"))
            event_type = data.get("event_type")
            payload = data.get("payload", {})

            # Extract and set correlation ID for distributed tracing
            correlation_id = data.get("correlation_id", "")
            if correlation_id:
                set_correlation_id(correlation_id)

            # Bind correlation ID to all logs in this record processing
            with structlog.contextvars.bound_contextvars(
                correlation_id=correlation_id,
                event_type=event_type,
            ):
                logger.info(
                    "Processing event",
                    message_id=payload.get("message_id"),
                )

                if event_type == "message.scheduled":
                    await self._handle_scheduled_message(payload)
                else:
                    logger.warning("Unknown event type")

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in record", error=str(e))
        except Exception as e:
            logger.error("Error processing record", error=str(e))

    async def _handle_scheduled_message(self, payload: dict) -> None:
        """Handle a message.scheduled event."""
        message_id = payload["message_id"]
        channels = payload["channels"]

        # Security: Check idempotency to prevent duplicate processing
        idempotency_key = self._idempotency.generate_key(message_id, channels)
        existing = self._idempotency.check_and_lock(idempotency_key)

        if existing:
            if existing.status == "completed":
                logger.info(
                    "Skipping duplicate message (idempotent)",
                    message_id=message_id,
                )
                return
            elif existing.status == "processing":
                logger.info(
                    "Message already being processed",
                    message_id=message_id,
                )
                return

        try:
            await self._processor.process_scheduled_message(
                message_id=message_id,
                channels=channels,
            )
            self._idempotency.mark_completed(
                idempotency_key,
                {"message_id": message_id, "channels": channels},
            )
        except Exception as e:
            self._idempotency.mark_failed(idempotency_key, str(e))
            raise
