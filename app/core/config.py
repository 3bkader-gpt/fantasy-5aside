import os
from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_URL = "sqlite:///./data/fantasy.db"

class Settings(BaseSettings):
    database_url: str = SQLITE_URL
    # لو True نستخدم SQLite حتى لو DATABASE_URL في .env يشير لـ Postgres (للعمل المحلي بدون Supabase)
    use_sqlite: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_database_url(self) -> str:
        if self.use_sqlite:
            return SQLITE_URL
        # في الإنتاج (مثلاً Render) متبقاش ملف .env فـ database_url ييجي من متغير البيئة
        url = self.database_url
        if url and url.startswith("sqlite"):
            return url
        # لو الاتصال لـ Postgres/Supabase ومتضبطش USE_SQLITE، استخدم الـ URL كما هو
        return url or SQLITE_URL

settings = Settings()
