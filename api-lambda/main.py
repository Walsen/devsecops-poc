"""Lambda handler for API - placeholder for serverless deployment."""


def handler(event: dict, context) -> dict:
    """AWS Lambda handler for API Gateway proxy integration."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message": "API Lambda placeholder"}',
    }
