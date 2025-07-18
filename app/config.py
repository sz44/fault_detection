from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./database.db"
    app_name: str = "Fault Detection API"
    # comment out to use sqlite
    # model_config = SettingsConfigDict(env_file=".env")

@lru_cache
def get_settings():
    return Settings()