"""Application configuration with environment-based settings."""
import os
import logging
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Base configuration class following Single Responsibility Principle."""
    
    # Load environment variables
    load_dotenv()
    
    # WhatsApp API Configuration
    ACCESS_TOKEN: Optional[str] = os.getenv("ACCESS_TOKEN")
    PHONE_NUMBER_ID: Optional[str] = os.getenv("PHONE_NUMBER_ID")
    VERSION: str = os.getenv("VERSION", "v18.0")
    VERIFY_TOKEN: Optional[str] = os.getenv("VERIFY_TOKEN")
    APP_SECRET: Optional[str] = os.getenv("APP_SECRET")
    APP_ID: Optional[str] = os.getenv("APP_ID")
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_SYSTEM_PROMPT: Optional[str] = os.getenv("OPENAI_SYSTEM_PROMPT")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_THREAD_TTL: int = int(os.getenv("REDIS_THREAD_TTL", "3600"))  # 1 hour default
    
    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL: str = os.getenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/2")
    RATELIMIT_ENABLED: bool = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    # Application
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration values."""
        required_vars = [
            ("ACCESS_TOKEN", cls.ACCESS_TOKEN),
            ("PHONE_NUMBER_ID", cls.PHONE_NUMBER_ID),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
        ]
        
        missing = [name for name, value in required_vars if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    REDIS_URL = "redis://localhost:6379/15"  # Use different DB for tests


def get_config() -> type[Config]:
    """Factory method to get configuration based on environment."""
    env = os.getenv("FLASK_ENV", "development").lower()
    
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    
    return config_map.get(env, DevelopmentConfig)

