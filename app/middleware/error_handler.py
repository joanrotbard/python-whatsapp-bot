"""Error handling middleware with Sentry integration."""
import logging
from flask import jsonify, current_app
from app.config.settings import Config

logger = logging.getLogger(__name__)


def init_error_handlers(app) -> None:
    """
    Initialize error handlers for the application.
    
    Args:
        app: Flask application instance
    """
    # Initialize Sentry if DSN is provided
    if Config.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            
            sentry_sdk.init(
                dsn=Config.SENTRY_DSN,
                integrations=[
                    FlaskIntegration(),
                    CeleryIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=app.config.get("FLASK_ENV", "production"),
            )
            logger.info("Sentry error tracking initialized")
        except ImportError:
            logger.warning("Sentry SDK not installed, skipping Sentry initialization")
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({"status": "error", "message": "Resource not found"}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle rate limit errors."""
        return jsonify({
            "status": "error",
            "message": "Rate limit exceeded. Please try again later."
        }), 429

