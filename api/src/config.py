from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Service
    service_name: str = "api"
    service_namespace: str = "secure-api.local"
    debug: bool = False

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

    # Authentication
    auth_enabled: bool = False  # Disable in development
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cognito_region: str = "us-east-1"

    # Service Discovery
    api_service_host: str = "api.secure-api.local"
    worker_service_host: str = "worker.secure-api.local"
    scheduler_service_host: str = "scheduler.secure-api.local"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
