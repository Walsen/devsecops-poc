from aws_cdk import (
    Stack,
    Duration,
    aws_ec2 as ec2,
    aws_guardduty as guardduty,
    aws_securityhub as securityhub,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_wafv2 as wafv2,
    aws_cloudtrail as cloudtrail,
    aws_logs as logs,
)
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        waf_ip_set: wafv2.CfnIPSet,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # GuardDuty Detector
        guardduty.CfnDetector(
            self, "GuardDutyDetector",
            enable=True,
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        # Security Hub
        securityhub.CfnHub(self, "SecurityHub")

        # CloudTrail - Dev: Single region only
        cloudtrail.Trail(
            self, "AuditTrail",
            send_to_cloud_watch_logs=True,
            cloud_watch_logs_retention=logs.RetentionDays.ONE_WEEK,  # Dev: Short retention
            include_global_service_events=True,
            is_multi_region_trail=False,  # Dev: Single region
        )

        # Lambda to auto-block malicious IPs from GuardDuty findings
        block_ip_lambda = lambda_.Function(
            self, "BlockIpLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3
import os

wafv2 = boto3.client('wafv2')

def handler(event, context):
    detail = event.get('detail', {})
    finding_type = detail.get('type', '')
    
    # Only process network-related findings
    if not any(t in finding_type for t in ['UnauthorizedAccess', 'Recon', 'Trojan']):
        return {'statusCode': 200, 'body': 'Skipped - not a network threat'}
    
    # Extract attacker IP
    service = detail.get('service', {})
    action = service.get('action', {})
    
    remote_ip = None
    if 'networkConnectionAction' in action:
        remote_ip = action['networkConnectionAction'].get('remoteIpDetails', {}).get('ipAddressV4')
    elif 'portProbeAction' in action:
        remote_ip = action['portProbeAction'].get('portProbeDetails', [{}])[0].get('remoteIpDetails', {}).get('ipAddressV4')
    
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
"""),
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
            self, "GuardDutyRule",
            event_pattern=events.EventPattern(
                source=["aws.guardduty"],
                detail_type=["GuardDuty Finding"],
                detail={"severity": [{"numeric": [">=", 4]}]},  # Medium+
            ),
        )

        guard_duty_rule.add_target(targets.LambdaFunction(block_ip_lambda))
