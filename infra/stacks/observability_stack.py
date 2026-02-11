"""
Observability Stack — CloudWatch metric filters, alarms, SNS topics, and dashboard.

Depends on: ComputeStack (log groups)
No AWS service enablement — pure CloudWatch resources, zero risk of failure.
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct


class ObservabilityStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        api_log_group: logs.ILogGroup | None = None,
        worker_log_group: logs.ILogGroup | None = None,
        scheduler_log_group: logs.ILogGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.alerts_topic = sns.Topic(
            self,
            "AlertsTopic",
            display_name="Application Alerts",
        )
        self.security_alerts_topic = sns.Topic(
            self,
            "SecurityAlertsTopic",
            display_name="Security Alerts (High Priority)",
        )

        if api_log_group:
            self._create_log_metric_filters("Api", api_log_group)
            self._create_security_metric_filters("Api", api_log_group)
        if worker_log_group:
            self._create_log_metric_filters("Worker", worker_log_group)
        if scheduler_log_group:
            self._create_log_metric_filters("Scheduler", scheduler_log_group)

        self._create_security_dashboard()

    def _create_log_metric_filters(
        self,
        service_name: str,
        log_group: logs.ILogGroup,
    ) -> None:
        ns = "SecureApi/Logs"

        error_filter = logs.MetricFilter(
            self,
            f"{service_name}ErrorFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name=f"{service_name}ErrorCount",
            filter_pattern=logs.FilterPattern.string_value("$.level", "=", "error"),
            metric_value="1",
        )
        error_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}ErrorAlarm",
            metric=error_filter.metric(statistic="Sum", period=Duration.minutes(5)),
            threshold=10,
            evaluation_periods=1,
            alarm_description=f"High error rate in {service_name} service",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        error_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

        critical_filter = logs.MetricFilter(
            self,
            f"{service_name}CriticalFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name=f"{service_name}CriticalCount",
            filter_pattern=logs.FilterPattern.string_value("$.level", "=", "critical"),
            metric_value="1",
        )
        critical_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}CriticalAlarm",
            metric=critical_filter.metric(statistic="Sum", period=Duration.minutes(1)),
            threshold=1,
            evaluation_periods=1,
            alarm_description=f"Critical error in {service_name} — immediate attention required",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        critical_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

        latency_filter = logs.MetricFilter(
            self,
            f"{service_name}LatencyFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name=f"{service_name}SlowOperations",
            filter_pattern=logs.FilterPattern.exists("$.duration_ms"),
            metric_value="$.duration_ms",
        )
        latency_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}LatencyAlarm",
            metric=latency_filter.metric(statistic="p95", period=Duration.minutes(5)),
            threshold=1000,
            evaluation_periods=3,
            alarm_description=f"High latency (p95 > 1s) in {service_name} service",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        latency_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

    def _create_security_metric_filters(
        self,
        service_name: str,
        log_group: logs.ILogGroup,
    ) -> None:
        ns = "SecureApi/Security"

        # Failed authentication
        auth_filter = logs.MetricFilter(
            self,
            f"{service_name}AuthFailedFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name="FailedAuthAttempts",
            filter_pattern=logs.FilterPattern.literal(
                '?"JWT verification failed" ?"Authentication required" ?"Invalid or expired token"'
            ),
            metric_value="1",
        )
        auth_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}AuthFailedAlarm",
            metric=auth_filter.metric(statistic="Sum", period=Duration.minutes(5)),
            threshold=50,
            evaluation_periods=1,
            alarm_description="High failed auth rate — potential brute force",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        auth_alarm.add_alarm_action(cw_actions.SnsAction(self.security_alerts_topic))

        # Rate limit hits
        rate_filter = logs.MetricFilter(
            self,
            f"{service_name}RateLimitFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name="RateLimitHits",
            filter_pattern=logs.FilterPattern.literal('"Rate limit exceeded"'),
            metric_value="1",
        )
        rate_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}RateLimitAlarm",
            metric=rate_filter.metric(statistic="Sum", period=Duration.minutes(5)),
            threshold=100,
            evaluation_periods=1,
            alarm_description="High rate limit hits — potential abuse",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        rate_alarm.add_alarm_action(cw_actions.SnsAction(self.security_alerts_topic))

        # Access denied (IDOR attempts)
        access_filter = logs.MetricFilter(
            self,
            f"{service_name}AccessDeniedFilter",
            log_group=log_group,
            metric_namespace=ns,
            metric_name="AccessDenied",
            filter_pattern=logs.FilterPattern.literal('?"Access denied" ?"ForbiddenError"'),
            metric_value="1",
        )
        access_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}AccessDeniedAlarm",
            metric=access_filter.metric(statistic="Sum", period=Duration.minutes(5)),
            threshold=30,
            evaluation_periods=1,
            alarm_description="High access denied rate — potential IDOR attempts",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        access_alarm.add_alarm_action(cw_actions.SnsAction(self.security_alerts_topic))

    def _create_security_dashboard(self) -> None:
        dashboard = cloudwatch.Dashboard(
            self,
            "SecurityDashboard",
            dashboard_name="SecureApi-Security",
        )

        # Row 1: Auth & Access
        dashboard.add_widgets(
            cloudwatch.TextWidget(markdown="# Auth & Access Control", width=24, height=1),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Failed Auth Attempts",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="FailedAuthAttempts",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    )
                ],
            ),
            cloudwatch.GraphWidget(
                title="Rate Limit Hits",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="RateLimitHits",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    )
                ],
            ),
            cloudwatch.GraphWidget(
                title="Access Denied (IDOR)",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="AccessDenied",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    )
                ],
            ),
        )

        # Row 2: WAF
        dashboard.add_widgets(
            cloudwatch.TextWidget(markdown="# WAF", width=24, height=1),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="WAF Blocked Requests",
                width=12,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/WAFV2",
                        metric_name="BlockedRequests",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        dimensions_map={
                            "WebACL": "secure-api-waf",
                            "Region": self.region,
                            "Rule": "ALL",
                        },
                    )
                ],
            ),
            cloudwatch.GraphWidget(
                title="WAF Allowed vs Blocked",
                width=12,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/WAFV2",
                        metric_name="AllowedRequests",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        dimensions_map={
                            "WebACL": "secure-api-waf",
                            "Region": self.region,
                            "Rule": "ALL",
                        },
                        label="Allowed",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/WAFV2",
                        metric_name="BlockedRequests",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        dimensions_map={
                            "WebACL": "secure-api-waf",
                            "Region": self.region,
                            "Rule": "ALL",
                        },
                        label="Blocked",
                    ),
                ],
            ),
        )

        # Row 3: App Health
        dashboard.add_widgets(
            cloudwatch.TextWidget(markdown="# Application Health", width=24, height=1),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Error Rate by Service",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="ApiErrorCount",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="API",
                    ),
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="WorkerErrorCount",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Worker",
                    ),
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="SchedulerErrorCount",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Scheduler",
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="API Latency (p95)",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="ApiSlowOperations",
                        statistic="p95",
                        period=Duration.minutes(5),
                    )
                ],
            ),
            cloudwatch.GraphWidget(
                title="Critical Errors",
                width=8,
                height=6,
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="ApiCriticalCount",
                        statistic="Sum",
                        period=Duration.minutes(1),
                        label="API",
                    ),
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="WorkerCriticalCount",
                        statistic="Sum",
                        period=Duration.minutes(1),
                        label="Worker",
                    ),
                ],
            ),
        )
