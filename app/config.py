from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    POSTGRES_URL: str = "postgres://localhost:5432"
    SQLITE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379"
    app_name: str = "Fault Detection API"
    # comment out to use defaults 
    model_config = SettingsConfigDict(env_file=".env")

@lru_cache
def get_settings():
    return Settings()