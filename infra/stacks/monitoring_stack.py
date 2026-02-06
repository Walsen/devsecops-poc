from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_cloudtrail as cloudtrail,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_cloudwatch_actions as cw_actions,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_events_targets as targets,
)
from aws_cdk import (
    aws_guardduty as guardduty,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_securityhub as securityhub,
)
from aws_cdk import (
    aws_sns as sns,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        waf_ip_set: wafv2.CfnIPSet,
        api_log_group: logs.ILogGroup | None = None,
        worker_log_group: logs.ILogGroup | None = None,
        scheduler_log_group: logs.ILogGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # SNS Topic for alerts
        self.alerts_topic = sns.Topic(
            self,
            "AlertsTopic",
            display_name="Application Alerts",
        )

        # Create metric filters and alarms for each service log group
        if api_log_group:
            self._create_log_metric_filters("Api", api_log_group)
        if worker_log_group:
            self._create_log_metric_filters("Worker", worker_log_group)
        if scheduler_log_group:
            self._create_log_metric_filters("Scheduler", scheduler_log_group)

        # GuardDuty Detector
        guardduty.CfnDetector(
            self,
            "GuardDutyDetector",
            enable=True,
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        # Security Hub
        securityhub.CfnHub(self, "SecurityHub")

        # CloudTrail - Dev: Single region only
        cloudtrail.Trail(
            self,
            "AuditTrail",
            send_to_cloud_watch_logs=True,
            cloud_watch_logs_retention=logs.RetentionDays.ONE_WEEK,  # Dev: Short retention
            include_global_service_events=True,
            is_multi_region_trail=False,  # Dev: Single region
        )

        # Lambda to auto-block malicious IPs from GuardDuty findings
        lambda_code = """
import boto3
import os

wafv2 = boto3.client('wafv2')

def handler(event, context):
    detail = event.get('detail', {})
    finding_type = detail.get('type', '')

    # Only process network-related findings
    threat_types = ['UnauthorizedAccess', 'Recon', 'Trojan']
    if not any(t in finding_type for t in threat_types):
        return {'statusCode': 200, 'body': 'Skipped - not a network threat'}

    # Extract attacker IP
    service = detail.get('service', {})
    action = service.get('action', {})

    remote_ip = None
    if 'networkConnectionAction' in action:
        conn = action['networkConnectionAction']
        remote_ip = conn.get('remoteIpDetails', {}).get('ipAddressV4')
    elif 'portProbeAction' in action:
        probe = action['portProbeAction'].get('portProbeDetails', [{}])[0]
        remote_ip = probe.get('remoteIpDetails', {}).get('ipAddressV4')

    if not remote_ip:
        return {'statusCode': 200, 'body': 'No IP found'}

    ip_set_name = os.environ['IP_SET_NAME']
    ip_set_id = os.environ['IP_SET_ID']
    ip_set_scope = os.environ['IP_SET_SCOPE']

    # Get current IP set
    response = wafv2.get_ip_set(Name=ip_set_name, Scope=ip_set_scope, Id=ip_set_id)
    addresses = response['IPSet']['Addresses']
    lock_token = response['LockToken']

    # Add new IP if not already blocked
    new_ip = f"{remote_ip}/32"
    if new_ip not in addresses:
        addresses.append(new_ip)
        wafv2.update_ip_set(
            Name=ip_set_name,
            Scope=ip_set_scope,
            Id=ip_set_id,
            Addresses=addresses,
            LockToken=lock_token
        )
        print(f"Blocked IP: {remote_ip}")

    return {'statusCode': 200, 'body': f'Processed IP: {remote_ip}'}
"""

        block_ip_lambda = lambda_.Function(
            self,
            "BlockIpLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(lambda_code),
            environment={
                "IP_SET_NAME": waf_ip_set.name,
                "IP_SET_ID": waf_ip_set.attr_id,
                "IP_SET_SCOPE": "REGIONAL",
            },
            timeout=Duration.seconds(30),
        )

        # Grant Lambda permission to update WAF IP Set
        block_ip_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["wafv2:GetIPSet", "wafv2:UpdateIPSet"],
                resources=[waf_ip_set.attr_arn],
            )
        )

        # EventBridge rule to trigger Lambda on GuardDuty findings
        guard_duty_rule = events.Rule(
            self,
            "GuardDutyRule",
            event_pattern=events.EventPattern(
                source=["aws.guardduty"],
                detail_type=["GuardDuty Finding"],
                detail={"severity": [{"numeric": [">=", 4]}]},  # Medium+
            ),
        )

        guard_duty_rule.add_target(targets.LambdaFunction(block_ip_lambda))

    def _create_log_metric_filters(
        self,
        service_name: str,
        log_group: logs.ILogGroup,
    ) -> None:
        """
        Create CloudWatch metric filters and alarms for structured logs.

        Filters for:
        - Error count (level = "error")
        - Critical alerts (level = "critical")
        - Slow operations (duration_ms > 1000)
        """
        namespace = "SecureApi/Logs"

        # Error count metric filter
        error_filter = logs.MetricFilter(
            self,
            f"{service_name}ErrorFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name=f"{service_name}ErrorCount",
            filter_pattern=logs.FilterPattern.literal('"level": "error"'),
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

        # Critical alert metric filter (immediate notification)
        critical_filter = logs.MetricFilter(
            self,
            f"{service_name}CriticalFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name=f"{service_name}CriticalCount",
            filter_pattern=logs.FilterPattern.literal('"level": "critical"'),
            metric_value="1",
        )

        critical_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}CriticalAlarm",
            metric=critical_filter.metric(statistic="Sum", period=Duration.minutes(1)),
            threshold=1,
            evaluation_periods=1,
            alarm_description=(
                f"Critical error in {service_name} service - immediate attention required"
            ),
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        critical_alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))

        # Slow operations metric filter (duration_ms > 1000)
        # Uses JSON filter pattern to extract duration_ms field
        latency_filter = logs.MetricFilter(
            self,
            f"{service_name}LatencyFilter",
            log_group=log_group,
            metric_namespace=namespace,
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
