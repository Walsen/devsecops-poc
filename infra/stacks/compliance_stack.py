"""
Compliance Stack — AWS Config recorder, delivery channel, and managed rules.

Standalone stack. No cross-stack dependencies.
Delivery channel is created first, then recorder depends on it,
then rules depend on the recorder.
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_config as config
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ComplianceStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        config_role = iam.Role(
            self, "ConfigRole",
            assumed_by=iam.ServicePrincipal("config.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWS_ConfigRole"),
            ],
        )

        config_bucket = s3.Bucket(
            self, "ConfigBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Delivery channel FIRST (recorder needs it to start)
        delivery_channel = config.CfnDeliveryChannel(
            self, "ConfigDeliveryChannel",
            s3_bucket_name=config_bucket.bucket_name,
        )

        # Recorder depends on delivery channel
        recorder = config.CfnConfigurationRecorder(
            self, "ConfigRecorder",
            role_arn=config_role.role_arn,
            recording_group=config.CfnConfigurationRecorder.RecordingGroupProperty(
                all_supported=True,
                include_global_resource_types=True,
            ),
        )
        recorder.add_dependency(delivery_channel)

        # Config rules depend on recorder
        rules = [
            ("RdsEncryptionEnabled", "RDS_STORAGE_ENCRYPTED",
             "RDS instances should have encryption enabled"),
            ("S3BucketEncryption", "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED",
             "S3 buckets should have server-side encryption enabled"),
            ("CloudTrailEnabled", "CLOUD_TRAIL_ENABLED",
             "CloudTrail should be enabled"),
            ("IamPasswordPolicy", "IAM_PASSWORD_POLICY",
             "IAM password policy should meet requirements"),
            ("VpcFlowLogsEnabled", "VPC_FLOW_LOGS_ENABLED",
             "VPC flow logs should be enabled"),
        ]

        for name, identifier, description in rules:
            rule = config.ManagedRule(
                self, name, identifier=identifier, description=description,
            )
            rule.node.add_dependency(recorder)
