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
            cls._pool = ConnectionPool.from_url(
                url,
                max_connections=max_connections,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
        return cls._pool
    
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
                pool = cls.create_pool(redis_url)
                cls._client = redis.Redis(connection_pool=pool)
                
                # Test connection
                cls._client.ping()
                logging.info("Redis connection established successfully")
            except (redis.ConnectionError, Exception) as e:
                logging.warning(f"Failed to connect to Redis: {e}")
                logging.warning("Application will continue without Redis (threads won't persist)")
                # Don't raise - allow app to continue without Redis
                # Return None client, services will handle gracefully
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

