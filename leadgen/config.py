from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    apify_api_token: str | None = None
    database_path: str = "leads.db"
    http_timeout: float = 20.0
    max_limit: int = 100
    raw_retention_days: int = 30
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")
