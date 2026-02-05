from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Scheduler settings loaded from environment."""

    # Service
    service_name: str = "scheduler"
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

    # Scheduler
    poll_interval_seconds: int = 60  # Check for due messages every minute
    batch_size: int = 100  # Max messages to process per poll

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
