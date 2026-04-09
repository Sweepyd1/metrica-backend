import os
import json
from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus
from dotenv import load_dotenv


load_dotenv()


def get_app_env() -> str:
    return os.getenv("APP_ENV", "development").lower()


def get_dev_jwt_secret() -> str:
    return "dev-jwt-secret-key-for-local-frontend-only-change-me"


def get_jwt_secret_key() -> str:
    configured_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if configured_secret:
        return configured_secret
    if get_app_env() != "production":
        return get_dev_jwt_secret()
    return ""


class ValidatedConfigModel(BaseModel):
    model_config = ConfigDict(validate_default=True)


class DatabaseConfig(ValidatedConfigModel):
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


class AppConfig(ValidatedConfigModel):
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


class SecurityConfig(ValidatedConfigModel):
    jwt_secret_key: str = Field(default_factory=get_jwt_secret_key)
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


class AuthConfig(ValidatedConfigModel):
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    oauth_flow_cookie_prefix: str = "oauth_flow"
    oauth_flow_ttl_seconds: int = 600
    cookie_secure: bool = Field(
        default_factory=lambda: get_app_env() == "production"
    )
    cookie_samesite: str = "lax"
    cookie_domain: Optional[str] = None
    phone_code_ttl_seconds: int = 300
    phone_code_length: int = 6
    phone_code_attempt_limit: int = 5
    phone_code_resend_seconds: int = 60
    debug_return_phone_code: bool = Field(
        default_factory=lambda: os.getenv(
            "AUTH_DEBUG_RETURN_PHONE_CODE",
            "true" if get_app_env() != "production" else "false",
        ).lower()
        == "true"
    )
    telegram_bot_token: str = Field(
        default_factory=lambda: os.getenv("AUTH_TELEGRAM_BOT_TOKEN", "")
    )
    telegram_bot_username: str = Field(
        default_factory=lambda: os.getenv("AUTH_TELEGRAM_BOT_USERNAME", "")
    )
    telegram_auth_max_age_seconds: int = 86400
    telegram_message_auth_ttl_seconds: int = 600
    telegram_message_code_length: int = 6
    telegram_api_base_url: str = "https://api.telegram.org"
    yandex_client_id: str = Field(
        default_factory=lambda: os.getenv("AUTH_YANDEX_CLIENT_ID", "")
    )
    yandex_client_secret: str = Field(
        default_factory=lambda: os.getenv("AUTH_YANDEX_CLIENT_SECRET", "")
    )
    yandex_redirect_uri: str = Field(
        default_factory=lambda: os.getenv("AUTH_YANDEX_REDIRECT_URI", "")
    )
    yandex_scope: str = Field(
        default_factory=lambda: os.getenv("AUTH_YANDEX_SCOPE", "")
    )
    yandex_authorize_url: str = "https://oauth.yandex.com/authorize"
    yandex_token_url: str = "https://oauth.yandex.com/token"
    yandex_user_info_url: str = "https://login.yandex.ru/info"
    vk_client_id: str = Field(
        default_factory=lambda: os.getenv("AUTH_VK_CLIENT_ID", "")
    )
    vk_client_secret: str = Field(
        default_factory=lambda: os.getenv("AUTH_VK_CLIENT_SECRET", "")
    )
    vk_redirect_uri: str = Field(
        default_factory=lambda: os.getenv("AUTH_VK_REDIRECT_URI", "")
    )
    vk_scope: str = Field(
        default_factory=lambda: os.getenv("AUTH_VK_SCOPE", "email phone")
    )
    vk_authorize_url: str = "https://id.vk.ru/authorize"
    vk_token_url: str = "https://id.vk.ru/oauth2/auth"
    vk_user_info_url: str = "https://id.vk.ru/oauth2/user_info"
    oauth_http_timeout_seconds: float = 15.0

    @field_validator("cookie_samesite")
    def validate_cookie_samesite(cls, v: str) -> str:
        allowed = {"lax", "strict", "none"}
        normalized = v.lower()
        if normalized not in allowed:
            raise ValueError("cookie_samesite must be one of: lax, strict, none")
        return normalized

    @field_validator("phone_code_length")
    def validate_phone_code_length(cls, v: int) -> int:
        if v < 4 or v > 8:
            raise ValueError("phone_code_length must be between 4 and 8")
        return v

    @field_validator("telegram_message_code_length")
    def validate_telegram_message_code_length(cls, v: int) -> int:
        if v < 4 or v > 8:
            raise ValueError("telegram_message_code_length must be between 4 and 8")
        return v

    @field_validator("oauth_flow_ttl_seconds")
    def validate_oauth_flow_ttl_seconds(cls, v: int) -> int:
        if v < 60:
            raise ValueError("oauth_flow_ttl_seconds must be at least 60")
        return v


class LoggingConfig(ValidatedConfigModel):
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


class AdminConfig(ValidatedConfigModel):
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
        validate_default=True,
    )

    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    security: SecurityConfig = SecurityConfig()
    auth: AuthConfig = AuthConfig()
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
