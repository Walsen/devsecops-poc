"""
Content filter implementation with security guardrails.

Security: Implements input/output filtering to prevent:
- Prompt injection attacks
- Malicious URLs
- PII exposure
- Policy violations
"""

import html
import re
from urllib.parse import urlparse

import structlog

from ...domain.ports.content_filter import (
    ContentFilter,
    ContentRisk,
    FilterResult,
    ViolationType,
)

logger = structlog.get_logger()

# Risk level ordering for comparison
RISK_ORDER = {
    ContentRisk.SAFE: 0,
    ContentRisk.LOW: 1,
    ContentRisk.MEDIUM: 2,
    ContentRisk.HIGH: 3,
    ContentRisk.BLOCKED: 4,
}


def _max_risk(a: ContentRisk, b: ContentRisk) -> ContentRisk:
    """Return the higher risk level."""
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b


# Prompt injection patterns (case-insensitive)
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(instructions?|prompts?)",
    r"disregard\s+(previous|all|above)",
    r"forget\s+(everything|all|previous)",
    r"new\s+instructions?:",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"\[\s*system\s*\]",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if|a)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"roleplay\s+as",
    r"jailbreak",
    r"bypass\s+(filter|safety|restriction)",
    r"override\s+(instruction|safety|filter)",
    r"execute\s+(command|code|script)",
    r"run\s+(command|code|script)",
    r"eval\s*\(",
    r"exec\s*\(",
]

# Malicious URL patterns
MALICIOUS_URL_PATTERNS = [
    r"bit\.ly",
    r"tinyurl\.com",
    r"t\.co",  # Allow Twitter but flag for review
    r"goo\.gl",
    r"ow\.ly",
    r"is\.gd",
    r"buff\.ly",
    r"adf\.ly",
    r"j\.mp",
    r"dlvr\.it",
]

# Allowed domains for URLs
ALLOWED_URL_DOMAINS = [
    "aws.amazon.com",
    "amazon.com",
    "linkedin.com",
    "github.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "credly.com",
    "certmetrics.com",
]

