import os
import json
from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus
from dotenv import load_dotenv


load_dotenv()


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "metrica"
    user: str = "postgres"
    password: str = ""
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30

    @property
    def url(self) -> str:
        """URL для подключения к PostgreSQL (синхронный)"""
        encoded_password = quote_plus(self.password)
        return f"postgresql://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        """Async URL для подключения к PostgreSQL через asyncpg"""
        encoded_password = quote_plus(self.password)
        return f"postgresql+asyncpg://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"


class AppConfig(BaseModel):
    env: str = "development"
    name: str = "Music Store API"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    cors_origins: List[str] = ["http://localhost:5173"]

    @field_validator("secret_key")
    def validate_secret_key(cls, v: str, info) -> str:
        """В production secret_key обязателен"""
        if info.data.get("env") == "production" and not v:
            raise ValueError("SECRET_KEY must be set in production")
        return v

    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v


class SecurityConfig(BaseModel):
    jwt_secret_key: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 3000
    refresh_token_expire_days: int = 70
    bcrypt_rounds: int = 12

    @field_validator("jwt_secret_key")
    def validate_jwt_secret(cls, v: str) -> str:
        if not v:
            raise ValueError("JWT_SECRET_KEY must be set")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"  # json или console
    folder: Path = Path("logs")

    @field_validator("folder", mode="before")
    def validate_folder(cls, v: Any) -> Path:
        if isinstance(v, str):
            v = Path(v)
        v = v.resolve()
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("level")
    def validate_level(cls, v: str) -> str:
        valid = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid:
            raise ValueError(f"Log level must be one of: {', '.join(valid)}")
        return v.upper()


class AdminConfig(BaseModel):
    """Начальный администратор (создаётся при первом запуске)"""

    login: str = "admin"
    password: str = Field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD", "admin123")
    )
    email: str = "admin@musicstore.local"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    security: SecurityConfig = SecurityConfig()
    logging: LoggingConfig = LoggingConfig()
    admin: AdminConfig = AdminConfig()

    @property
    def is_development(self) -> bool:
        return self.app.env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app.env.lower() == "production"


cfg = Config()


def get_config() -> Config:
    return cfg


def setup_environment():
    """Настройка окружения (вызывается при старте)"""
    os.environ.setdefault("PYTHONPATH", str(Path.cwd()))

    if cfg.is_development:
        os.environ.setdefault("PYTHONASYNCIODEBUG", "1")

    # Настройка базового логирования
    import logging as std_logging

    std_logging.basicConfig(
        level=getattr(std_logging, cfg.logging.level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class AdminConfig(BaseModel):
    login: str = "admin"
    password: str = Field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD", "admin123")
    )
    email: str = "admin@musicstore.local"
