# Security Implementation Standards

## Authentication & Authorization

### JWT Validation
All API endpoints MUST validate JWT tokens:
```python
# Required validations
- Algorithm: RS256 only (reject HS256, none)
- Audience: Must match expected client ID
- Issuer: Must match Cognito User Pool URL
- Expiration: Token must not be expired
- JWKS: Cache with TTL, refresh on key rotation
```

### User-Scoped Access (IDOR Prevention)
```python
# ✅ Always filter by authenticated user
async def get_message(self, message_id: UUID, user_id: str) -> Message:
    message = await self._repository.get_by_id(message_id)
    if message and message.user_id != user_id:
        raise ForbiddenError("Access denied")
    return message

# ❌ Never trust client-provided user IDs
async def get_message(self, message_id: UUID, user_id: str) -> Message:
    return await self._repository.get_by_id(message_id)  # Missing user check!
```

## Input Validation & Sanitization

### Pydantic Validators
```python
from pydantic import BaseModel, field_validator
import html

class CreateMessageDTO(BaseModel):
    content: str
    
    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Escape HTML to prevent XSS
        return html.escape(v.strip())
```

### Request Size Limits
```python
# Middleware to limit request body size
MAX_BODY_SIZE = 1_048_576  # 1MB

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        raise HTTPException(413, "Request too large")
    return await call_next(request)
```

## Secrets Management

### Never Hardcode Secrets
```python
# ❌ NEVER do this
API_KEY = "sk-1234567890abcdef"
DATABASE_URL = "postgresql://user:password@host/db"

# ✅ Use environment variables or Secrets Manager
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    api_key: str  # Loaded from environment
```

### Runtime Secrets Fetch
```python
# For sensitive secrets, fetch at runtime
class SecretsManager:
    def __init__(self):
        self._client = boto3.client("secretsmanager")
        self._cache: dict[str, tuple[str, float]] = {}
        self._ttl = 300  # 5 minutes
    
    async def get_secret(self, secret_id: str) -> str:
        # Check cache first
        if secret_id in self._cache:
            value, expires = self._cache[secret_id]
            if time.time() < expires:
                return value
        
        # Fetch from Secrets Manager
        response = self._client.get_secret_value(SecretId=secret_id)
        value = response["SecretString"]
        self._cache[secret_id] = (value, time.time() + self._ttl)
        return value
```

## Rate Limiting

### Per-User Rate Limits
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self._limit = requests_per_minute
        self._window = 60  # seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
    
    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        window_start = now - self._window
        
        # Clean old requests
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]
        
        if len(self._requests[user_id]) >= self._limit:
            return False
        
        self._requests[user_id].append(now)
        return True
```

## AI/LLM Security (Content Filtering)

### Input Filtering
```python
# Block prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"disregard\s+.*\s+instructions",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+",
    r"pretend\s+to\s+be",
]

def detect_prompt_injection(content: str) -> bool:
    content_lower = content.lower()
    return any(re.search(p, content_lower) for p in PROMPT_INJECTION_PATTERNS)
```

### Output Filtering
```python
# Detect PII in AI responses
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

def detect_pii(content: str) -> list[str]:
    violations = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, content):
            violations.append(pii_type)
    return violations
```

## Security Headers

### Required Response Headers
```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
```

## Idempotency (Replay Attack Prevention)

### Message Processing
```python
class IdempotencyService:
    def check_and_lock(self, key: str) -> IdempotencyRecord | None:
        """
        Returns existing record if already processed.
        Returns None and locks if new (safe to process).
        """
        ...
    
    def mark_completed(self, key: str, result: dict) -> None:
        """Mark operation as completed to prevent replay."""
        ...
```

## Security Scanning (CI/CD)

### Required Scanners
| Scanner | Purpose |
|---------|---------|
| Trivy | Container & SBOM vulnerability scanning |
| Semgrep | SAST with OWASP Top 10 rules |
| pip-audit | Python dependency CVE checking |
| Checkov | IaC security for CDK/CloudFormation |
| npm audit | JavaScript dependency vulnerabilities |
| Dependabot | Automated dependency updates |

## References
- Security documentation: #[[file:docs/security.md]]
- OWASP Top 10: https://owasp.org/Top10/