# PII patterns
PII_PATTERNS = [
    r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",  # SSN
    r"\b\d{16}\b",  # Credit card (basic)
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email (flag, don't block)
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone number
]

# Profanity list (basic - extend as needed)
PROFANITY_PATTERNS = [
    # Add patterns as needed - keeping minimal for example
]

# Off-topic patterns (not related to AWS certifications)
OFF_TOPIC_PATTERNS = [
    r"(buy|sell|purchase)\s+(now|today|cheap)",
    r"(click|visit)\s+(here|now|link)",
    r"(free|discount|offer)\s+(money|gift|prize)",
    r"(casino|gambling|lottery)",
    r"(crypto|bitcoin|nft)\s+(invest|buy|sell)",
]


class ContentFilterImpl(ContentFilter):
    """
    Implementation of content filtering with security guardrails.

    Security features:
    - Prompt injection detection
    - Malicious URL blocking
    - PII detection
    - Off-topic content filtering
    - HTML sanitization
    """

    def __init__(self, strict_mode: bool = True) -> None:
        """
        Initialize content filter.

        Args:
            strict_mode: If True, block on medium risk. If False, only block high risk.
        """
        self._strict_mode = strict_mode
        self._injection_patterns = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]
        self._malicious_url_patterns = [
            re.compile(p, re.IGNORECASE) for p in MALICIOUS_URL_PATTERNS
        ]
        self._pii_patterns = [re.compile(p) for p in PII_PATTERNS]
        self._off_topic_patterns = [re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS]

    def filter_input(self, content: str) -> FilterResult:
        """
        Filter user input before sending to AI.

        Security: Detects prompt injection attempts and malicious content.
        """
        violations: list[ViolationType] = []
        risk_level = ContentRisk.SAFE

        # Check for prompt injection
        for pattern in self._injection_patterns:
            if pattern.search(content):
                violations.append(ViolationType.PROMPT_INJECTION)
                risk_level = ContentRisk.BLOCKED
                logger.warning(
                    "Prompt injection detected",
                    pattern=pattern.pattern,
                    content_preview=content[:100],
                )
                break

        # Check for malicious URLs
        if risk_level != ContentRisk.BLOCKED:
            urls = re.findall(r"https?://[^\s]+", content)
            for url in urls:
                if self._is_malicious_url(url):
                    violations.append(ViolationType.MALICIOUS_URL)
                    risk_level = _max_risk(risk_level, ContentRisk.HIGH)
                    logger.warning("Malicious URL detected", url=url)

        # Check for off-topic content
        if risk_level not in (ContentRisk.BLOCKED, ContentRisk.HIGH):
            for pattern in self._off_topic_patterns:
                if pattern.search(content):
                    violations.append(ViolationType.OFF_TOPIC)
                    risk_level = _max_risk(risk_level, ContentRisk.MEDIUM)
                    break

        # Sanitize content
        sanitized = self._sanitize_input(content)

        is_safe = risk_level in (ContentRisk.SAFE, ContentRisk.LOW)
        if not self._strict_mode:
            is_safe = risk_level != ContentRisk.BLOCKED

        return FilterResult(
            is_safe=is_safe,
            risk_level=risk_level,
            violations=violations,
            sanitized_content=sanitized if is_safe else None,
            reason=f"Violations: {[v.value for v in violations]}" if violations else None,
        )

    def filter_output(self, content: str) -> FilterResult:
        """
        Filter AI-generated output before publishing.

        Security: Ensures AI output doesn't contain malicious content or PII.
        """
        violations: list[ViolationType] = []
        risk_level = ContentRisk.SAFE

        # Check for PII in output
        for pattern in self._pii_patterns:
            if pattern.search(content):
                violations.append(ViolationType.PII_EXPOSURE)
                risk_level = _max_risk(risk_level, ContentRisk.HIGH)
                logger.warning("PII detected in output", pattern=pattern.pattern)

        # Check for malicious URLs in output
        urls = re.findall(r"https?://[^\s]+", content)
        for url in urls:
            if self._is_malicious_url(url):
                violations.append(ViolationType.MALICIOUS_URL)
                risk_level = _max_risk(risk_level, ContentRisk.HIGH)

        # Check for prompt injection artifacts (AI might have been compromised)
        for pattern in self._injection_patterns:
            if pattern.search(content):
                violations.append(ViolationType.PROMPT_INJECTION)
                risk_level = ContentRisk.BLOCKED
                logger.error(
                    "Prompt injection artifact in AI output - possible compromise",
                    content_preview=content[:200],
                )
                break

        # Sanitize output
        sanitized = self._sanitize_output(content)

        is_safe = risk_level in (ContentRisk.SAFE, ContentRisk.LOW)
        if not self._strict_mode:
            is_safe = risk_level != ContentRisk.BLOCKED

        return FilterResult(
            is_safe=is_safe,
            risk_level=risk_level,
            violations=violations,
            sanitized_content=sanitized if is_safe else None,
            reason=f"Violations: {[v.value for v in violations]}" if violations else None,
        )

    def _is_malicious_url(self, url: str) -> bool:
        """Check if URL is potentially malicious."""
        # Check against known shorteners/suspicious domains
        for pattern in self._malicious_url_patterns:
            if pattern.search(url):
                return True

        # Check if domain is in allowed list
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Check if it's a subdomain of allowed domains
            for allowed in ALLOWED_URL_DOMAINS:
                if domain == allowed or domain.endswith(f".{allowed}"):
                    return False

            # Unknown domain - flag as suspicious but don't block
            logger.info("Unknown URL domain", domain=domain, url=url)
            return False  # Don't block, just log

        except Exception:
            return True  # Can't parse = suspicious

    def _sanitize_input(self, content: str) -> str:
        """Sanitize user input."""
        # HTML escape
        sanitized = html.escape(content)
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        # Normalize whitespace
        sanitized = " ".join(sanitized.split())
        return sanitized

    def _sanitize_output(self, content: str) -> str:
        """Sanitize AI output."""
        # Remove any HTML tags that might have been generated
        sanitized = re.sub(r"<[^>]+>", "", content)
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        # Normalize excessive whitespace but preserve line breaks
        lines = sanitized.split("\n")
        lines = [" ".join(line.split()) for line in lines]
        sanitized = "\n".join(lines)
        return sanitized.strip()
