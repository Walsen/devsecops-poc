"""Lambda handler for Scheduler - placeholder for serverless deployment."""


def handler(event: dict, context) -> dict:
    """AWS Lambda handler for EventBridge scheduled events."""
    return {"statusCode": 200, "processed": 0}
