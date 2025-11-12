"""OpenAI provider implementation using Chat Completions API (Strategy Pattern)."""
import os
import json
import logging
from typing import Optional, Any, List, Dict
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv

from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.conversation_repository import IConversationRepository
from app.domain.interfaces.vertical_manager import IVerticalManager


class OpenAIProvider(IAIProvider):
    """
    OpenAI Chat Completions API provider implementation.
    
    Implements IAIProvider interface following Strategy Pattern.
    Uses Chat Completions API instead of deprecated Assistants API.
    Maintains conversation context in Redis.
    """
    
    def __init__(
        self,
        conversation_repository: IConversationRepository,
        vertical_manager: Optional[IVerticalManager] = None,
        model: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            conversation_repository: Repository for conversation storage
            vertical_manager: Optional vertical manager for function calls
            model: OpenAI model to use (default: gpt-4o-mini)
            system_prompt: Optional system prompt for the assistant
        """
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.api_key)
        self.conversation_repository = conversation_repository
        self.vertical_manager = vertical_manager
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.system_prompt = system_prompt or os.getenv(
            "OPENAI_SYSTEM_PROMPT",
            """You are a friendly and professional travel assistant who helps people manage their flights and bookings. 

            Your main responsibilities are:
            1. Find and suggest flight options based on the traveler’s preferences (origin, destination, travel dates, number of passengers, etc.).
            2. Show details of an existing booking.
            3. Cancel a booking if the traveler requests it (but always confirm first).
            4. Display the traveler’s past or upcoming trips.

            Guidelines:
            - Always reply in the same language the user used in their last message.
            - Sound natural and human — like a helpful travel expert, not a robot.
            - Be clear, warm, and concise. Keep the tone conversational and professional.
            - If you need more details to complete a request, ask politely and naturally.
            - When giving results, organize them neatly (for example, bullet points or short paragraphs).
            - Never invent information. If you don’t have enough data, say so and explain what’s missing.
            - Always double-check before canceling or changing a booking.
            - If the user asks for something that is not related to your main functions (flight search, booking management, or travel history), politely respond: 
            “I’m sorry, but I don’t have the capability to help with that.”
            """
        )
        self._logger = logging.getLogger(__name__)
        self._max_context_messages = 50  # Limit context window
    
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Get conversation thread ID for user (backward compatibility).
        
        For Chat Completions API, we use user_id directly as the conversation identifier.
        This method exists for backward compatibility with the interface.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            User ID (as conversation identifier)
        """
        return user_id
    
    def generate_response(
        self,
        message_body: str,
        user_id: str,
        user_name: str,
        function_handler: Optional[Any] = None
    ) -> str:
        """
        Generate AI response to user message using Chat Completions API.
        
        Args:
            message_body: User's message text
            user_id: Unique user identifier
            user_name: User's display name
            function_handler: Optional handler (not used, kept for interface compatibility)
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If AI service call fails
        """
        # Get or initialize conversation
        messages = self.conversation_repository.get_conversation(user_id)
        
        if messages is None:
            # Initialize new conversation with system prompt
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            self.conversation_repository.save_conversation(user_id, messages)
        else:
            # Check if conversation is too old (older than 1 hour)
            # This is handled by Redis TTL, but we can also check message count
            # Clear old messages if conversation is too long
            if len(messages) > self._max_context_messages:
                self.conversation_repository.clear_old_messages(
                    user_id,
                    keep_last_n=self._max_context_messages
                )
                messages = self.conversation_repository.get_conversation(user_id) or messages
        
        # Add user message
        messages.append({
            "role": "user",
            "content": message_body
        })
        
        # Extend TTL when conversation is used
        self.conversation_repository.extend_ttl(user_id)
        
        # Build tools definition from vertical manager
        tools = self._build_tools_definition()
        
        # Call Chat Completions API
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Prepare API call parameters
                api_params: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                }
                
                # Add tools if available
                if tools:
                    api_params["tools"] = tools
                    api_params["tool_choice"] = "auto"  # Let model decide when to use tools
                
                # Make API call
                response = self.client.chat.completions.create(**api_params)
                
                # Get assistant message
                assistant_message = response.choices[0].message
                
                # Add assistant message to conversation
                assistant_msg_dict: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_message.content or ""
                }
                
                # Handle tool calls if present
                if assistant_message.tool_calls:
                    assistant_msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                    
                    # Save assistant message with tool calls
                    messages.append(assistant_msg_dict)
                    self.conversation_repository.save_conversation(user_id, messages)
                    
                    # Execute function calls
                    tool_messages = self._handle_function_calls(
                        assistant_message.tool_calls,
                        user_id
                    )
                    
                    # Add tool messages to conversation
                    for tool_msg in tool_messages:
                        messages.append(tool_msg)
                    
                    # Continue loop to get final response
                    continue
                
                # No tool calls - we have the final response
                messages.append(assistant_msg_dict)
                self.conversation_repository.save_conversation(user_id, messages)
                
                # Return the response
                return assistant_message.content or "I apologize, but I couldn't generate a response."
                
            except Exception as e:
                self._logger.error(f"Error in Chat Completions API call: {e}", exc_info=True)
                raise
    
    def _build_tools_definition(self) -> Optional[List[Dict[str, Any]]]:
        """
        Build tools definition from handlers for Chat Completions API.
        
        Each handler provides its own schema, eliminating the need for
        hardcoded schemas in the provider.
        
        Returns:
            List of tool definitions in OpenAI format, or None if no handlers
        """
        if not self.vertical_manager:
            return None
        
        handlers = self.vertical_manager.get_all_handlers()
        if not handlers:
            return None
        
        tools = []
        
        # Get schemas directly from handlers
        for handler in handlers.values():
            try:
                schema = handler.get_function_schema()
                tools.append(schema)
                self._logger.debug(
                    f"Added schema for function: {handler.get_function_name()}"
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to get schema from handler {handler.get_function_name()}: {e}",
                    exc_info=True
                )
                # Continue with other handlers even if one fails
        
        return tools if tools else None
    
    def _handle_function_calls(
        self,
        tool_calls: List[Any],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Handle function calls from the assistant.
        
        Args:
            tool_calls: List of tool call objects from OpenAI
            user_id: User ID for function call context
            
        Returns:
            List of tool message dictionaries to add to conversation
        """
        if not self.vertical_manager:
            self._logger.error("Function call received but no vertical manager configured")
            return []
        
        tool_messages = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = tool_call.function.arguments
            
            self._logger.info(f"Handling function call: {function_name} with args: {function_args}")
            
            # Get handler for this function
            handler = self.vertical_manager.get_handler(function_name)
            
            if not handler:
                self._logger.error(f"No handler found for function: {function_name}")
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Function {function_name} not supported"
                    })
                })
                continue
            
            # Parse function arguments
            try:
                if isinstance(function_args, str):
                    parameters = json.loads(function_args)
                else:
                    parameters = function_args
            except json.JSONDecodeError as e:
                self._logger.error(f"Failed to parse function arguments: {e}")
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Invalid function arguments: {str(e)}"
                    })
                })
                continue
            
            # Execute handler
            try:
                result = handler.handle(parameters, user_id=user_id)
                
                # Convert result to JSON string
                result_json = json.dumps(result)
                
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": result_json
                })
                
                self._logger.info(f"Function {function_name} executed successfully")
                
            except Exception as e:
                self._logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Function execution failed: {str(e)}"
                    })
                })
        
        return tool_messages
