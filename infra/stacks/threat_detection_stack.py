"""
Threat Detection Stack — GuardDuty, SecurityHub, CloudTrail, incident response.

Depends on: SecurityStack (WAF IP set for auto-blocking)
Account-level services that only need to be enabled once.
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudtrail as cloudtrail
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


class ThreatDetectionStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        waf_ip_set: wafv2.CfnIPSet,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.security_alerts_topic = sns.Topic(
            self,
            "SecurityAlertsTopic",
            display_name="Threat Detection Alerts",
        )

        # GuardDuty
        guardduty.CfnDetector(
            self,
            "GuardDutyDetector",
            enable=True,
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        # Security Hub
        securityhub.CfnHub(self, "SecurityHub")

        # CloudTrail
        cloudtrail.Trail(
            self,
            "AuditTrail",
            send_to_cloud_watch_logs=True,
            cloud_watch_logs_retention=logs.RetentionDays.ONE_WEEK,
            include_global_service_events=True,
            is_multi_region_trail=False,
        )

        # Incident response Lambda
        self._create_incident_response(waf_ip_set)

    def _create_incident_response(self, waf_ip_set: wafv2.CfnIPSet) -> None:
        lambda_code = """import boto3
import json
import os
from datetime import datetime

wafv2_client = boto3.client('wafv2')
sns_client = boto3.client('sns')

def handler(event, context):
    detail = event.get('detail', {})
    finding_type = detail.get('type', '')
    severity = detail.get('severity', 0)

    incident = {
        'timestamp': datetime.utcnow().isoformat(),
        'finding_type': finding_type,
        'severity': severity,
        'account_id': detail.get('accountId'),
        'region': detail.get('region'),
    }

    # Extract attacker IP from various action types
    service = detail.get('service', {})
    action = service.get('action', {})
    remote_ip = None

    if 'networkConnectionAction' in action:
        remote_ip = action['networkConnectionAction'].get('remoteIpDetails', {}).get('ipAddressV4')
    elif 'portProbeAction' in action:
        probes = action['portProbeAction'].get('portProbeDetails', [])
        if probes:
            remote_ip = probes[0].get('remoteIpDetails', {}).get('ipAddressV4')
    elif 'awsApiCallAction' in action:
        remote_ip = action['awsApiCallAction'].get('remoteIpDetails', {}).get('ipAddressV4')

    incident['attacker_ip'] = remote_ip

    # Auto-block for high-severity threats
    threat_types = ['UnauthorizedAccess', 'Recon', 'Trojan', 'CryptoCurrency', 'Backdoor']
    should_block = any(t in finding_type for t in threat_types) and severity >= 4
    response_actions = []

    if should_block and remote_ip:
        try:
            ip_set_name = os.environ['IP_SET_NAME']
            ip_set_id = os.environ['IP_SET_ID']
            ip_set_scope = os.environ['IP_SET_SCOPE']

            resp = wafv2_client.get_ip_set(Name=ip_set_name, Scope=ip_set_scope, Id=ip_set_id)
            addresses = resp['IPSet']['Addresses']
            lock_token = resp['LockToken']

            new_ip = f"{remote_ip}/32"
            if new_ip not in addresses:
                addresses.append(new_ip)
                wafv2_client.update_ip_set(
                    Name=ip_set_name, Scope=ip_set_scope, Id=ip_set_id,
                    Addresses=addresses, LockToken=lock_token,
                )
                response_actions.append(f"Blocked IP {remote_ip} in WAF")
            else:
                response_actions.append(f"IP {remote_ip} already blocked")
        except Exception as e:
            response_actions.append(f"Failed to block IP: {str(e)}")

    incident['response_actions'] = response_actions

    # Send alert
    alert_topic = os.environ.get('SECURITY_ALERTS_TOPIC')
    if alert_topic:
        severity_label = 'CRITICAL' if severity >= 7 else 'HIGH' if severity >= 4 else 'MEDIUM'
        sns_client.publish(
            TopicArn=alert_topic,
            Subject=f"[{severity_label}] GuardDuty: {finding_type}",
            Message=json.dumps(incident, default=str, indent=2),
        )

    print(json.dumps(incident, default=str))
    return {'statusCode': 200, 'body': json.dumps(incident, default=str)}
"""

        fn = lambda_.Function(
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
            description="Auto-block malicious IPs from GuardDuty findings",
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["wafv2:GetIPSet", "wafv2:UpdateIPSet"],
                resources=[waf_ip_set.attr_arn],
            )
        )
        self.security_alerts_topic.grant_publish(fn)

        # GuardDuty findings -> Lambda
        guardduty_rule = events.Rule(
            self,
            "GuardDutyRule",
            event_pattern=events.EventPattern(
                source=["aws.guardduty"],
                detail_type=["GuardDuty Finding"],
                detail={"severity": [{"numeric": [">=", 4]}]},
            ),
        )
        guardduty_rule.add_target(targets.LambdaFunction(fn))

        # Security Hub findings -> SNS
        events.Rule(
            self,
            "SecurityHubRule",
            event_pattern=events.EventPattern(
                source=["aws.securityhub"],
                detail_type=["Security Hub Findings - Imported"],
                detail={"findings": {"Severity": {"Label": ["CRITICAL", "HIGH"]}}},
            ),
        ).add_target(
            targets.SnsTopic(
                self.security_alerts_topic,
                message=events.RuleTargetInput.from_text(
                    "Security Hub Critical/High Finding detected. Check Security Hub console."
                ),
            )
        )
