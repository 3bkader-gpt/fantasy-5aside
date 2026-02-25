import os
from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_URL = "sqlite:///./data/fantasy.db"

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_database_url(self) -> str:
        # أولاً: وضع الاختبار مع TEST_DATABASE_URL
        if self.testing and self.test_database_url:
            return self.test_database_url

        if self.use_sqlite:
            return SQLITE_URL
        # Prefer SUPABASE_URL if present; otherwise fall back to DATABASE_URL
        url = self.supabase_url or self.database_url
        if url and url.startswith("sqlite"):
            return url
        # لو الاتصال لـ Postgres/Supabase ومتضبطش USE_SQLITE، استخدم الـ URL كما هو
        return url or SQLITE_URL

settings = Settings()
