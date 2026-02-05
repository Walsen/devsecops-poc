# Serverless Infrastructure (infra-fs)

Fully serverless architecture for Omnichannel Publisher using Lambda, DynamoDB, and API Gateway.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CloudFront                               │
│                             │                                    │
│              ┌──────────────┴──────────────┐                    │
│              ▼                              ▼                    │
│         Amplify                        API Gateway               │
│        (Frontend)                          │                     │
│                                            ▼                     │
│                                    Lambda (API)                  │
│                                       │    │                     │
│                          ┌────────────┘    └────────────┐       │
│                          ▼                              ▼       │
│                     DynamoDB                        Kinesis     │
│                          ▲                              │       │
│                          │                              ▼       │
│              EventBridge Scheduler              Lambda (Worker) │
│                          │                              │       │
│                          ▼                              ▼       │
│                  Lambda (Scheduler)            Social Media APIs │
└─────────────────────────────────────────────────────────────────┘
```

## Cost Comparison vs Containers

| Traffic Level | Containers (ECS) | Serverless |
|---------------|------------------|------------|
| Dev/Low       | ~$180-200/mo     | ~$5-15/mo  |
| Medium        | ~$200-250/mo     | ~$20-40/mo |
| High          | ~$250-350/mo     | ~$50-80/mo |

## Stacks

| Stack | Resources |
|-------|-----------|
| DataStack | DynamoDB (single-table), Kinesis, S3 |
| AuthStack | Cognito User Pool |
| ApiStack | Lambda + API Gateway |
| WorkerStack | Lambda + Kinesis trigger |
| SchedulerStack | EventBridge + Lambda |
| MonitoringStack | CloudWatch dashboards/alarms |
| SecurityStack | WAF, GuardDuty, Security Hub |
| FrontendStack | Amplify Hosting |

## DynamoDB Single-Table Design

```
PK                    SK                      GSI1PK          GSI1SK
─────────────────────────────────────────────────────────────────────
MSG#<id>              METADATA                USER#<user-id>  MSG#<id>
MSG#<id>              CHANNEL#facebook        STATUS#scheduled <scheduled_at>
MSG#<id>              CHANNEL#linkedin        
CERT#<id>             METADATA                USER#<user-id>  CERT#<id>
CERT#<id>             CHANNEL#facebook        
USER#<id>             PROFILE                 
```

## Deployment

```bash
# Install dependencies
cd infra-fs
uv sync

# Deploy all stacks
uv run cdk deploy --all

# Deploy specific stack
uv run cdk deploy OmnichannelApiStack
```

## CI/CD Selection

Set `INFRA_TYPE` environment variable or use workflow dispatch:

```yaml
# containers (default) - uses infra/
# serverless - uses infra-fs/
```
