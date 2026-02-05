#!/usr/bin/env python3
import os
import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack
from stacks.auth_stack import AuthStack
from stacks.compute_stack import ComputeStack
from stacks.monitoring_stack import MonitoringStack
from stacks.edge_stack import EdgeStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

# Network foundation
network_stack = NetworkStack(app, "NetworkStack", env=env)

# Security components (KMS, Secrets Manager, WAF IP Set)
security_stack = SecurityStack(
    app, "SecurityStack",
    env=env,
    vpc=network_stack.vpc,
)

# Data layer (RDS, S3, Kinesis)
data_stack = DataStack(
    app, "DataStack",
    env=env,
    vpc=network_stack.vpc,
    kms_key=security_stack.kms_key,
    service_security_group=network_stack.service_security_group,
)

# Authentication (Cognito User Pool)
auth_stack = AuthStack(app, "AuthStack", env=env)

# Compute layer (ECS Fargate, ALB, Cloud Map)
compute_stack = ComputeStack(
    app, "ComputeStack",
    env=env,
    vpc=network_stack.vpc,
    kms_key=security_stack.kms_key,
    db_secret=data_stack.db_secret,
    event_stream=data_stack.event_stream,
    service_security_group=network_stack.service_security_group,
    alb_security_group=network_stack.alb_security_group,
    user_pool=auth_stack.user_pool,
    user_pool_client=auth_stack.user_pool_client,
)

# Edge layer (CloudFront, WAF) - must be us-east-1 for CloudFront WAF
edge_stack = EdgeStack(
    app, "EdgeStack",
    env=cdk.Environment(account=env.account, region="us-east-1"),
    alb=compute_stack.alb,
    waf_ip_set=security_stack.waf_ip_set,
)

# Monitoring & automated response
monitoring_stack = MonitoringStack(
    app, "MonitoringStack",
    env=env,
    vpc=network_stack.vpc,
    waf_ip_set=security_stack.waf_ip_set,
)

app.synth()
