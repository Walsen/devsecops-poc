import json

import structlog
from aiobotocore.session import get_session

from .config import settings

logger = structlog.get_logger()


class EventPublisher:
    """Publishes events to Kinesis for worker processing."""

    def __init__(self) -> None:
        self._session = get_session()

    async def publish_message_due(
        self,
        message_id: str,
        channels: list[str],
    ) -> None:
        """Publish a message.scheduled event for a due message."""
        event = {
            "event_type": "message.scheduled",
            "payload": {
                "message_id": message_id,
                "channels": channels,
            },
        }

        client_kwargs = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        async with self._session.create_client("kinesis", **client_kwargs) as client:
            await client.put_record(
                StreamName=settings.kinesis_stream_name,
                Data=json.dumps(event).encode("utf-8"),
                PartitionKey=message_id,
            )

        logger.info(
            "Published message.scheduled event",
            message_id=message_id,
            channels=channels,
        )
