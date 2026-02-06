"""
Monitoring Stack - Phase 5: Security Observability, Compliance & Incident Response

Features:
- Security dashboards with key metrics
- Failed authentication alerting
- Compliance automation (AWS Config, Security Hub standards)
- Incident response automation (GuardDuty actions, runbooks)
- WAF metrics and alerting
"""

from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_config as config
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_guardduty as guardduty
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_securityhub as securityhub
from aws_cdk import aws_sns as sns
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        waf_ip_set: wafv2.CfnIPSet,
        waf_web_acl: wafv2.CfnWebACL | None = None,
        api_log_group: logs.ILogGroup | None = None,
        worker_log_group: logs.ILogGroup | None = None,
        scheduler_log_group: logs.ILogGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # SNS Topics for different alert severities
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

        # Create metric filters and alarms for each service log group
        if api_log_group:
            self._create_log_metric_filters("Api", api_log_group)
            self._create_security_metric_filters("Api", api_log_group)
        if worker_log_group:
            self._create_log_metric_filters("Worker", worker_log_group)
        if scheduler_log_group:
            self._create_log_metric_filters("Scheduler", scheduler_log_group)

        # =================================================================
        # Phase 5.1: Security Observability
        # =================================================================

        # GuardDuty Detector
        self.guardduty_detector = guardduty.CfnDetector(
            self,
            "GuardDutyDetector",
            enable=True,
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        # Security Hub with standards
        self.security_hub = securityhub.CfnHub(self, "SecurityHub")

        # Enable AWS Foundational Security Best Practices
        securityhub.CfnStandard(
            self,
            "AWSFoundationalStandard",
            standards_arn=(
                f"arn:aws:securityhub:{self.region}::standards/"
                "aws-foundational-security-best-practices/v/1.0.0"
            ),
        )

        # CloudTrail
        self.audit_trail = cloudtrail.Trail(
            self,
            "AuditTrail",
            send_to_cloud_watch_logs=True,
            cloud_watch_logs_retention=logs.RetentionDays.ONE_WEEK,
            include_global_service_events=True,
            is_multi_region_trail=False,
        )

        # =================================================================
        # Phase 5.2: Compliance Automation (AWS Config)
        # =================================================================
        self._create_config_rules()

        # =================================================================
        # Phase 5.3: Incident Response Automation
        # =================================================================
        self._create_incident_response_lambda(waf_ip_set)

        # =================================================================
        # Phase 5.4: Security Dashboard
        # =================================================================
        self._create_security_dashboard(waf_web_acl)

    def _create_log_metric_filters(
        self,
        service_name: str,
        log_group: logs.ILogGroup,
    ) -> None:
        """Create CloudWatch metric filters and alarms for structured logs."""
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

        # Critical alert metric filter
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

        # Slow operations metric filter
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

    def _create_security_metric_filters(
        self,
        service_name: str,
        log_group: logs.ILogGroup,
    ) -> None:
        """Create security-specific metric filters for authentication and access."""
        namespace = "SecureApi/Security"

        # Failed authentication attempts
        auth_failed_filter = logs.MetricFilter(
            self,
            f"{service_name}AuthFailedFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name="FailedAuthAttempts",
            filter_pattern=logs.FilterPattern.literal(
                '?"JWT verification failed" ?"Authentication required" ?"Invalid or expired token"'
            ),
            metric_value="1",
        )

        # Alert on high failed auth rate (potential brute force)
        auth_failed_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}AuthFailedAlarm",
            metric=auth_failed_filter.metric(
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=50,
            evaluation_periods=1,
            alarm_description="High rate of failed authentication attempts - potential brute force",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        auth_failed_alarm.add_alarm_action(
            cw_actions.SnsAction(self.security_alerts_topic)
        )

        # CSRF token failures
        csrf_failed_filter = logs.MetricFilter(
            self,
            f"{service_name}CSRFFailedFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name="CSRFFailures",
            filter_pattern=logs.FilterPattern.literal(
                '?"CSRF token" ?"csrf_token"'
            ),
            metric_value="1",
        )

        csrf_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}CSRFAlarm",
            metric=csrf_failed_filter.metric(
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=20,
            evaluation_periods=1,
            alarm_description="High rate of CSRF failures - potential attack",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        csrf_alarm.add_alarm_action(cw_actions.SnsAction(self.security_alerts_topic))

        # Rate limit hits
        rate_limit_filter = logs.MetricFilter(
            self,
            f"{service_name}RateLimitFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name="RateLimitHits",
            filter_pattern=logs.FilterPattern.literal('"Rate limit exceeded"'),
            metric_value="1",
        )

        rate_limit_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}RateLimitAlarm",
            metric=rate_limit_filter.metric(
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=100,
            evaluation_periods=1,
            alarm_description="High rate limit hits - potential abuse",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        rate_limit_alarm.add_alarm_action(cw_actions.SnsAction(self.security_alerts_topic))

        # Access denied (IDOR attempts)
        access_denied_filter = logs.MetricFilter(
            self,
            f"{service_name}AccessDeniedFilter",
            log_group=log_group,
            metric_namespace=namespace,
            metric_name="AccessDenied",
            filter_pattern=logs.FilterPattern.literal(
                '?"Access denied" ?"ForbiddenError"'
            ),
            metric_value="1",
        )

        access_denied_alarm = cloudwatch.Alarm(
            self,
            f"{service_name}AccessDeniedAlarm",
            metric=access_denied_filter.metric(
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=30,
            evaluation_periods=1,
            alarm_description="High access denied rate - potential IDOR attempts",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        access_denied_alarm.add_alarm_action(
            cw_actions.SnsAction(self.security_alerts_topic)
        )

    def _create_config_rules(self) -> None:
        """Create AWS Config rules for compliance monitoring."""
        # Config Recorder (required for rules)
        config_role = iam.Role(
            self,
            "ConfigRole",
            assumed_by=iam.ServicePrincipal("config.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWS_ConfigRole"
                ),
            ],
        )

        config.CfnConfigurationRecorder(
            self,
            "ConfigRecorder",
            role_arn=config_role.role_arn,
            recording_group=config.CfnConfigurationRecorder.RecordingGroupProperty(
                all_supported=True,
                include_global_resource_types=True,
            ),
        )

        # Rule: ECS tasks should not have public IPs
        config.ManagedRule(
            self,
            "EcsTaskNoPublicIp",
            identifier="ECS_TASK_DEFINITION_NONROOT_USER",
            description="ECS task definitions should run as non-root user",
        )

        # Rule: RDS encryption enabled
        config.ManagedRule(
            self,
            "RdsEncryptionEnabled",
            identifier="RDS_STORAGE_ENCRYPTED",
            description="RDS instances should have encryption enabled",
        )

        # Rule: S3 buckets should have encryption
        config.ManagedRule(
            self,
            "S3BucketEncryption",
            identifier="S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED",
            description="S3 buckets should have server-side encryption enabled",
        )

        # Rule: CloudTrail enabled
        config.ManagedRule(
            self,
            "CloudTrailEnabled",
            identifier="CLOUD_TRAIL_ENABLED",
            description="CloudTrail should be enabled",
        )

        # Rule: IAM password policy
        config.ManagedRule(
            self,
            "IamPasswordPolicy",
            identifier="IAM_PASSWORD_POLICY",
            description="IAM password policy should meet requirements",
        )

        # Rule: VPC flow logs enabled
        config.ManagedRule(
            self,
            "VpcFlowLogsEnabled",
            identifier="VPC_FLOW_LOGS_ENABLED",
            description="VPC flow logs should be enabled",
        )

        # Rule: Secrets Manager rotation
        config.ManagedRule(
            self,
            "SecretsManagerRotation",
            identifier="SECRETSMANAGER_SCHEDULED_ROTATION_SUCCESS_CHECK",
            description="Secrets Manager secrets should have rotation configured",
        )

    def _create_incident_response_lambda(self, waf_ip_set: wafv2.CfnIPSet) -> None:
        """Create Lambda for automated incident response."""
        lambda_code = """import boto3
import json
import os
from datetime import datetime

wafv2 = boto3.client('wafv2')
sns = boto3.client('sns')

def handler(event, context):
    \"\"\"Automated incident response for GuardDuty findings.\"\"\"
    detail = event.get('detail', {})
    finding_type = detail.get('type', '')
    severity = detail.get('severity', 0)

    incident = {
        'timestamp': datetime.utcnow().isoformat(),
        'finding_type': finding_type,
        'severity': severity,
        'account_id': detail.get('accountId'),
        'region': detail.get('region'),
        'resource': detail.get('resource', {}),
    }

    service = detail.get('service', {})
    action = service.get('action', {})

    remote_ip = None
    if 'networkConnectionAction' in action:
        conn = action['networkConnectionAction']
        remote_ip = conn.get('remoteIpDetails', {}).get('ipAddressV4')
        incident['connection_direction'] = conn.get('connectionDirection')
        incident['protocol'] = conn.get('protocol')
    elif 'portProbeAction' in action:
        probes = action['portProbeAction'].get('portProbeDetails', [])
        if probes:
            remote_ip = probes[0].get('remoteIpDetails', {}).get('ipAddressV4')
            incident['probed_ports'] = [p.get('localPortDetails', {}).get('port') for p in probes]
    elif 'awsApiCallAction' in action:
        api_call = action['awsApiCallAction']
        remote_ip = api_call.get('remoteIpDetails', {}).get('ipAddressV4')
        incident['api_call'] = api_call.get('api')
        incident['service_name'] = api_call.get('serviceName')

    incident['attacker_ip'] = remote_ip

    threat_types = ['UnauthorizedAccess', 'Recon', 'Trojan', 'CryptoCurrency', 'Backdoor']
    should_block = any(t in finding_type for t in threat_types) and severity >= 4

    response_actions = []

    if should_block and remote_ip:
        try:
            ip_set_name = os.environ['IP_SET_NAME']
            ip_set_id = os.environ['IP_SET_ID']
            ip_set_scope = os.environ['IP_SET_SCOPE']

            response = wafv2.get_ip_set(Name=ip_set_name, Scope=ip_set_scope, Id=ip_set_id)
            addresses = response['IPSet']['Addresses']
            lock_token = response['LockToken']

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
                response_actions.append(f"Blocked IP {remote_ip} in WAF")
            else:
                response_actions.append(f"IP {remote_ip} already blocked")
        except Exception as e:
            response_actions.append(f"Failed to block IP: {str(e)}")

    incident['response_actions'] = response_actions

    alert_topic = os.environ.get('SECURITY_ALERTS_TOPIC')
    if alert_topic:
        severity_label = 'CRITICAL' if severity >= 7 else 'HIGH' if severity >= 4 else 'MEDIUM'

        message = f\"\"\"Security Incident Detected - {severity_label}
Finding: {finding_type}
Severity: {severity}/10
Time: {incident['timestamp']}
Attacker IP: {remote_ip or 'Unknown'}
Account: {incident['account_id']}
Region: {incident['region']}
Response Actions: {response_actions}
\"\"\"

        sns.publish(
            TopicArn=alert_topic,
            Subject=f"[{severity_label}] GuardDuty: {finding_type}",
            Message=message,
        )

    print(json.dumps(incident, default=str))

    return {'statusCode': 200, 'body': json.dumps(incident, default=str)}
"""

        incident_response_lambda = lambda_.Function(
            self,
            "IncidentResponseLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(lambda_code),
            environment={
                "IP_SET_NAME": waf_ip_set.name or "blocked-ips",
                "IP_SET_ID": waf_ip_set.attr_id,
                "IP_SET_SCOPE": "REGIONAL",
                "SECURITY_ALERTS_TOPIC": self.security_alerts_topic.topic_arn,
            },
            timeout=Duration.seconds(60),
            description="Automated incident response for GuardDuty findings",
        )

        # Grant permissions
        incident_response_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["wafv2:GetIPSet", "wafv2:UpdateIPSet"],
                resources=[waf_ip_set.attr_arn],
            )
        )

        self.security_alerts_topic.grant_publish(incident_response_lambda)

        # EventBridge rule for GuardDuty findings
        guardduty_rule = events.Rule(
            self,
            "GuardDutyRule",
            event_pattern=events.EventPattern(
                source=["aws.guardduty"],
                detail_type=["GuardDuty Finding"],
                detail={"severity": [{"numeric": [">=", 4]}]},
            ),
        )
        guardduty_rule.add_target(targets.LambdaFunction(incident_response_lambda))

        # EventBridge rule for Security Hub findings
        security_hub_rule = events.Rule(
            self,
            "SecurityHubRule",
            event_pattern=events.EventPattern(
                source=["aws.securityhub"],
                detail_type=["Security Hub Findings - Imported"],
                detail={
                    "findings": {
                        "Severity": {"Label": ["CRITICAL", "HIGH"]},
                    }
                },
            ),
        )
        security_hub_rule.add_target(
            targets.SnsTopic(
                self.security_alerts_topic,
                message=events.RuleTargetInput.from_text(
                    "Security Hub Critical/High Finding detected. Check Security Hub console."
                ),
            )
        )

    def _create_security_dashboard(
        self,
        waf_web_acl: wafv2.CfnWebACL | None,
    ) -> None:
        """Create CloudWatch dashboard for security metrics."""
        dashboard = cloudwatch.Dashboard(
            self,
            "SecurityDashboard",
            dashboard_name="SecureApi-Security",
        )

        # Row 1: Authentication & Access Control
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# 🔐 Authentication & Access Control",
                width=24,
                height=1,
            ),
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Failed Authentication Attempts",
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="FailedAuthAttempts",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                ],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="CSRF Failures",
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="CSRFFailures",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                ],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Access Denied (IDOR)",
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="AccessDenied",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                ],
                width=8,
                height=6,
            ),
        )

        # Row 2: Rate Limiting & WAF
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# 🛡️ Rate Limiting & WAF",
                width=24,
                height=1,
            ),
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Rate Limit Hits",
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Security",
                        metric_name="RateLimitHits",
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                ],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="WAF Blocked Requests",
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
                    ),
                ],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="WAF Allowed vs Blocked",
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
                width=8,
                height=6,
            ),
        )

        # Row 3: Application Health
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# 📊 Application Health",
                width=24,
                height=1,
            ),
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Error Rate by Service",
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
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="API Latency (p95)",
                left=[
                    cloudwatch.Metric(
                        namespace="SecureApi/Logs",
                        metric_name="ApiSlowOperations",
                        statistic="p95",
                        period=Duration.minutes(5),
                    ),
                ],
                width=8,
                height=6,
            ),
            cloudwatch.GraphWidget(
                title="Critical Errors",
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
                width=8,
                height=6,
            ),
        )

        # Row 4: GuardDuty & Compliance
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown="# 🔍 Threat Detection & Compliance",
                width=24,
                height=1,
            ),
        )

        dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="GuardDuty Findings (24h)",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/GuardDuty",
                        metric_name="FindingsCount",
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
                width=6,
                height=4,
            ),
            cloudwatch.SingleValueWidget(
                title="Security Hub Findings",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SecurityHub",
                        metric_name="FindingsCount",
                        statistic="Sum",
                        period=Duration.hours(24),
                    ),
                ],
                width=6,
                height=4,
            ),
            cloudwatch.AlarmStatusWidget(
                title="Security Alarms Status",
                alarms=[],  # Will be populated by alarm references
                width=12,
                height=4,
            ),
        )
