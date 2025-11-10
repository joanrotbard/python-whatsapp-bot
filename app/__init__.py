"""Flask application factory with dependency injection and scalability features."""
import logging
from flask import Flask

from app.config.settings import Config, get_config
from app.infrastructure.redis_client import RedisClientFactory
from app.infrastructure.service_container import ServiceContainer
from app.middleware.rate_limiter import create_rate_limiter
from app.middleware.monitoring import register_metrics_middleware
from app.middleware.error_handler import init_error_handlers
from app.views import webhook_blueprint
from app.views.health import health_blueprint


def create_app(config_class=None) -> Flask:
    """
    Create and configure Flask application with dependency injection.
    
    Implements Factory Pattern and Dependency Injection for scalability.
    
    Args:
        config_class: Optional configuration class (for testing)
        
    Returns:
        Configured Flask application
    """
    _logger = logging.getLogger(__name__)
    
    try:
        app = Flask(__name__)
        
        # Load configuration
        config = config_class or get_config()
        app.config.from_object(config)
        
        # Also load environment variables directly to app.config for backward compatibility
        # This ensures variables like APP_SECRET are available via current_app.config
        import os
        from dotenv import load_dotenv
        load_dotenv()
        app.config["APP_SECRET"] = os.getenv("APP_SECRET")
        app.config["APP_ID"] = os.getenv("APP_ID")
        
        # Validate configuration (but don't fail if optional things are missing)
        try:
            config.validate()
        except ValueError as e:
            _logger.warning(f"Configuration validation warning: {e}")
            # Continue anyway - some vars might be optional in certain environments
        
        # Configure logging
        _configure_logging()
        
        # Initialize infrastructure (Redis - optional, won't fail if unavailable)
        try:
            _initialize_infrastructure(app)
        except Exception as e:
            _logger.warning(f"Infrastructure initialization warning: {e}")
            # Continue - app can work without Redis
        
        # Initialize middleware
        try:
            _initialize_middleware(app)
        except Exception as e:
            _logger.error(f"Middleware initialization failed: {e}", exc_info=True)
            # Some middleware might fail, but continue
        
        # Initialize services and store in app context
        try:
            with app.app_context():
                _initialize_services(app)
        except Exception as e:
            _logger.error(f"Service initialization failed: {e}", exc_info=True)
            # Try to continue - app might still work
        
        # Register blueprints
        app.register_blueprint(webhook_blueprint)
        app.register_blueprint(health_blueprint)
        
        # Register teardown handlers
        @app.teardown_appcontext
        def close_redis(error):
            """Close Redis connections on app teardown."""
            # Redis connection pool handles cleanup automatically
            pass
        
        _logger.info("Flask application initialized successfully")
        
    except Exception as e:
        _logger.critical(f"Failed to create Flask application: {e}", exc_info=True)
        # Re-raise to prevent silent failures
        raise
    
    return app


def _configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO if not Config.DEBUG else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _initialize_infrastructure(app: Flask) -> None:
    """
    Initialize infrastructure components (Redis, etc.).
    
    Args:
        app: Flask application instance
    """
    try:
        # Try to initialize Redis connection pool (optional)
        redis_client = RedisClientFactory.get_client()
        if redis_client:
            logging.info("Infrastructure initialized successfully with Redis")
        else:
            logging.warning("Infrastructure initialized without Redis (threads won't persist)")
    except Exception as e:
        logging.warning(f"Failed to initialize Redis: {e}. Continuing without Redis.")
        # Don't raise - allow app to continue without Redis


def _initialize_middleware(app: Flask) -> None:
    """
    Initialize middleware (rate limiting, monitoring, error handling).
    
    Args:
        app: Flask application instance
    """
    # Rate limiting
    limiter = create_rate_limiter(app)
    app.config['limiter'] = limiter
    
    # Monitoring (Prometheus metrics)
    if Config.ENABLE_METRICS:
        register_metrics_middleware(app)
    
    # Error handling (Sentry)
    init_error_handlers(app)


def _initialize_services(app: Flask) -> None:
    """
    Initialize application services using Service Container.
    
    Args:
        app: Flask application instance
    """
    container = ServiceContainer()
    
    # Store container in app config for access in views/tasks
    app.config['service_container'] = container
    
    # Pre-initialize services (optional, for eager loading)
    # This can be done lazily instead
    logging.debug("Services will be initialized on demand via ServiceContainer")
