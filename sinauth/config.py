from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    service_name: str
    data_path: Path
    auth_secret: str
    token_ttl_seconds: int
    web_auth_token_ttl_seconds: int
    registration_enabled: bool
    admin_username: str
    admin_password: str
    host: str
    port: int
    forwarded_allow_ips: str


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "sinauth"),
        data_path=Path(os.getenv("DATA_PATH", "data/sinauth.pkl")),
        auth_secret=os.getenv("AUTH_SECRET", "change-me-in-production"),
        token_ttl_seconds=int(os.getenv("TOKEN_TTL_SECONDS", "518400")),
        web_auth_token_ttl_seconds=int(os.getenv("WEB_AUTH_TOKEN_TTL_SECONDS", "300")),
        registration_enabled=env_bool("REGISTRATION_ENABLED", True),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
