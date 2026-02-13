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

## Exercise 6: Pentesting Tools (Kali Linux / Parrot OS)

These exercises use professional penetration testing tools. Install them via
your distro's package manager or use a Kali/Parrot live image.

```bash
# Kali / Parrot / Debian
sudo apt install sqlmap nikto nmap hydra ffuf nuclei

# macOS (via Homebrew)
brew install sqlmap nikto nmap hydra ffuf nuclei
```

> **Important**: Only run these against your own infrastructure. Set the
> target variables once and reuse them across exercises.

```bash
export TARGET="https://d2rv56b0ccriwq.cloudfront.net"
export ALB_TARGET="http://Comput-Alb16-j1fq7hseoZQw-945843054.us-east-1.elb.amazonaws.com"
export AWS_PROFILE="awscbba"
```

### 6.1 — nmap: Service Discovery & Port Scanning

Discover what's exposed and verify only expected ports are open.

```bash
# Quick scan of the ALB (CloudFront won't respond to nmap)
nmap -sV -T4 -Pn \
  Comput-Alb16-j1fq7hseoZQw-945843054.us-east-1.elb.amazonaws.com

# Check for TLS configuration
nmap --script ssl-enum-ciphers -p 443 \
  d2rv56b0ccriwq.cloudfront.net
```

Expected: Only port 80 open on ALB (CloudFront terminates TLS).
TLS scan should show TLS 1.2+ only, no weak ciphers.

**Trace it:**

```bash
# Check if nmap probes triggered WAF rules
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "aws-waf-logs-alb" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId, httpRequest.clientIp
    | filter action = 'BLOCK'
    | sort @timestamp desc | limit 20
  "
```

### 6.2 — nikto: Web Server Vulnerability Scan

Scan for common web server misconfigurations, default files, and known vulnerabilities.

```bash
nikto -h "$TARGET" \
  -Tuning 1234567890abc \
  -output nikto-report.html -Format html
```

Expected: nikto will probe hundreds of paths. Most will return 404 or get
blocked by WAF. Review the report for any unexpected 200 responses.

**Trace it:**

```bash
# See the flood of nikto probes in WAF logs
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "aws-waf-logs-cloudfront" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, httpRequest.uri, httpRequest.clientIp
    | stats count() by action
  "
```

You should see a large number of BLOCK actions from the
`AWSManagedRulesKnownBadInputsRuleSet` and `AWSManagedRulesCommonRuleSet`.

### 6.3 — sqlmap: Automated SQL Injection Testing

sqlmap is the gold standard for SQL injection detection. It will try dozens
of injection techniques against each parameter.

```bash
# Test the public certifications endpoint
sqlmap -u "$TARGET/api/v1/certifications/types/?q=test" \
  --batch \
  --level=3 \
  --risk=2 \
  --random-agent \
  --output-dir=./sqlmap-output

# Test with a custom header for tracing
sqlmap -u "$TARGET/api/v1/certifications/types/?q=test" \
  --batch \
  --level=3 \
  --headers="X-Request-ID: sqlmap-test-$(date +%s)" \
  --output-dir=./sqlmap-output
```

Expected: sqlmap should report "all tested parameters do not appear to be
injectable" because:
1. WAF blocks most SQLi payloads before they reach the app
2. SQLAlchemy uses parameterized queries (immune to SQLi)

**Trace it:**

```bash
# Count WAF blocks triggered by sqlmap
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "aws-waf-logs-cloudfront" "aws-waf-logs-alb" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId, httpRequest.uri
    | filter action = 'BLOCK'
    | filter terminatingRuleId like 'SQLi'
    | stats count() by terminatingRuleId
  "
```

### 6.4 — ffuf: Endpoint Fuzzing & Directory Discovery

Fuzz for hidden endpoints, admin panels, and debug routes.

```bash
# Fuzz for common paths (use SecLists wordlist)
# Install: apt install seclists
ffuf -u "$TARGET/FUZZ" \
  -w /usr/share/seclists/Discovery/Web-Content/common.txt \
  -mc 200,301,302,401,403 \
  -H "X-Request-ID: ffuf-fuzz-$(date +%s)" \
  -rate 10 \
  -o ffuf-results.json

# Fuzz API versions
ffuf -u "$TARGET/api/FUZZ/health" \
  -w <(echo -e "v1\nv2\nv3\ninternal\nadmin\ndebug\ntest") \
  -mc 200 \
  -H "X-Request-ID: ffuf-api-$(date +%s)"
```

Expected: Only `/health`, `/docs`, `/api/v1/*` should return 200.
No admin panels, debug endpoints, or hidden API versions.

**Trace it:**

```bash
# See ffuf's probes in API logs (requests that passed WAF)
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "/ecs/secure-api/api" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, path, status_code, correlation_id
    | filter correlation_id like 'ffuf-fuzz'
    | stats count() by status_code
  "
```

### 6.5 — nuclei: Template-Based Vulnerability Scanning

nuclei uses community-maintained templates to test for thousands of known
vulnerabilities, misconfigurations, and exposures.

```bash
# Update templates first
nuclei -update-templates

# Run with common web templates
nuclei -u "$TARGET" \
  -t http/cves/ \
  -t http/misconfiguration/ \
  -t http/exposures/ \
  -t http/vulnerabilities/ \
  -severity medium,high,critical \
  -rate-limit 10 \
  -header "X-Request-ID: nuclei-scan-$(date +%s)" \
  -o nuclei-results.txt

# Run specifically for security headers check
nuclei -u "$TARGET" \
  -t http/misconfiguration/http-missing-security-headers.yaml \
  -o nuclei-headers.txt
```

