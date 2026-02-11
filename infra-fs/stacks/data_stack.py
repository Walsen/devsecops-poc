"""Data Stack - DynamoDB tables and Kinesis stream for serverless architecture."""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class DataStack(Stack):
    """DynamoDB tables, Kinesis stream, and S3 bucket for serverless architecture."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Main table - Single Table Design for messages and certifications
        self.main_table = dynamodb.Table(
            self,
            "MainTable",
            table_name="omnichannel-main",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            time_to_live_attribute="ttl",
        )

        # GSI for querying by user
        self.main_table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(name="GSI1PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="GSI1SK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI for querying by status (scheduled messages ready for processing)
        self.main_table.add_global_secondary_index(
            index_name="GSI2",
            partition_key=dynamodb.Attribute(name="GSI2PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="GSI2SK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Kinesis stream for async message processing
        self.kinesis_stream = kinesis.Stream(
            self,
            "MessageStream",
            stream_name="omnichannel-messages",
            shard_count=1,
            retention_period=Duration.hours(24),
            encryption=kinesis.StreamEncryption.MANAGED,
        )

        # S3 bucket for media uploads
        self.media_bucket = s3.Bucket(
            self,
            "MediaBucket",
            bucket_name=f"omnichannel-media-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT],
                    allowed_origins=["*"],  # Restrict in production
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
        )
