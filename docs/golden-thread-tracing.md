# Golden Thread: Distributed Security Tracing Exercise

This guide walks through a hands-on attack simulation exercise that demonstrates
end-to-end request tracing across all infrastructure layers using a single
correlation ID — the "Golden Thread."

## Overview

The Golden Thread is the correlation ID (`X-Request-ID`) that links logs across:

1. **Edge Layer** — WAF logs (CloudFront + ALB)
2. **Application Layer** — API structured logs (structlog JSON)
3. **Async Layer** — Kinesis event → Worker logs
4. **Database Layer** — PostgreSQL audit logs (pgaudit)

All queryable from CloudWatch Logs Insights with a single filter.

## Prerequisites

- AWS CLI configured (`aws sso login --profile awscbba`)
- `curl` or `httpie` installed
- CloudFront domain: `d2rv56b0ccriwq.cloudfront.net`
- ALB domain: `Comput-Alb16-j1fq7hseoZQw-945843054.us-east-1.elb.amazonaws.com`
- ECS services running (`just aws-up`)

## Exercise 1: Trace a Legitimate Request

### Step 1 — Send a request with a known correlation ID

```bash
# Pick a memorable trace ID
TRACE_ID="golden-thread-test-$(date +%s)"

# Hit the health endpoint through CloudFront
curl -v \
  -H "X-Request-ID: $TRACE_ID" \
  "https://d2rv56b0ccriwq.cloudfront.net/health"
```

Verify the response includes your trace ID:

```
< X-Request-ID: golden-thread-test-1739...
< X-Correlation-ID: golden-thread-test-1739...
```

### Step 2 — Query CloudWatch Logs Insights

Open CloudWatch Logs Insights in the AWS Console, or use the CLI:

```bash
# Query API logs for the trace ID
aws logs start-query \
  --profile awscbba \
  --log-group-names "/ecs/secure-api/api" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, service, event, correlation_id, method, path, status_code
    | filter correlation_id = '$TRACE_ID'
    | sort @timestamp asc
  "
```

Then retrieve results:

```bash
aws logs get-query-results \
  --profile awscbba \
  --query-id <QUERY_ID_FROM_ABOVE>
```

Expected output — two log entries for the single request:

| timestamp | event | method | path | status_code |
|-----------|-------|--------|------|-------------|
| T+0ms | Request started | GET | /health | — |
| T+1ms | Request completed | GET | /health | 200 |

### Step 3 — Query WAF logs

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "aws-waf-logs-cloudfront" "aws-waf-logs-alb" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, httpRequest.uri, httpRequest.clientIp, action,
           terminatingRuleId, httpRequest.requestId
    | sort @timestamp desc
    | limit 20
  "
```

> Note: WAF logs don't include custom `X-Request-ID` headers by default,
> but they include the AWS-generated `requestId` and the full URI + IP,
> which can be correlated by timestamp and client IP with the API logs.

## Exercise 2: Simulate a SQL Injection Attack

This exercise demonstrates how WAF detects and blocks SQL injection attempts,
and how you can trace the blocked request across layers.

### Step 1 — Send a SQL injection payload

```bash
TRACE_ID="sqli-attack-$(date +%s)"

# Attempt SQL injection via query parameter
curl -v \
  -H "X-Request-ID: $TRACE_ID" \
  "https://d2rv56b0ccriwq.cloudfront.net/api/v1/certifications/types/?q=' OR 1=1--"
```

Expected: WAF blocks the request with HTTP 403.

### Step 2 — Try through the ALB directly (bypassing CloudFront)

```bash
# Same attack directly to ALB (tests the REGIONAL WAF)
curl -v \
  -H "X-Request-ID: $TRACE_ID-alb" \
  "http://Comput-Alb16-j1fq7hseoZQw-945843054.us-east-1.elb.amazonaws.com/api/v1/certifications/types/?q=' OR 1=1--"
```

Expected: Also blocked by the ALB WAF (same SQLi rule set).

### Step 3 — Check WAF logs for the block

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "aws-waf-logs-cloudfront" "aws-waf-logs-alb" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId,
           httpRequest.uri, httpRequest.clientIp,
           httpRequest.country
    | filter action = 'BLOCK'
    | sort @timestamp desc
    | limit 10
  "
```

Expected: You'll see entries with `action=BLOCK` and
`terminatingRuleId=AWSManagedRulesSQLiRuleSet`.

