"""Worker Stack - Lambda function triggered by Kinesis for message delivery."""

from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_lambda_event_sources as event_sources,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class WorkerStack(Stack):
    """Lambda function that processes messages from Kinesis and delivers to channels."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        main_table: dynamodb.Table,
        kinesis_stream: kinesis.Stream,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Secrets for social media APIs
        self.social_secrets = secretsmanager.Secret(
            self,
            "SocialMediaSecrets",
            secret_name="omnichannel/social-media-credentials",
            description="API credentials for social media platforms",
        )

        # Worker Lambda function
        self.worker_function = lambda_.Function(
            self,
            "WorkerFunction",
            function_name="omnichannel-worker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="main.handler",
            code=lambda_.Code.from_asset("../worker-lambda"),
            environment={
                "TABLE_NAME": main_table.table_name,
                "SECRETS_ARN": self.social_secrets.secret_arn,
                "LOG_LEVEL": "INFO",
                "USE_AI_AGENT": "true",
                "BEDROCK_MODEL_ID": "anthropic.claude-haiku-4-5-20251001-v1:0",
            },
            timeout=Duration.minutes(5),
            memory_size=1024,
            architecture=lambda_.Architecture.ARM_64,
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
            reserved_concurrent_executions=10,  # Limit concurrency for rate limiting
        )

        # Grant permissions
        main_table.grant_read_write_data(self.worker_function)
        self.social_secrets.grant_read(self.worker_function)

        # Bedrock permissions for AI agent
        self.worker_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # SES permissions for email
        self.worker_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # SNS permissions for SMS
        self.worker_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                resources=["*"],
            )
        )

        # Kinesis event source - triggers Lambda on new records
        self.worker_function.add_event_source(
            event_sources.KinesisEventSource(
                kinesis_stream,
                starting_position=lambda_.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                parallelization_factor=1,
                report_batch_item_failures=True,
            )
        )
