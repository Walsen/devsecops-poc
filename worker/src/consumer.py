import asyncio
import json
from typing import Any

import structlog
from aiobotocore.session import get_session

from .config import settings
from .processor import MessageProcessor

logger = structlog.get_logger()


class KinesisConsumer:
    """Kinesis stream consumer for processing message events."""

    def __init__(self, processor: MessageProcessor) -> None:
        self._processor = processor
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
            # Get shard iterator
            stream_desc = await client.describe_stream(StreamName=settings.kinesis_stream_name)
            shards = stream_desc["StreamDescription"]["Shards"]

            # Process all shards concurrently
            tasks = [self._process_shard(client, shard["ShardId"]) for shard in shards]
            await asyncio.gather(*tasks)

    async def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        logger.info("Stopping Kinesis consumer")

    async def _process_shard(self, client: Any, shard_id: str) -> None:
        """Process records from a single shard."""
        logger.info("Processing shard", shard_id=shard_id)

        # Get shard iterator (start from latest)
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

                # Avoid throttling
                if not response.get("Records"):
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error("Error processing shard", shard_id=shard_id, error=str(e))
                await asyncio.sleep(5)

    async def _process_record(self, record: dict) -> None:
        """Process a single Kinesis record."""
        try:
            data = json.loads(record["Data"].decode("utf-8"))
            event_type = data.get("event_type")
            payload = data.get("payload", {})

            logger.info(
                "Processing event",
                event_type=event_type,
                message_id=payload.get("message_id"),
            )

            if event_type == "message.scheduled":
                await self._processor.process_scheduled_message(
                    message_id=payload["message_id"],
                    channels=payload["channels"],
                )
            else:
                logger.warning("Unknown event type", event_type=event_type)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in record", error=str(e))
        except Exception as e:
            logger.error("Error processing record", error=str(e))
