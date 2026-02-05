import json
from typing import Any

from aiobotocore.session import get_session

from ...application.interfaces import EventPublisher


class KinesisEventPublisher(EventPublisher):
    """Kinesis implementation of EventPublisher."""

    def __init__(self, stream_name: str, region: str = "us-east-1") -> None:
        self._stream_name = stream_name
        self._region = region
        self._session = get_session()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to Kinesis."""
        event = {
            "event_type": event_type,
            "payload": payload,
        }

        async with self._session.create_client("kinesis", region_name=self._region) as client:
            await client.put_record(
                StreamName=self._stream_name,
                Data=json.dumps(event).encode("utf-8"),
                PartitionKey=payload.get("message_id", "default"),
            )
