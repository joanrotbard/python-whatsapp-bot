"""Views module - exports all blueprints."""
from app.views.webhook import webhook_blueprint
from app.views.health import health_blueprint

__all__ = ["webhook_blueprint", "health_blueprint"]
