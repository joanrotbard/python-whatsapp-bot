"""Monitoring and metrics middleware using Prometheus."""
import logging
from typing import Callable
from flask import request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from app.config.settings import Config

logger = logging.getLogger(__name__)

# Prometheus metrics
messages_received_total = Counter(
    'whatsapp_messages_received_total',
    'Total number of WhatsApp messages received',
    ['status']
)

messages_processed_duration = Histogram(
    'whatsapp_messages_processed_duration_seconds',
    'Time spent processing WhatsApp messages',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

openai_api_calls_total = Counter(
    'openai_api_calls_total',
    'Total number of OpenAI API calls',
    ['operation', 'status']
)

active_threads = Gauge(
    'whatsapp_active_threads',
    'Number of active conversation threads'
)

webhook_requests_total = Counter(
    'whatsapp_webhook_requests_total',
    'Total number of webhook requests',
    ['method', 'endpoint', 'status']
)

webhook_request_duration = Histogram(
    'whatsapp_webhook_request_duration_seconds',
    'Time spent processing webhook requests',
    ['endpoint']
)


def register_metrics_middleware(app) -> None:
    """
    Register Prometheus metrics middleware.
    
    Args:
        app: Flask application instance
    """
    if not Config.ENABLE_METRICS:
        return
    
    # Add metrics endpoint
    @app.route('/metrics')
    def metrics():
        """Prometheus metrics endpoint."""
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    # Wrap app with Prometheus WSGI middleware
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    
    logger.info("Prometheus metrics enabled at /metrics")


def track_webhook_request(endpoint: str):
    """
    Decorator to track webhook request metrics.
    
    Args:
        endpoint: Endpoint name for metrics
    """
    def decorator(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                response = f(*args, **kwargs)
                status_code = response[1] if isinstance(response, tuple) else 200
                
                # Track metrics
                webhook_requests_total.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=status_code
                ).inc()
                
                webhook_request_duration.labels(endpoint=endpoint).observe(
                    time.time() - start_time
                )
                
                return response
            except Exception as e:
                webhook_requests_total.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=500
                ).inc()
                raise
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


def track_message_processing(wa_id: str, success: bool):
    """
    Track message processing metrics.
    
    Args:
        wa_id: WhatsApp user ID
        success: Whether processing was successful
    """
    try:
        if Config.ENABLE_METRICS:
            status = "success" if success else "error"
            messages_received_total.labels(status=status).inc()
    except Exception as e:
        # Don't fail if metrics tracking fails
        logger.debug(f"Failed to track message processing metrics: {e}")


def track_openai_call(operation: str, success: bool):
    """
    Track OpenAI API call metrics.
    
    Args:
        operation: Operation name (e.g., 'create_thread', 'run_assistant')
        success: Whether call was successful
    """
    try:
        if Config.ENABLE_METRICS:
            status = "success" if success else "error"
            openai_api_calls_total.labels(operation=operation, status=status).inc()
    except Exception as e:
        # Don't fail if metrics tracking fails
        logger.debug(f"Failed to track OpenAI call metrics: {e}")

