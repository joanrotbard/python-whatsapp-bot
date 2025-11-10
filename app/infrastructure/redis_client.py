"""Redis client factory following Dependency Inversion Principle."""
import logging
from typing import Optional
import redis
from redis.connection import ConnectionPool

from app.config.settings import Config


class RedisClientFactory:
    """Factory for creating Redis clients with connection pooling."""
    
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    @classmethod
    def create_pool(cls, url: str, max_connections: int = 50) -> ConnectionPool:
        """
        Create Redis connection pool.
        
        Args:
            url: Redis connection URL
            max_connections: Maximum number of connections in pool
            
        Returns:
            ConnectionPool instance
        """
        if cls._pool is None:
            # Log URL (masked for security)
            masked_url = cls._mask_url(url)
            logging.debug(f"Creating Redis connection pool: {masked_url}")
            
            cls._pool = ConnectionPool.from_url(
                url,
                max_connections=max_connections,
                decode_responses=True,
                socket_connect_timeout=10,  # Increased for Railway
                socket_timeout=10,  # Increased for Railway
                retry_on_timeout=True,
                health_check_interval=30,
                socket_keepalive=True,  # Keep connections alive
                socket_keepalive_options={}  # TCP keepalive options
            )
        return cls._pool
    
    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask sensitive parts of Redis URL for logging."""
        if '@' in url:
            # Mask password: redis://user:password@host -> redis://user:***@host
            parts = url.split('@')
            if len(parts) == 2:
                auth_part = parts[0]
                if ':' in auth_part:
                    scheme_user = auth_part.rsplit(':', 1)[0]
                    return f"{scheme_user}:***@{parts[1]}"
        return url
    
    @classmethod
    def get_client(cls, url: Optional[str] = None) -> Optional[redis.Redis]:
        """
        Get Redis client instance (singleton pattern).
        
        Args:
            url: Optional Redis URL (uses Config if not provided)
            
        Returns:
            Redis client instance or None if connection fails
        """
        if cls._client is None:
            try:
                redis_url = url or Config.REDIS_URL
                
                # Validate URL format
                if not redis_url:
                    logging.warning("REDIS_URL not configured")
                    return None
                
                # Ensure URL has proper scheme
                if not redis_url.startswith(('redis://', 'rediss://', 'unix://')):
                    logging.warning(f"Invalid Redis URL scheme. URL must start with redis://, rediss://, or unix://")
                    logging.warning(f"Got: {redis_url[:50]}...")
                    return None
                
                logging.info(f"Connecting to Redis...")
                pool = cls.create_pool(redis_url)
                cls._client = redis.Redis(connection_pool=pool)
                
                # Test connection with retry
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        cls._client.ping()
                        logging.info("Redis connection established successfully")
                        break
                    except redis.ConnectionError as e:
                        if attempt < max_retries - 1:
                            logging.debug(f"Redis ping failed (attempt {attempt + 1}/{max_retries}), retrying...")
                            import time
                            time.sleep(1)
                        else:
                            raise
                            
            except redis.AuthenticationError as e:
                logging.error(f"Redis authentication failed: {e}")
                logging.error("Check that your REDIS_URL includes username and password if required")
                logging.error("Format: redis://username:password@host:port/db")
                cls._client = None
            except redis.ConnectionError as e:
                logging.warning(f"Failed to connect to Redis: {e}")
                logging.warning("Application will continue without Redis (threads won't persist)")
                cls._client = None
            except Exception as e:
                logging.warning(f"Unexpected error connecting to Redis: {e}", exc_info=True)
                logging.warning("Application will continue without Redis (threads won't persist)")
                cls._client = None
        
        return cls._client
    
    @classmethod
    def close(cls) -> None:
        """Close Redis connections."""
        if cls._client:
            cls._client.close()
            cls._client = None
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None

