# Penetration Testing

Automated security testing using Kali Linux in Docker or Vagrant.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Build the container
docker build -f testing/Dockerfile.kali -t pentest:latest testing/

# Run all tests
docker run --rm -e TARGET_URL=http://your-alb.amazonaws.com pentest all
```

### Option 2: Vagrant

**VirtualBox:**
```bash
cd testing/
vagrant up --provider=virtualbox
vagrant ssh
cd /vagrant && just all
```

**Libvirt (Linux):**
```bash
cd testing/
vagrant up --provider=libvirt
vagrant ssh
just all  # Files not synced, copy justfile manually
```

## Available Tests

- `all` - Run all basic tests
- `health` - Health check
- `headers` - Security headers verification
- `waf-sql` - SQL injection WAF test
- `waf-xss` - XSS WAF test
- `rate-limit` - Rate limiting test
- `smoke` - Quick smoke test
- `full-scan` - Full scan with nmap + nikto
- `report` - Generate test report

## Examples

```bash
# Smoke test
docker run --rm -e TARGET_URL=http://your-alb.amazonaws.com pentest smoke

# Full scan
docker run --rm -e TARGET_URL=http://your-alb.amazonaws.com pentest full-scan

# Generate report
docker run --rm -v $(pwd):/tests -e TARGET_URL=http://your-alb.amazonaws.com pentest report
```
