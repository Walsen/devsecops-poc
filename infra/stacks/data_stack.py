import json

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_kms as kms,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class DataStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        kms_key: kms.Key,
        service_security_group: ec2.SecurityGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Database credentials in Secrets Manager
        self.db_secret = secretsmanager.Secret(
            self,
            "DbSecret",
            secret_name="secure-api/db-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": "dbadmin"}),
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        # Security group for RDS
        db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=vpc,
            description="Security group for RDS instance",
            allow_all_outbound=False,
        )
        # Allow ECS services to connect to RDS
        db_security_group.add_ingress_rule(
            service_security_group, ec2.Port.tcp(5432), "From ECS services"
        )

        # RDS PostgreSQL - Dev: Single-AZ, smaller instance
        self.database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15,
            ),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_secret(self.db_secret),
            multi_az=False,  # Dev: Single-AZ
            storage_encrypted=True,
            storage_encryption_key=kms_key,
            deletion_protection=False,  # Dev: Allow deletion
            backup_retention=Duration.days(1),  # Dev: Minimal backups
            removal_policy=RemovalPolicy.DESTROY,  # Dev: Clean up on delete
        )

        # S3 bucket with encryption - Dev: S3-managed encryption, auto-delete
        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,  # Dev: Free S3 encryption
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=False,  # Dev: No versioning
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Kinesis Data Stream - Dev: On-demand mode (pay per use)
        self.event_stream = kinesis.Stream(
            self,
            "EventStream",
            stream_name="secure-api-events",
            encryption=kinesis.StreamEncryption.MANAGED,  # Dev: AWS-managed encryption
            stream_mode=kinesis.StreamMode.ON_DEMAND,  # Dev: Pay per use
            retention_period=Duration.days(1),  # Dev: Minimal retention
        )
