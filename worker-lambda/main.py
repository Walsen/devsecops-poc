"""Lambda handler for Worker - placeholder for serverless deployment."""


def handler(event: dict, context) -> dict:
    """AWS Lambda handler for Kinesis event source."""
    records = event.get("Records", [])
    return {"batchItemFailures": [], "processedRecords": len(records)}
