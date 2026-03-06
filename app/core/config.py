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
    # URL مخصص لقاعدة بيانات الاختبار (PostgreSQL)
    test_database_url: str | None = None
    # إذا True نعتبر أنفسنا في وضع الاختبار (pytest أو سكربتات اختبارية)
    testing: bool = False
    # لو True نستخدم SQLite حتى لو DATABASE_URL في .env يشير لـ Postgres (للعمل المحلي بدون Supabase)
    use_sqlite: bool = False
    # CORS: comma-separated origins, e.g. https://fantasy-5aside.onrender.com,https://yourdomain.com. Use * for dev.
    cors_origins: str = "*"
    # Environment: production enables HSTS and stricter defaults
    env: str = "development"
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str | None = None

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
