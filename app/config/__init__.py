"""Configuration module."""
from app.config.settings import Config, get_config, DevelopmentConfig, ProductionConfig, TestingConfig

__all__ = ["Config", "get_config", "DevelopmentConfig", "ProductionConfig", "TestingConfig"]

