"""
Compliance Stack — AWS Config recorder, delivery channel, and managed rules.

Uses a Custom Resource to create the Config recorder and delivery channel
in the correct order, working around a CloudFormation bug where
AWS::Config::ConfigurationRecorder hangs because it tries to start
recording before a delivery channel exists.
"""

from aws_cdk import CustomResource, Duration, RemovalPolicy, Stack
from aws_cdk import aws_config as config
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from constructs import Construct

CONFIG_SETUP_CODE = """\
import boto3
import cfnresponse
import json

def handler(event, context):
    try:
        props = event["ResourceProperties"]
        request_type = event["RequestType"]
        recorder_name = props["RecorderName"]
        role_arn = props["RoleArn"]
        bucket_name = props["BucketName"]

        client = boto3.client("config")

        if request_type in ("Create", "Update"):
            # 1. Create recorder (without starting)
            client.put_configuration_recorder(
                ConfigurationRecorder={
                    "name": recorder_name,
                    "roleARN": role_arn,
                    "recordingGroup": {
                        "allSupported": True,
                        "includeGlobalResourceTypes": True,
                    },
                }
            )
            # 2. Create delivery channel
            client.put_delivery_channel(
                DeliveryChannel={
                    "name": recorder_name,
                    "s3BucketName": bucket_name,
                }
            )
            # 3. Now start recording
            client.start_configuration_recorder(
                ConfigurationRecorderName=recorder_name
            )
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                "RecorderName": recorder_name,
            })

        elif request_type == "Delete":
            try:
                client.stop_configuration_recorder(
                    ConfigurationRecorderName=recorder_name
                )
            except Exception:
                pass
            try:
                client.delete_delivery_channel(
                    DeliveryChannelName=recorder_name
                )
            except Exception:
                pass
            try:
                client.delete_configuration_recorder(
                    ConfigurationRecorderName=recorder_name
                )
            except Exception:
                pass
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    except Exception as e:
        print(f"Error: {e}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})
"""


class ComplianceStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # S3 bucket for Config delivery
        config_bucket = s3.Bucket(
            self,
            "ConfigBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Bucket policy for Config service
        config_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("config.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{config_bucket.bucket_arn}/AWSLogs/*"],
                conditions={
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control",
                    },
                },
            )
        )
        config_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("config.amazonaws.com")],
                actions=["s3:GetBucketAcl"],
                resources=[config_bucket.bucket_arn],
            )
        )

        # IAM role for Config recorder
        config_role = iam.Role(
            self,
            "ConfigRole",
            assumed_by=iam.ServicePrincipal("config.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWS_ConfigRole",
                ),
            ],
        )
        config_bucket.grant_write(config_role)

        # Lambda to set up Config (recorder + delivery channel + start)
        setup_fn = _lambda.Function(
            self,
            "ConfigSetupFn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_inline(CONFIG_SETUP_CODE),
            timeout=Duration.seconds(60),
        )

        # Grant Lambda permissions to manage Config
        setup_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "config:PutConfigurationRecorder",
                    "config:PutDeliveryChannel",
                    "config:StartConfigurationRecorder",
                    "config:StopConfigurationRecorder",
                    "config:DeleteConfigurationRecorder",
                    "config:DeleteDeliveryChannel",
                ],
                resources=["*"],
            )
        )
        setup_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[config_role.role_arn],
            )
        )

        recorder_name = "compliance-recorder"

        # Custom Resource that creates recorder + channel in correct order
        config_setup = CustomResource(
            self,
            "ConfigSetup",
            service_token=setup_fn.function_arn,
            properties={
                "RecorderName": recorder_name,
                "RoleArn": config_role.role_arn,
                "BucketName": config_bucket.bucket_name,
            },
        )
        config_setup.node.add_dependency(config_role)
        config_setup.node.add_dependency(config_bucket)

        # Config rules depend on the custom resource
        rules = [
            (
                "RdsEncryptionEnabled",
                "RDS_STORAGE_ENCRYPTED",
                "RDS instances should have encryption enabled",
            ),
            (
                "S3BucketEncryption",
                "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED",
                "S3 buckets should have server-side encryption enabled",
            ),
            (
                "CloudTrailEnabled",
                "CLOUD_TRAIL_ENABLED",
                "CloudTrail should be enabled",
            ),
            (
                "IamPasswordPolicy",
                "IAM_PASSWORD_POLICY",
                "IAM password policy should meet requirements",
            ),
            (
                "VpcFlowLogsEnabled",
                "VPC_FLOW_LOGS_ENABLED",
                "VPC flow logs should be enabled",
            ),
        ]

        for name, identifier, description in rules:
            rule = config.ManagedRule(
                self,
                name,
                identifier=identifier,
                description=description,
            )
            rule.node.add_dependency(config_setup)
