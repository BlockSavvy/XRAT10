from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "X Thread Analyzer"
    DEBUG: bool = True
    PORT: int = 8000
    
    # X API Settings
    X_API_KEY: str
    X_API_SECRET: str
    X_ACCESS_TOKEN: str
    X_ACCESS_TOKEN_SECRET: str
    X_BEARER_TOKEN: str
    
    # OAuth 2.0 Settings
    CLIENT_ID: str = "Yk15X05tVXJDYjREX1VtTDZFdzk6MTpjaQ"
    CLIENT_SECRET: str = "1PahUUHERTJCEob59uDlL_DPoXwF64b5kHDynGOPFm3s14S1aG"
    
    # Base URLs
    BASE_URL: str = "http://127.0.0.1:8000" if DEBUG else "https://xrat10.vercel.app"
    CALLBACK_URL: str = f"{BASE_URL}/callback"
    
    # Database Settings
    DATABASE_URL: str = "sqlite:///./analyses.db"
    
    # Security Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Returns:
        Settings: Application settings
    """
    return Settings() 