"""Rate limiting middleware using Flask-Limiter."""
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, current_app
from typing import Callable

from app.config.settings import Config
from app.infrastructure.redis_client import RedisClientFactory


def get_limiter_key() -> str:
    """
    Get rate limit key based on WhatsApp user ID or IP address.
    
    Returns:
        String key for rate limiting
    """
    # Try to extract WhatsApp user ID from request body
    if request.is_json:
        body = request.get_json()
        try:
            wa_id = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("contacts", [{}])[0].get("wa_id")
            if wa_id:
                return f"rate_limit:wa:{wa_id}"
        except (KeyError, IndexError, AttributeError):
            pass
    
    # Fallback to IP address
    return get_remote_address()


def create_rate_limiter(app) -> Limiter:
    """
    Create and configure Flask-Limiter instance.
    
    Args:
        app: Flask application instance
        
    Returns:
        Configured Limiter instance
    """
    try:
        if not Config.RATELIMIT_ENABLED:
            # Return a no-op limiter if rate limiting is disabled
            return Limiter(
                app=app,
                key_func=get_remote_address,
                default_limits=[],
                storage_uri="memory://"
            )
        
        # Use Redis for rate limiting storage
        redis_url = Config.RATELIMIT_STORAGE_URL
        # Extract host:port/db from redis URL
        if "://" in redis_url:
            redis_path = redis_url.split("://", 1)[1]
        else:
            redis_path = redis_url
        
        limiter = Limiter(
            app=app,
            key_func=get_limiter_key,
            default_limits=["1000 per hour", "100 per minute"],
            storage_uri=f"redis://{redis_path}",
            strategy="fixed-window",
            headers_enabled=True
        )
        
        return limiter
    except Exception as e:
        logging.warning(f"Failed to initialize rate limiter: {e}, using memory storage")
        return Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["1000 per hour", "100 per minute"],
            storage_uri="memory://"
        )

