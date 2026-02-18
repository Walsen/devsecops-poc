# Automated Penetration Testing

This guide covers the automated penetration testing framework using Dockerized Kali Linux.

## Quick Start

```bash
# 1. Build the container
docker build -f testing/Dockerfile.kali -t pentest:latest testing/

# 2. Set target URL
export TARGET_URL=http://your-alb.amazonaws.com

# 3. Run tests
docker run --rm -e TARGET_URL=$TARGET_URL pentest all
```

## Architecture

### Components

1. **Kali Linux Container** (`testing/Dockerfile.kali`)
   - Base: `kalilinux/kali-rolling`
   - Tools: curl, jq, nmap, nikto, sqlmap, just
   - Size: ~500MB compressed

2. **Justfile Recipes** (`testing/justfile`)
   - Declarative test definitions
   - Environment variable support
   - Pass/fail validation

3. **CI/CD Integration** (optional)
   - GitHub Actions workflow
   - Scheduled execution
   - Automated reporting

## Available Tests

### Basic Tests

| Recipe | Description | Duration |
|--------|-------------|----------|
| `all` | All basic security tests | ~2 min |
| `smoke` | Health + headers check | ~10 sec |
| `health` | Connectivity test | ~5 sec |
| `headers` | Security headers | ~5 sec |

### Security Tests

| Recipe | Description | Duration |
|--------|-------------|----------|
| `waf-sql` | SQL injection WAF test | ~10 sec |
| `waf-xss` | XSS protection test | ~10 sec |
| `rate-limit` | Rate limiting (70 requests) | ~30 sec |
| `idor TOKEN` | IDOR protection (requires auth) | ~15 sec |

### Advanced Scans

| Recipe | Description | Duration |
|--------|-------------|----------|
| `nmap HOST` | Port scan | ~1 min |
| `nikto` | Web vulnerability scan | ~5 min |
| `sqlmap` | Automated SQL injection | ~10 min |
| `full-scan` | Complete scan (all tools) | ~15 min |

### Reporting

| Recipe | Description | Duration |
|--------|-------------|----------|
| `report` | Generate test report file | ~2 min |

## Usage Examples

### Development Testing

```bash
# Quick smoke test
docker run --rm -e TARGET_URL=http://localhost:8080 pentest smoke

# Full test suite
docker run --rm -e TARGET_URL=http://localhost:8080 pentest all

# Generate report
docker run --rm -v $(pwd):/tests \
  -e TARGET_URL=http://localhost:8080 pentest report
```

### Staging/Production Testing

```bash
# Get ALB endpoint from CloudFormation
export TARGET_URL=$(aws cloudformation describe-stacks \
  --stack-name ComputeStack \
  --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
  --output text)

# Run smoke test first
docker run --rm -e TARGET_URL=http://$TARGET_URL pentest smoke

# If smoke passes, run full suite
docker run --rm -e TARGET_URL=http://$TARGET_URL pentest all
```

### Authenticated Testing

```bash
# Get JWT token from Cognito
export TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=$USER,PASSWORD=$PASS \
  --query 'AuthenticationResult.AccessToken' \
  --output text)

# Run IDOR test
docker run --rm -e TARGET_URL=$TARGET_URL pentest idor $TOKEN
```

## CI/CD Integration

### GitHub Actions Workflow

Create `.github/workflows/pentest.yml`:

```yaml
name: Penetration Test
on:
  workflow_dispatch:
    inputs:
      target_url:
        description: 'Target URL'
        required: true
      test_type:
        description: 'Test type (smoke/all/full-scan)'
        required: false
        default: 'all'
  schedule:
    - cron: '0 2 * * 1'  # Weekly Monday 2am

jobs:
  pentest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build container
        run: docker build -f testing/Dockerfile.kali -t pentest testing/
      
      - name: Run tests
        run: |
          docker run --rm \
            -e TARGET_URL=${{ inputs.target_url || secrets.DEV_API_URL }} \
            pentest ${{ inputs.test_type || 'all' }}
      
      - name: Generate report
        if: always()
        run: |
          docker run --rm -v $(pwd):/tests \
            -e TARGET_URL=${{ inputs.target_url || secrets.DEV_API_URL }} \
            pentest report
      
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pentest-report-${{ github.run_number }}
          path: pentest-report.txt
```

