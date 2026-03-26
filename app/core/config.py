import os
from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_URL = "sqlite:///./data/fantasy.db"


def _parse_cors_origins(value: str) -> list[str]:
    """Parse CORS_ORIGINS env (comma-separated) into list. '*' stays as single element."""
    if not value or not value.strip():
        return ["*"]
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts if parts else ["*"]


class Settings(BaseSettings):
    database_url: str = SQLITE_URL
    # Optional: use Supabase pooler URL when available (more reliable on some networks)
    supabase_url: str | None = None
    # Supabase Storage: project URL (e.g. https://xxx.supabase.co) and service_role key for server uploads
    supabase_project_url: str | None = None
    supabase_service_role_key: str | None = None
    # URL مخصص لقاعدة بيانات الاختبار (PostgreSQL)
    test_database_url: str | None = None
    # إذا True نعتبر أنفسنا في وضع الاختبار (pytest أو سكربتات اختبارية)
    testing: bool = False
    # لو True نستخدم SQLite حتى لو DATABASE_URL في .env يشير لـ Postgres (للعمل المحلي بدون Supabase)
    use_sqlite: bool = False
    # CORS: comma-separated origins, e.g. https://fantasy-5aside.onrender.com,https://yourdomain.com. Use * for dev.
    cors_origins: str = "*"
    # Trust X-Forwarded-For for client IP extraction only behind trusted proxy.
    trust_proxy_headers: bool = False
    # Environment: production enables HSTS and stricter defaults
    env: str = "development"
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str | None = None
    # Email / provider settings
    email_provider: str = "log"  # "log", "brevo", etc. (override via EMAIL_PROVIDER)
    email_daily_limit: int = 300  # Default aligned with Brevo Free plan
    brevo_api_key: str | None = None
    brevo_sender_email: str | None = None
    brevo_sender_name: str | None = None
    brevo_api_base_url: str = "https://api.brevo.com/v3"

    # Sentry (Phase 6)
    sentry_dsn: str | None = None
    sentry_environment: str | None = None
    sentry_traces_sample_rate: float = 0.0

    # Superadmin (Phase 6)
    superadmin_secret: str | None = None

    # Email verification link TTL (hours); token stored on User with expiry
    user_verify_token_ttl_hours: int = 24

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return _parse_cors_origins(self.cors_origins)

    @property
    def effective_database_url(self) -> str:
        # أولاً: وضع الاختبار مع TEST_DATABASE_URL أو الرجوع لـ SQLite للأمان
        if self.testing:
            return self.test_database_url or SQLITE_URL

        if self.use_sqlite:
            return SQLITE_URL
        # Prefer SUPABASE_URL if present; otherwise fall back to DATABASE_URL
        url = self.supabase_url or self.database_url
        if url and url.startswith("sqlite"):
            return url
        # لو الاتصال لـ Postgres/Supabase ومتضبطش USE_SQLITE، استخدم الـ URL كما هو
        return url or SQLITE_URL

settings = Settings()
