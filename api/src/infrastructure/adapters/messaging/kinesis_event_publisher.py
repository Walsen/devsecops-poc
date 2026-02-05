import json
from typing import Any

from aiobotocore.session import get_session

from ....application.ports.outbound import EventPublisher


class KinesisEventPublisher(EventPublisher):
    """Kinesis adapter implementing EventPublisher port."""

    def __init__(
        self,
        stream_name: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._stream_name = stream_name
        self._region = region
        self._endpoint_url = endpoint_url
        self._session = get_session()

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to Kinesis."""
        event = {
            "event_type": event_type,
            "payload": payload,
        }

        client_kwargs = {"region_name": self._region}
        if self._endpoint_url:
            client_kwargs["endpoint_url"] = self._endpoint_url

        async with self._session.create_client("kinesis", **client_kwargs) as client:
            await client.put_record(
                StreamName=self._stream_name,
                Data=json.dumps(event).encode("utf-8"),
                PartitionKey=payload.get("message_id", "default"),
            )
