"""Scheduler Stack - EventBridge Scheduler for triggering scheduled messages."""

from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_events_targets as targets,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from constructs import Construct


class SchedulerStack(Stack):
    """EventBridge rule + Lambda for processing scheduled messages."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        main_table: dynamodb.Table,
        kinesis_stream: kinesis.Stream,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Scheduler Lambda function
        self.scheduler_function = lambda_.Function(
            self,
            "SchedulerFunction",
            function_name="omnichannel-scheduler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="main.handler",
            code=lambda_.Code.from_asset("../scheduler-lambda"),
            environment={
                "TABLE_NAME": main_table.table_name,
                "KINESIS_STREAM_NAME": kinesis_stream.stream_name,
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=lambda_.Architecture.ARM_64,
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Grant permissions
        main_table.grant_read_write_data(self.scheduler_function)
        kinesis_stream.grant_write(self.scheduler_function)

        # EventBridge rule - runs every minute
        self.schedule_rule = events.Rule(
            self,
            "ScheduleRule",
            rule_name="omnichannel-scheduler-trigger",
            description="Triggers scheduler Lambda every minute to process due messages",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )

        self.schedule_rule.add_target(
            targets.LambdaFunction(
                self.scheduler_function,
                retry_attempts=2,
            )
        )

        # DLQ for failed scheduler invocations
        # In production, add SQS DLQ for failed events