### Step 4 — Verify the request never reached the API

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "/ecs/secure-api/api" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, event, correlation_id, path
    | filter correlation_id = '$TRACE_ID'
    | sort @timestamp asc
  "
```

Expected: **Zero results** — the request was blocked at the WAF layer
before reaching the application.

## Exercise 3: Trace a Request Through All Layers (API → Kinesis → Worker → DB)

This requires authentication. Use a valid JWT token from Cognito.

### Step 1 — Get a JWT token

```bash
# Option A: Use the Cognito hosted UI to sign in and grab the token
# from the browser's network tab after redirect

# Option B: Use AWS CLI (if you have a test user)
TOKEN=$(aws cognito-idp initiate-auth \
  --profile awscbba \
  --client-id <COGNITO_CLIENT_ID> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<test_user>,PASSWORD=<test_password> \
  --query 'AuthenticationResult.AccessToken' \
  --output text)
```

### Step 2 — Schedule a message (triggers the full pipeline)

```bash
TRACE_ID="full-trace-$(date +%s)"

curl -v \
  -H "X-Request-ID: $TRACE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": {"text": "Golden thread tracing test"},
    "channels": ["email"],
    "scheduled_at": "2026-02-12T23:00:00Z"
  }' \
  "https://d2rv56b0ccriwq.cloudfront.net/api/v1/messages/"
```

### Step 3 — Trace across ALL log groups

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names \
    "aws-waf-logs-cloudfront" \
    "aws-waf-logs-alb" \
    "/ecs/secure-api/api" \
    "/ecs/secure-api/worker" \
    "/ecs/secure-api/scheduler" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, @logStream, @message
    | filter @message like '$TRACE_ID'
    | sort @timestamp asc
    | limit 50
  "
```

Expected timeline:

| Time | Log Group | Event |
|------|-----------|-------|
| T+0ms | aws-waf-logs-cloudfront | WAF evaluates request (ALLOW) |
| T+5ms | aws-waf-logs-alb | ALB WAF evaluates request (ALLOW) |
| T+10ms | /ecs/secure-api/api | Request started |
| T+15ms | /ecs/secure-api/api | Event published to Kinesis |
| T+20ms | /ecs/secure-api/api | Request completed (201) |
| T+500ms | /ecs/secure-api/worker | Processing event (same correlation_id) |
| T+600ms | /ecs/secure-api/worker | Channel delivery attempted |

### Step 4 — Check PostgreSQL audit logs for the SQL trace comment

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "/aws/rds/instance/datastack-database/postgresql" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, @message
    | filter @message like '$TRACE_ID'
    | sort @timestamp asc
    | limit 20
  "
```

Expected: SQL statements prefixed with `/* correlation_id=full-trace-... */`:

```
/* correlation_id=full-trace-1739... */ INSERT INTO messages (id, content_text, ...) VALUES (...)
```

## Exercise 4: Brute Force Detection

### Step 1 — Send rapid unauthenticated requests

```bash
# Send 60 requests in quick succession (triggers rate limiting)
for i in $(seq 1 60); do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "X-Request-ID: brute-force-$i" \
    "https://d2rv56b0ccriwq.cloudfront.net/api/v1/messages/"
done
echo ""
```

Expected: First requests return 401 (unauthorized), then 429 (rate limited).

### Step 2 — Check rate limit metric filter

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "/ecs/secure-api/api" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, event, correlation_id, client_ip
    | filter event = 'Rate limit exceeded'
    | sort @timestamp desc
    | limit 20
  "
```

### Step 3 — Check CloudWatch alarm state

```bash
aws cloudwatch describe-alarms \
  --profile awscbba \
  --alarm-name-prefix "ObservabilityStack" \
  --state-value ALARM \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table
```

## Exercise 5: XSS Attempt Detection

### Step 1 — Send an XSS payload

```bash
TRACE_ID="xss-test-$(date +%s)"

curl -v \
  -H "X-Request-ID: $TRACE_ID" \
  "https://d2rv56b0ccriwq.cloudfront.net/api/v1/certifications/types/?q=<script>alert(1)</script>"
```

Expected: WAF blocks with 403 (AWSManagedRulesCommonRuleSet catches XSS).

### Step 2 — Verify in WAF logs

```bash
aws logs start-query \
  --profile awscbba \
  --log-group-names "aws-waf-logs-cloudfront" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId, httpRequest.uri
    | filter action = 'BLOCK'
    | filter httpRequest.uri like 'script'
    | sort @timestamp desc
  "
```

