from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Worker settings loaded from environment."""

    # Service
    service_name: str = "worker"
    service_namespace: str = "secure-api.local"

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "omnichannel"
    db_user: str = "dbadmin"
    db_password: str = ""

    # AWS
    kinesis_stream_name: str = "secure-api-events"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None  # For LocalStack

    # Meta API (Facebook, Instagram, WhatsApp)
    meta_access_token: str = ""
    meta_phone_number_id: str = ""  # WhatsApp
    meta_page_id: str = ""  # Facebook
    meta_instagram_account_id: str = ""
    whatsapp_community_id: str = ""  # WhatsApp community group ID

    # LinkedIn API
    linkedin_access_token: str = ""
    linkedin_organization_id: str = ""

    # AWS SES (Email)
    ses_sender_email: str = ""

    # AWS SNS (SMS)
    sns_sender_id: str = ""

    # AI Agent
    use_ai_agent: bool = False  # Enable AI agent for intelligent posting
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