### Trigger Workflow

```bash
# Manual trigger
gh workflow run pentest.yml \
  -f target_url=http://your-alb.amazonaws.com \
  -f test_type=smoke

# View results
gh run list --workflow=pentest.yml
gh run view <run-id>
gh run download <run-id>
```

## Adding Custom Tests

### 1. Edit Justfile

Add new recipe to `testing/justfile`:

```just
# Test custom security control
custom-security-test:
    @echo "=== Custom Security Test ==="
    curl -v {{target}}/custom/endpoint \
      -H "X-Custom-Header: test" \
      | grep "expected-response" \
      && echo "PASS" || echo "FAIL"
```

### 2. Rebuild Container

```bash
docker build -f testing/Dockerfile.kali -t pentest:latest testing/
```

### 3. Run New Test

```bash
docker run --rm -e TARGET_URL=$TARGET_URL pentest custom-security-test
```

## Troubleshooting

### Build Issues

```bash
# Clear Docker cache
docker builder prune -a

# Rebuild without cache
docker build --no-cache -f testing/Dockerfile.kali -t pentest testing/
```

### Network Issues

```bash
# Test connectivity from host
curl http://your-alb.amazonaws.com/health

# Use host network mode (Linux only)
docker run --rm --network host \
  -e TARGET_URL=http://localhost:8080 pentest health

# Check DNS resolution
docker run --rm pentest sh -c "nslookup your-alb.amazonaws.com"
```

### Permission Issues

```bash
# Ensure write permissions for reports
chmod 777 $(pwd)

# Run with user mapping
docker run --rm -u $(id -u):$(id -g) \
  -v $(pwd):/tests \
  -e TARGET_URL=$TARGET_URL pentest report
```

### Container Debugging

```bash
# Interactive shell
docker run --rm -it \
  -e TARGET_URL=$TARGET_URL \
  --entrypoint /bin/bash \
  pentest

# Inside container, run tests manually
just health
just headers
```

## Best Practices

### 1. Test Environments

- **Development**: Run full test suite on every deployment
- **Staging**: Run smoke tests on deployment, full suite weekly
- **Production**: Only run smoke tests, require approval for full scans

### 2. Test Frequency

```yaml
# Recommended schedule
- Development: On every PR + deployment
- Staging: Daily smoke, weekly full scan
- Production: Weekly smoke (off-hours)
```

### 3. Result Handling

```bash
# Save reports with timestamps
docker run --rm -v $(pwd):/tests \
  -e TARGET_URL=$TARGET_URL pentest report

mv pentest-report.txt "pentest-$(date +%Y%m%d-%H%M%S).txt"

# Archive old reports
mkdir -p reports/archive
mv pentest-*.txt reports/archive/
```

### 4. Security Considerations

- Never test production without authorization
- Use dedicated test accounts
- Rotate test credentials regularly
- Monitor for false positives
- Document all findings

## Integration with Other Tools

### OWASP ZAP

```bash
# Run ZAP baseline scan
docker run -t ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t $TARGET_URL
```

### Nuclei

```bash
# Run Nuclei vulnerability scanner
docker run -it projectdiscovery/nuclei \
  -u $TARGET_URL -severity critical,high
```

### Combine with Pentest Container

```bash
# Run all tools in sequence
docker run --rm -e TARGET_URL=$TARGET_URL pentest all
docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t $TARGET_URL
docker run -it projectdiscovery/nuclei -u $TARGET_URL -severity critical,high
```

## References

- [Kali Linux Documentation](https://www.kali.org/docs/)
- [Just Command Runner](https://just.systems/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [AWS Penetration Testing Policy](https://aws.amazon.com/security/penetration-testing/)
