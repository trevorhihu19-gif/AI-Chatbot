from functools import lru_cache
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  
    )

    app_env: Literal["development", "production", "test"] = "development"
    app_name: str = "Surge"
    app_version: str = "1.0.0"
    secret_key: str  

    @property
    def debug(self) -> bool:
        return self.app_env == "development"

    frontend_url: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_url]
        if self.app_env == "development":
            origins += [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        return origins

    database_url: str     
    database_url_sync: str 
    clerk_secret_key: str
    clerk_publishable_key: str
    clerk_webhook_secret: str

    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.7

    tavily_api_key: str


    chroma_host: str = "localhost"
    chroma_port: int = 8001

    arcjet_key: str

    sentry_dsn: str = "" 

    max_upload_size_mb: int = 20
    upload_dir: str = "./uploads"
    
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    semantic_weight: float = 0.6   
    keyword_weight: float = 0.4  

    allowed_file_types: str = "pdf, docx, txt, csv, md"
    @property
    def allowed_extensions(self) -> set[str]:
          return {ext.strip().lower() for ext in self.allowed_file_types.split(",") if ext.strip()} 

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_long(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()