from dataclasses import dataclass


@dataclass(frozen=True)
class MessageContent:
    """Immutable value object for message content."""
    text: str
    media_url: str | None = None
    
    def __post_init__(self) -> None:
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Message text cannot be empty")
        if len(self.text) > 4096:
            raise ValueError("Message text cannot exceed 4096 characters")
        if self.media_url and not self.media_url.startswith(("https://", "s3://")):
            raise ValueError("Media URL must be HTTPS or S3")
