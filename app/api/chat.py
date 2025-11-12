"""Chat API endpoints for frontend/UI consumption."""
import logging
from typing import Dict, Any, Tuple
from flask import Blueprint, request, jsonify, current_app

from app.application.services.conversation_service import (
    ConversationService,
    ConversationRequest,
    ConversationResponse
)


chat_blueprint = Blueprint("chat", __name__)
_logger = logging.getLogger(__name__)


def _get_conversation_service() -> ConversationService:
    """
    Get conversation service from service container.
    
    Returns:
        ConversationService instance
        
    Raises:
        RuntimeError: If service container is not available
    """
    container = current_app.config.get('service_container')
    if not container:
        raise RuntimeError("Service container not available")
    
    # Get conversation service (will be added to container)
    if hasattr(container, 'get_conversation_service'):
        return container.get_conversation_service()
    else:
        # Fallback: create service directly
        ai_provider = container.get_ai_provider()
        return ConversationService(ai_provider=ai_provider)


@chat_blueprint.route("/api/chat", methods=["POST"])
def chat():
    """
    Chat API endpoint for frontend/UI consumption.
    
    This endpoint allows any frontend to send messages and receive AI responses.
    It's provider-agnostic and doesn't require WhatsApp or any specific platform.
    
    Expected payload:
    {
        "user_id": "user123",           # Required: Unique user identifier
        "user_name": "John Doe",        # Optional: User's display name
        "message": "Hello, I need help" # Required: User's message
    }
    
    Returns:
        JSON response with AI-generated text:
        {
            "success": true,
            "response": "AI response text here",
            "user_id": "user123",
            "metadata": {...}
        }
    """
    try:
        body = request.get_json()
        
        if not body:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        # Validate required fields
        user_id = body.get("user_id")
        message = body.get("message")
        
        if not user_id:
            return jsonify({
                "success": False,
                "error": "Missing required field: user_id"
            }), 400
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Missing required field: message"
            }), 400
        
        # Get user name (optional, defaults to user_id)
        user_name = body.get("user_name", user_id)
        
        # Create conversation request
        conversation_request = ConversationRequest(
            user_id=user_id,
            user_name=user_name,
            message=message,
            context=body.get("context")  # Optional context
        )
        
        # Get conversation service and process message
        try:
            service = _get_conversation_service()
        except RuntimeError as e:
            _logger.error(f"Service unavailable: {e}")
            return jsonify({
                "success": False,
                "error": "Service temporarily unavailable"
            }), 503
        
        # Process message
        response = service.process_message(conversation_request)
        
        # Build API response
        if response.success:
            return jsonify({
                "success": True,
                "response": response.response_text,
                "user_id": response.user_id,
                "metadata": response.metadata
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": response.error or "Failed to process message",
                "user_id": response.user_id
            }), 500
            
    except Exception as e:
        _logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Internal error: {str(e)}"
        }), 500


@chat_blueprint.route("/api/chat/history/<user_id>", methods=["GET"])
def get_conversation_history(user_id: str):
    """
    Get conversation history for a user.
    
    Args:
        user_id: User identifier (from URL path)
        
    Returns:
        JSON response with conversation history information
    """
    try:
        # Get conversation service
        try:
            service = _get_conversation_service()
        except RuntimeError as e:
            _logger.error(f"Service unavailable: {e}")
            return jsonify({
                "success": False,
                "error": "Service temporarily unavailable"
            }), 503
        
        # Get conversation history
        history = service.get_conversation_history(user_id)
        
        if history:
            return jsonify({
                "success": True,
                "history": history
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve conversation history"
            }), 500
            
    except Exception as e:
        _logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Internal error: {str(e)}"
        }), 500

