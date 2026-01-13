from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_name: str = "ExpenseTrackerAPI"
    base_url: str = "http://127.0.0.1:8000"

    database_url: str

    # Clerk/Auth0 JWT settings
    jwt_issuer: str = "https://clerk.example.com"
    jwt_audience: str | None = None
    jwks_url: str = "https://clerk.example.com/.well-known/jwks.json"

    cors_origins: str = "http://localhost:3000"

    default_timezone: str = "Europe/Kyiv"
    default_currency: str = "CZK"

    # Pagination
    transactions_page_size_default: int = 30
    transactions_page_size_max: int = 100

    def cors_origin_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
