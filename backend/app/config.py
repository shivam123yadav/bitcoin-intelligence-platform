from dataclasses import dataclass, field
import os


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _frontend_cors_origins() -> list[str]:
    configured = os.getenv("FRONTEND_CORS_ORIGINS")
    if not configured:
        return list(DEFAULT_CORS_ORIGINS)

    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if not origins:
        return list(DEFAULT_CORS_ORIGINS)
    if "*" in origins:
        raise ValueError(
            "FRONTEND_CORS_ORIGINS must not contain an unrestricted wildcard"
        )
    return origins


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "bitcoin-intelligence-backend")
    version: str = os.getenv("SERVICE_VERSION", "1.0.0")
    cors_origins: list[str] = field(default_factory=_frontend_cors_origins)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