Expected: Security headers should pass (we set X-Content-Type-Options,
X-Frame-Options, HSTS, CSP, etc. via SecurityHeadersMiddleware).
No critical CVEs should be found.

**Trace it:**

```bash
# Check WAF blocks from nuclei's probes
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "aws-waf-logs-cloudfront" \
  --start-time $(date -d '30 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId, httpRequest.uri
    | filter action = 'BLOCK'
    | stats count() by terminatingRuleId
    | sort count() desc
  "
```

### 6.6 — hydra: Authentication Brute Force

Test rate limiting and account lockout against the Cognito-backed auth.

```bash
# Create a small password list
cat > /tmp/passwords.txt << 'EOF'
password
123456
admin
letmein
welcome
monkey
dragon
master
qwerty
login
EOF

# Brute force the auth endpoint (will hit rate limiter fast)
hydra -l test@example.com \
  -P /tmp/passwords.txt \
  -s 443 -S \
  d2rv56b0ccriwq.cloudfront.net \
  https-post-form \
  "/api/v1/auth/login:username=^USER^&password=^PASS^:Invalid"
```

Expected: hydra will fail — requests get rate-limited (429) after a few
attempts. WAF rate limiting (2000 req/IP) and app-level rate limiting
(60 req/min per user) both kick in.

**Trace it:**

```bash
# Check rate limit hits and failed auth attempts
aws logs start-query --profile $AWS_PROFILE \
  --log-group-names "/ecs/secure-api/api" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields @timestamp, event, client_ip, correlation_id
    | filter event like 'Rate limit' or event like 'Authentication failed'
    | sort @timestamp desc | limit 30
  "

# Check if the security alarm fired
aws cloudwatch describe-alarms --profile $AWS_PROFILE \
  --alarm-name-prefix "ObservabilityStack" \
  --state-value ALARM \
  --query 'MetricAlarms[].AlarmName' --output table
```

### 6.7 — Full Pentest Summary Script

Run all tools in sequence and generate a combined report:

```bash
#!/usr/bin/env bash
# golden-thread-pentest.sh — Run all exercises and collect traces
set -euo pipefail

TARGET="https://d2rv56b0ccriwq.cloudfront.net"
PROFILE="awscbba"
TIMESTAMP=$(date +%s)
REPORT_DIR="./pentest-report-$TIMESTAMP"
mkdir -p "$REPORT_DIR"

echo "=== Golden Thread Pentest — $TIMESTAMP ==="

echo "[1/5] nmap scan..."
nmap -sV -T4 -Pn -oN "$REPORT_DIR/nmap.txt" \
  Comput-Alb16-j1fq7hseoZQw-945843054.us-east-1.elb.amazonaws.com

echo "[2/5] nikto scan..."
nikto -h "$TARGET" -output "$REPORT_DIR/nikto.html" -Format html 2>/dev/null || true

echo "[3/5] sqlmap test..."
sqlmap -u "$TARGET/api/v1/certifications/types/?q=test" \
  --batch --level=2 --output-dir="$REPORT_DIR/sqlmap" 2>/dev/null || true

echo "[4/5] ffuf fuzz..."
ffuf -u "$TARGET/FUZZ" \
  -w /usr/share/seclists/Discovery/Web-Content/common.txt \
  -mc 200,301,302,401,403 -rate 10 \
  -o "$REPORT_DIR/ffuf.json" 2>/dev/null || true

echo "[5/5] nuclei scan..."
nuclei -u "$TARGET" \
  -severity medium,high,critical -rate-limit 10 \
  -o "$REPORT_DIR/nuclei.txt" 2>/dev/null || true

echo ""
echo "=== Collecting WAF traces ==="
QUERY_ID=$(aws logs start-query --profile "$PROFILE" \
  --log-group-names "aws-waf-logs-cloudfront" "aws-waf-logs-alb" \
  --start-time $((TIMESTAMP - 3600)) --end-time $(date +%s) \
  --query-string "
    fields @timestamp, action, terminatingRuleId, httpRequest.uri, httpRequest.clientIp
    | filter action = 'BLOCK'
    | stats count() by terminatingRuleId
    | sort count() desc
  " --query 'queryId' --output text)

sleep 5
aws logs get-query-results --profile "$PROFILE" \
  --query-id "$QUERY_ID" > "$REPORT_DIR/waf-blocks-summary.json"

echo ""
echo "=== Results saved to $REPORT_DIR ==="
ls -la "$REPORT_DIR/"
```

## Interpreting Results

After running the pentest tools, query CloudWatch for a consolidated view:

```bash
# Total WAF blocks by rule in the last hour
aws logs start-query --profile awscbba \
  --log-group-names "aws-waf-logs-cloudfront" "aws-waf-logs-alb" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string "
    fields action, terminatingRuleId
    | filter action = 'BLOCK'
    | stats count() as blocked by terminatingRuleId
    | sort blocked desc
  "
```

Expected output after a full pentest run:

| terminatingRuleId | blocked |
|-------------------|---------|
| AWSManagedRulesCommonRuleSet | ~200+ |
| AWSManagedRulesSQLiRuleSet | ~50+ |
| AWSManagedRulesKnownBadInputsRuleSet | ~30+ |
| RateLimitRule | ~10+ |
| BlockBadIps | 0 (unless GuardDuty auto-blocked your IP) |

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
