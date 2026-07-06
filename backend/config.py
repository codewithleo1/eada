from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    allowed_origins: str = Field(default="http://localhost,http://localhost:5173", alias="ALLOWED_ORIGINS")

    # LLM
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    primary_model: str = "gemini/gemini-2.5-flash"
    fallback_model: str = "groq/llama-3.1-70b-versatile"
    max_tokens: int = 8192
    temperature: float = 0.1

    # Langfuse
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="http://localhost:3000", alias="LANGFUSE_HOST")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://eada:eada@localhost:5432/eada",
        alias="DATABASE_URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # Auth
    secret_key: str = Field(default="supersecretkey", alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


# Single instance imported everywhere
settings = Settings()
