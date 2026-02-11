"""
Outbound port for content filtering and moderation.

Security: Provides guardrails for AI-generated content to prevent
prompt injection, malicious content, and policy violations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ContentRisk(Enum):
    """Risk levels for content moderation."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class ViolationType(Enum):
    """Types of content policy violations."""

    PROMPT_INJECTION = "prompt_injection"
    MALICIOUS_URL = "malicious_url"
    PROFANITY = "profanity"
    SPAM = "spam"
    PII_EXPOSURE = "pii_exposure"
    BRAND_SAFETY = "brand_safety"
    OFF_TOPIC = "off_topic"


@dataclass
class FilterResult:
    """Result of content filtering."""

    is_safe: bool
    risk_level: ContentRisk
    violations: list[ViolationType]
    sanitized_content: str | None = None  # Cleaned version if available
    reason: str | None = None


class ContentFilter(ABC):
    """
    Port for content filtering and moderation.

    Security: Validates both input (user content) and output (AI-generated)
    to prevent prompt injection and policy violations.
    """

    @abstractmethod
    def filter_input(self, content: str) -> FilterResult:
        """
        Filter user input before sending to AI.

        Security: Detects prompt injection attempts and malicious content.

        Args:
            content: User-provided content

        Returns:
            FilterResult with safety assessment
        """
        ...

    @abstractmethod
    def filter_output(self, content: str) -> FilterResult:
        """
        Filter AI-generated output before publishing.

        Security: Ensures AI output doesn't contain malicious content,
        PII, or policy violations.

        Args:
            content: AI-generated content

        Returns:
            FilterResult with safety assessment
        """
        ...