## Useful CloudWatch Logs Insights Queries

### Trace a single request across all services

```sql
fields @timestamp, service, event, correlation_id, method, path, status_code
| filter correlation_id = "YOUR_TRACE_ID"
| sort @timestamp asc
```

### Find all blocked WAF requests in the last hour

```sql
fields @timestamp, action, terminatingRuleId,
       httpRequest.uri, httpRequest.clientIp
| filter action = "BLOCK"
| stats count() by terminatingRuleId
```

### Error rate by service (last 24h)

```sql
fields service, level
| filter level = "error"
| stats count() by service, bin(1h)
```

### Slow database queries (via pgaudit logs)

```sql
fields @timestamp, @message
| filter @message like "duration"
| filter @message like "ms"
| sort @timestamp desc
| limit 20
```

### Find all requests from a specific IP

```sql
fields @timestamp, event, correlation_id, client_ip, path, status_code
| filter client_ip = "YOUR_IP"
| sort @timestamp desc
| limit 50
```

## Architecture Reference

```
Attacker                                                    CloudWatch Logs
   │                                                              ▲
   │  GET /api?id=' OR 1=1                                       │
   ▼                                                              │
┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  CloudFront  │───▶│   ALB WAF    │───▶│  API Service │────────▶│
│  + WAF       │    │  (REGIONAL)  │    │  (ECS)       │         │
│  (CLOUDFRONT)│    │              │    │              │         │
└──────────────┘    └──────────────┘    └──────┬───────┘         │
       │                   │                   │                  │
       │ aws-waf-logs-     │ aws-waf-logs-     │ /ecs/secure-    │
       │ cloudfront        │ alb               │ api/api         │
       ▼                   ▼                   ▼                  │
   CloudWatch          CloudWatch          CloudWatch             │
                                               │                  │
                                    ┌──────────┴──────────┐      │
                                    ▼                     ▼      │
                              ┌──────────┐         ┌──────────┐  │
                              │ Kinesis  │────────▶│  Worker  │──┘
                              │          │         │  (ECS)   │
                              └──────────┘         └────┬─────┘
                                                        │
                                                        ▼
                                                  ┌──────────┐
                                                  │PostgreSQL │
                                                  │(pgaudit)  │
                                                  └──────────┘
                                                        │
                                                        ▼
                                                   CloudWatch
                                              /aws/rds/.../postgresql

    The "Golden Thread" = correlation_id linking ALL log entries
```

## What Each Layer Captures

| Layer | Log Group | Key Fields | Correlation |
|-------|-----------|------------|-------------|
| CloudFront WAF | `aws-waf-logs-cloudfront` | action, terminatingRuleId, URI, clientIp | timestamp + IP |
| ALB WAF | `aws-waf-logs-alb` | action, terminatingRuleId, URI, clientIp | timestamp + IP |
| API Service | `/ecs/secure-api/api` | event, correlation_id, method, path, status_code | X-Request-ID |
| Worker Service | `/ecs/secure-api/worker` | event, correlation_id, message_id, channels | correlation_id from Kinesis event |
| Scheduler | `/ecs/secure-api/scheduler` | event, correlation_id | correlation_id |
| PostgreSQL | `/aws/rds/.../postgresql` | SQL statement with `/* correlation_id=... */` | SQL comment |
| CloudTrail | CloudTrail log group | API calls, IAM actions | AWS request ID |
| GuardDuty | GuardDuty findings | threat type, severity, IP | finding ID |

## Limitations

- WAF logs don't include custom HTTP headers (`X-Request-ID`). Correlation
  between WAF and API logs relies on timestamp + client IP matching.
- PostgreSQL audit logs via pgaudit can be verbose. In production, consider
  setting `pgaudit.log = write` instead of `all` to reduce volume.
- The `log_min_duration_statement = 500` only logs slow queries. Set to `0`
  temporarily if you need to see all queries during the exercise.
- RDS log group name depends on the CDK-generated instance identifier
  (e.g., `/aws/rds/instance/datastack-databaseb269d8bb-dlatzwfqig4v/postgresql`).
  Check the actual name in CloudWatch console.

## References

- [Security Architecture](security.md)
- [Hexagonal Architecture](hexagonal-architecture.md)
- [Service Discovery](service-discovery.md)
