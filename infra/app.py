#!/usr/bin/env python3
import os
import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.data_stack import DataStack
from stacks.auth_stack import AuthStack
from stacks.compute_stack import ComputeStack
from stacks.observability_stack import ObservabilityStack
from stacks.compliance_stack import ComplianceStack
from stacks.threat_detection_stack import ThreatDetectionStack
from stacks.edge_stack import EdgeStack
from stacks.github_oidc_stack import GitHubOIDCStack
from stacks.registry_stack import RegistryStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

# GitHub OIDC bootstrap (deploy separately with context vars)
github_org = app.node.try_get_context("github_org")
github_repo = app.node.try_get_context("github_repo")
if github_org and github_repo:
    GitHubOIDCStack(
        app, "GitHubOIDCStack", env=env,
        github_org=github_org, github_repo=github_repo,
    )

# --- Container registry (deployed before builds) ---

registry_stack = RegistryStack(app, "RegistryStack", env=env)

# --- Core infrastructure (deployed together) ---

network_stack = NetworkStack(app, "NetworkStack", env=env)

security_stack = SecurityStack(
    app, "SecurityStack", env=env,
    vpc=network_stack.vpc,
)

auth_stack = AuthStack(app, "AuthStack", env=env)

data_stack = DataStack(
    app, "DataStack", env=env,
    vpc=network_stack.vpc,
    kms_key=security_stack.kms_key,
    service_security_group=network_stack.service_security_group,
)

compute_stack = ComputeStack(
    app, "ComputeStack", env=env,
    vpc=network_stack.vpc,
    kms_key=security_stack.kms_key,
    db_secret=data_stack.db_secret,
    event_stream=data_stack.event_stream,
    service_security_group=network_stack.service_security_group,
    alb_security_group=network_stack.alb_security_group,
    user_pool=auth_stack.user_pool,
    user_pool_client=auth_stack.user_pool_client,
)

# --- Monitoring (each stack is independent, can fail without affecting others) ---

observability_stack = ObservabilityStack(
    app, "ObservabilityStack", env=env,
    api_log_group=compute_stack.api_log_group,
    worker_log_group=compute_stack.worker_log_group,
    scheduler_log_group=compute_stack.scheduler_log_group,
)

compliance_stack = ComplianceStack(app, "ComplianceStack", env=env)

threat_detection_stack = ThreatDetectionStack(
    app, "ThreatDetectionStack", env=env,
    waf_ip_set=security_stack.waf_ip_set,
)

# --- Edge (deployed independently, CloudFront takes 15-30 min) ---

edge_stack = EdgeStack(
    app, "EdgeStack",
    env=cdk.Environment(account=env.account, region="us-east-1"),
)
edge_stack.add_dependency(compute_stack)

app.synth()
