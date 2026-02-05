from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_kms as kms,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct


class SecurityStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # KMS key for encryption at rest
        self.kms_key = kms.Key(
            self, "EncryptionKey",
            enable_key_rotation=True,
            alias="secure-api-key",
            description="KMS key for encrypting RDS, S3, and Kinesis data",
            removal_policy=RemovalPolicy.RETAIN,
        )

        # WAF IP Set for blocking malicious IPs (updated by Lambda)
        self.waf_ip_set = wafv2.CfnIPSet(
            self, "BlockedIpSet",
            name="blocked-ips",
            scope="REGIONAL",
            ip_address_version="IPV4",
            addresses=[],  # Populated dynamically by GuardDuty response Lambda
        )

        # Outputs
        CfnOutput(
            self, "KmsKeyArn",
            value=self.kms_key.key_arn,
            export_name="SecureApiKmsKeyArn",
        )

        CfnOutput(
            self, "WafIpSetArn",
            value=self.waf_ip_set.attr_arn,
            export_name="SecureApiWafIpSetArn",
        )
