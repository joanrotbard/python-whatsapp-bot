"""Health check endpoints."""
import logging
from flask import Blueprint, jsonify
from app.infrastructure.redis_client import RedisClientFactory
from app.config.settings import Config

health_blueprint = Blueprint("health", __name__)
_logger = logging.getLogger(__name__)


@health_blueprint.route("/health", methods=["GET"])
def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        JSON response with health status
    """
    return jsonify({
        "status": "healthy",
        "service": "whatsapp-bot"
    }), 200


@health_blueprint.route("/health/ready", methods=["GET"])
def readiness_check():
    """
    Readiness check endpoint (checks dependencies).
    
    Returns:
        JSON response with readiness status
    """
    checks = {
        "redis": False,
        "overall": False
    }
    
    # Check Redis connection
    try:
        redis_client = RedisClientFactory.get_client()
        redis_client.ping()
        checks["redis"] = True
    except Exception as e:
        _logger.error(f"Redis health check failed: {e}")
        checks["redis"] = False
    
    # Overall status
    checks["overall"] = checks["redis"]
    
    status_code = 200 if checks["overall"] else 503
    
    return jsonify({
        "status": "ready" if checks["overall"] else "not_ready",
        "checks": checks
    }), status_code


@health_blueprint.route("/health/live", methods=["GET"])
def liveness_check():
    """
    Liveness check endpoint (for Kubernetes).
    
    Returns:
        JSON response with liveness status
    """
    return jsonify({
        "status": "alive",
        "service": "whatsapp-bot"
    }), 200

