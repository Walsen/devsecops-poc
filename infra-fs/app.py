#!/usr/bin/env python3
"""CDK App for Serverless Omnichannel Publisher infrastructure."""

import aws_cdk as cdk

from stacks import (
    ApiStack,
    AuthStack,
    DataStack,
    FrontendStack,
    MonitoringStack,
    SchedulerStack,
    SecurityStack,
    WorkerStack,
)

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

# Data layer - DynamoDB, Kinesis, S3
data_stack = DataStack(app, "OmnichannelDataStack", env=env)

# Auth - Cognito
auth_stack = AuthStack(app, "OmnichannelAuthStack", env=env)

# API - Lambda + API Gateway
api_stack = ApiStack(
    app,
    "OmnichannelApiStack",
    main_table=data_stack.main_table,
    kinesis_stream=data_stack.kinesis_stream,
    media_bucket=data_stack.media_bucket,
    user_pool=auth_stack.user_pool,
    user_pool_client_id=auth_stack.user_pool_client_id,
    env=env,
)
api_stack.add_dependency(data_stack)
api_stack.add_dependency(auth_stack)

# Worker - Lambda with Kinesis trigger
worker_stack = WorkerStack(
    app,
    "OmnichannelWorkerStack",
    main_table=data_stack.main_table,
    kinesis_stream=data_stack.kinesis_stream,
    env=env,
)
worker_stack.add_dependency(data_stack)

# Scheduler - EventBridge + Lambda
scheduler_stack = SchedulerStack(
    app,
    "OmnichannelSchedulerStack",
    main_table=data_stack.main_table,
    kinesis_stream=data_stack.kinesis_stream,
    env=env,
)
scheduler_stack.add_dependency(data_stack)

# Monitoring - CloudWatch dashboards and alarms
monitoring_stack = MonitoringStack(
    app,
    "OmnichannelMonitoringStack",
    api_function=api_stack.api_function,
    worker_function=worker_stack.worker_function,
    scheduler_function=scheduler_stack.scheduler_function,
    env=env,
)
monitoring_stack.add_dependency(api_stack)
monitoring_stack.add_dependency(worker_stack)
monitoring_stack.add_dependency(scheduler_stack)

# Security - WAF, GuardDuty, Security Hub
security_stack = SecurityStack(
    app,
    "OmnichannelSecurityStack",
    api_gateway_arn=f"arn:aws:apigateway:{env.region}::/restapis/{api_stack.api.rest_api_id}/stages/v1",
    env=env,
)
security_stack.add_dependency(api_stack)

# Frontend - Amplify
frontend_stack = FrontendStack(
    app,
    "OmnichannelFrontendStack",
    api_url=api_stack.api_url,
    user_pool_id=auth_stack.user_pool.user_pool_id,
    user_pool_client_id=auth_stack.user_pool_client_id,
    env=env,
)
frontend_stack.add_dependency(api_stack)
frontend_stack.add_dependency(auth_stack)

app.synth()
