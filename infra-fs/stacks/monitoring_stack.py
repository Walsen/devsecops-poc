"""Monitoring Stack - CloudWatch dashboards and alarms for serverless."""

from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_cloudwatch_actions as cw_actions,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_sns as sns,
)
from constructs import Construct


class MonitoringStack(Stack):
    """CloudWatch dashboards and alarms for Lambda functions."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_function: lambda_.Function,
        worker_function: lambda_.Function,
        scheduler_function: lambda_.Function,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SNS topic for alerts
        self.alerts_topic = sns.Topic(
            self,
            "AlertsTopic",
            topic_name="omnichannel-alerts",
            display_name="Omnichannel Publisher Alerts",
        )

        # Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name="omnichannel-serverless",
        )

        # Lambda metrics widgets
        self.dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# Omnichannel Publisher - Serverless",
                width=24,
                height=1,
            ),
        )

        # API Function metrics
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Lambda - Invocations & Errors",
                left=[
                    api_function.metric_invocations(statistic="Sum"),
                    api_function.metric_errors(statistic="Sum"),
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="API Lambda - Duration",
                left=[
                    api_function.metric_duration(statistic="Average"),
                    api_function.metric_duration(statistic="p99"),
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="API Lambda - Concurrent Executions",
                left=[
                    api_function.metric("ConcurrentExecutions", statistic="Maximum"),
                ],
                width=8,
            ),
        )

        # Worker Function metrics
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Worker Lambda - Invocations & Errors",
                left=[
                    worker_function.metric_invocations(statistic="Sum"),
                    worker_function.metric_errors(statistic="Sum"),
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Worker Lambda - Duration",
                left=[
                    worker_function.metric_duration(statistic="Average"),
                    worker_function.metric_duration(statistic="p99"),
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Scheduler Lambda - Invocations",
                left=[
                    scheduler_function.metric_invocations(statistic="Sum"),
                    scheduler_function.metric_errors(statistic="Sum"),
                ],
                width=8,
            ),
        )

        # Alarms
        # API errors alarm
        api_errors_alarm = cloudwatch.Alarm(
            self,
            "ApiErrorsAlarm",
            alarm_name="omnichannel-api-errors",
            metric=api_function.metric_errors(statistic="Sum", period=Duration.minutes(5)),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="API Lambda error rate is high",
        )
        api_errors_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

        # Worker errors alarm
        worker_errors_alarm = cloudwatch.Alarm(
            self,
            "WorkerErrorsAlarm",
            alarm_name="omnichannel-worker-errors",
            metric=worker_function.metric_errors(statistic="Sum", period=Duration.minutes(5)),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Worker Lambda error rate is high",
        )
        worker_errors_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

        # API latency alarm
        api_latency_alarm = cloudwatch.Alarm(
            self,
            "ApiLatencyAlarm",
            alarm_name="omnichannel-api-latency",
            metric=api_function.metric_duration(statistic="p99", period=Duration.minutes(5)),
            threshold=5000,  # 5 seconds
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="API Lambda p99 latency is high",
        )
        api_latency_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))
