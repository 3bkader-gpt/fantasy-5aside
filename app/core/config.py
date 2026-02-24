from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/fantasy.db"
    
    # In a real app, you'd add JWT keys, algorithm, etc. here
    # secret_key: str = "SUPER_SECRET_KEY"
    # algorithm: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
