"""LangChain-based AI provider implementation (Strategy Pattern).

Uses LangChain for:
- Memory management (replaces Redis conversation storage)
- Tool/function calling
- Chain orchestration
- Streaming support
"""
import os
import json
import logging
import hashlib
from typing import Optional, Dict, Any, List

# Graceful import handling for LangChain dependencies
try:
    from langchain_openai import ChatOpenAI
    from langchain_community.chat_message_histories import ChatMessageHistory
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
    from langchain_core.tools import StructuredTool
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    # Agents removed in LangChain 1.0.0 - using chains with bind_tools instead
    from pydantic import BaseModel, Field, create_model
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    _LANGCHAIN_IMPORT_ERROR = str(e)
    # Create dummy classes for type hints (won't be used if not available)
    ChatOpenAI = None
    ChatMessageHistory = None
    BaseChatMessageHistory = None
    HumanMessage = None
    AIMessage = None
    SystemMessage = None
    BaseMessage = None
    StructuredTool = None
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    RunnableConfig = None
    BaseModel = None
    Field = None
    create_model = None
from dotenv import load_dotenv

from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.vertical_manager import IVerticalManager
from app.infrastructure.providers.response_parsers import get_parser_registry


# Model token limits (context window sizes)
MODEL_TOKEN_LIMITS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
}


def estimate_tokens_from_chars(text: str) -> int:
    """
    Estimate token count from character count.
    
    Uses a conservative estimate: ~4 characters per token for English text.
    For JSON/structured data, this can be more variable, so we use a conservative ratio.
    
    Args:
        text: Text string to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Conservative estimate: 3.5 chars per token (accounts for JSON structure, spaces, etc.)
    return int(len(text) / 3.5)


def get_model_token_limit(model: str) -> int:
    """
    Get the maximum token limit for a given model.
    
    Args:
        model: Model name (e.g., "gpt-4o-mini")
        
    Returns:
        Maximum token limit for the model (default: 128000 for newer models)
    """
    # Check exact match first
    if model in MODEL_TOKEN_LIMITS:
        return MODEL_TOKEN_LIMITS[model]
    
    # Check for partial matches (e.g., "gpt-4o-mini-2024-08-06")
    for model_key, limit in MODEL_TOKEN_LIMITS.items():
        if model.startswith(model_key):
            return limit
    
    # Default to 128000 for newer models (gpt-4o family)
    if "gpt-4o" in model or "gpt-4-turbo" in model:
        return 128000
    
    # Default fallback
    return 128000


def calculate_context_limits(model: str, reserved_tokens: int = 5000) -> Dict[str, int]:
    """
    Calculate dynamic context limits based on model's token limit.
    
    Args:
        model: Model name
        reserved_tokens: Tokens to reserve for system messages, user messages, 
                        assistant responses, and other overhead (default: 20000)
        
    Returns:
        Dictionary with calculated limits:
        - max_total_tokens: Maximum tokens for the entire context
        - max_tool_message_tokens: Maximum tokens for a single tool message
        - max_tool_message_chars: Maximum characters for a single tool message
        - max_flights_in_context: Maximum number of flights to include
        - max_chars_per_flight: Maximum characters per flight context string
        - max_history_messages: Maximum number of messages in history
    """
    max_tokens = get_model_token_limit(model)
    
    # Reserve tokens for system, user messages, assistant responses, and overhead
    available_tokens = max_tokens - reserved_tokens
    
    # Allocate tokens for tool messages (60% of available)
    max_tool_message_tokens = int(available_tokens * 0.6)
    
    # Convert tokens to characters (conservative: 3.5 chars per token)
    max_tool_message_chars = int(max_tool_message_tokens * 3.5)
    
    # Estimate max flights: each flight context string is ~500-2000 chars
    # Use average of 1500 chars per flight
    avg_chars_per_flight = 1500
    estimated_tokens_per_flight = estimate_tokens_from_chars("x" * avg_chars_per_flight)
    max_flights_in_context = max(5, int(max_tool_message_tokens / estimated_tokens_per_flight))
    
    # Limit individual flight strings to prevent any single flight from being too large
    max_chars_per_flight = min(2000, int(max_tool_message_chars / max_flights_in_context))
    
    # Limit history messages based on available tokens
    # Estimate ~500 tokens per message (user + assistant)
    estimated_tokens_per_message = 500
    max_history_messages = max(5, int(available_tokens * 0.4 / estimated_tokens_per_message))
    
    return {
        "max_total_tokens": max_tokens,
        "max_tool_message_tokens": max_tool_message_tokens,
        "max_tool_message_chars": max_tool_message_chars,
        "max_flights_in_context": max_flights_in_context,
        "max_chars_per_flight": max_chars_per_flight,
        "max_history_messages": max_history_messages,
    }


class LangChainProvider(IAIProvider):
    """
    LangChain-based AI provider implementation.
    
    Uses LangChain for memory management, tool calling, and chain orchestration.
    Replaces Redis-based conversation storage with LangChain's memory system.
    """
    
    def __init__(
        self,
        vertical_manager: Optional[IVerticalManager] = None,
        model: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None,
        memory_type: str = "buffer",  # "buffer" or "summary"
        max_token_limit: int = 2000  # For summary memory
    ):
        """
        Initialize LangChain provider.
        
        Args:
            vertical_manager: Optional vertical manager for function handlers
            model: OpenAI model to use (default: gpt-4o-mini)
            system_prompt: Optional system prompt for the assistant
            memory_type: Type of memory ("buffer" or "summary")
            max_token_limit: Max tokens for summary memory
            
        Raises:
            ImportError: If LangChain dependencies are not installed
            ValueError: If OPENAI_API_KEY is not found
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                f"LangChain dependencies are not installed. "
                f"Please install them with: pip install langchain langchain-openai langchain-core pydantic\n"
                f"Original error: {_LANGCHAIN_IMPORT_ERROR}"
            )
        
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.vertical_manager = vertical_manager
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._base_system_prompt = system_prompt or os.getenv(
            "OPENAI_SYSTEM_PROMPT",
            """You are a friendly and professional travel assistant who helps people manage their flights and bookings. 

            Your main responsibilities are:
            1. Find and suggest flight options based on the traveler's preferences (origin, destination, travel dates, number of passengers, etc.).
            2. Show details of an existing booking.
            3. Cancel a booking if the traveler requests it (but always confirm first).
            4. Display the traveler's past or upcoming trips.

            Guidelines:
            - Always reply in the same language the user used in their last message.
            - Sound natural and human — like a helpful travel expert, not a robot.
            - Be clear, warm, and concise. Keep the tone conversational and professional.
            - If you need more details to complete a request, ask politely and naturally.
            - When giving results, organize them neatly (for example, bullet points or short paragraphs).
            - Never invent information. If you don't have enough data, say so and explain what's missing.
            - Always double-check before canceling or changing a booking.
            - If the user asks for something that is not related to your main functions (flight search, booking management, or travel history), politely respond: 
            "I'm sorry, but I don't have the capability to help with that."
            """
        )
        # Store base prompt, actual system_prompt will be generated dynamically with current date
        self.system_prompt = self._base_system_prompt
        self._logger = logging.getLogger(__name__)
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=0.7,
            api_key=self.api_key
        )
        
        # Initialize memory storage (per user)
        # In LangChain 1.0.0, we use ChatMessageHistory instead of ConversationBufferMemory
        self._memories: Dict[str, ChatMessageHistory] = {}
        self.memory_type = memory_type  # For future use (summary memory)
        self.max_token_limit = max_token_limit
        
        # Calculate dynamic context limits based on model
        self.context_limits = calculate_context_limits(self.model)
        self._logger.info(
            f"Context limits for model {self.model}: "
            f"max_tool_message_chars={self.context_limits['max_tool_message_chars']}, "
            f"max_flights={self.context_limits['max_flights_in_context']}, "
            f"max_history_messages={self.context_limits['max_history_messages']}"
        )
        
        # Store current user_id for tool execution context
        self._current_user_id: Optional[str] = None
        
        # Build tools from handlers
        self.tools = []
        self._build_langchain_tools()
        
        # Build chain with tools if available
        # In LangChain 1.0.0, we use bind_tools instead of agents
        if self.tools:
            self.chain = self._build_chain()
        else:
            self.chain = None
    
    def _get_system_prompt_with_date(self) -> str:
        """
        Get system prompt with current date information.
        
        Returns:
            System prompt string with current date context
        """
        from datetime import date, datetime
        today = date.today()
        today_str = today.strftime("%A, %B %d, %Y")  # e.g., "Friday, November 15, 2024"
        today_iso = today.strftime("%Y-%m-%d")  # e.g., "2024-11-15"
        
        date_context = f"""
IMPORTANT DATE CONTEXT:
- Today's date is: {today_str} ({today_iso})
- When users ask about dates (e.g., "what day is tomorrow?", "what is today's date?"), use this current date as reference.
- When users use relative date expressions like "mañana", "tomorrow", "el martes que viene", etc., calculate from today's date: {today_iso}
- Always use the current date ({today_iso}) as the reference point for all relative date calculations.
"""
        
        return self._base_system_prompt + date_context
    
    def _get_memory(self, user_id: str) -> ChatMessageHistory:
        """
        Get or create memory for a user.
        
        In LangChain 1.0.0, we use ChatMessageHistory which stores messages directly.
        
        Args:
            user_id: User identifier
            
        Returns:
            ChatMessageHistory instance
        """
        if user_id not in self._memories:
            # Create new chat message history
            memory = ChatMessageHistory()
            
            # Add system message with current date at the beginning
            system_prompt_with_date = self._get_system_prompt_with_date()
            memory.add_message(SystemMessage(content=system_prompt_with_date))
            
            self._memories[user_id] = memory
            self._logger.debug(f"Created new memory for user {user_id} with current date context")
        else:
            # Update system message with current date if it exists
            # This ensures the date is always current, even for existing conversations
            memory = self._memories[user_id]
            # Find and update system message if it exists
            for i, msg in enumerate(memory.messages):
                if isinstance(msg, SystemMessage):
                    system_prompt_with_date = self._get_system_prompt_with_date()
                    memory.messages[i] = SystemMessage(content=system_prompt_with_date)
                    self._logger.debug(f"Updated system message with current date for user {user_id}")
                    break
        
        return self._memories[user_id]
    
    def _build_langchain_tools(self) -> None:
        """Build LangChain tools from function handlers."""
        if not self.vertical_manager:
            return
        
        handlers = self.vertical_manager.get_all_handlers()
        if not handlers:
            return
        
        for handler in handlers.values():
            try:
                tool = self._create_tool_from_handler(handler)
                if tool:
                    self.tools.append(tool)
                    self._logger.debug(f"Created LangChain tool: {tool.name}")
            except Exception as e:
                self._logger.error(
                    f"Failed to create LangChain tool from handler {handler.get_function_name()}: {e}",
                    exc_info=True
                )
                continue
    
    def _create_tool_from_handler(self, handler) -> Optional[StructuredTool]:
        """
        Create a LangChain tool from a function handler.
        
        Args:
            handler: IFunctionHandler instance
            
        Returns:
            StructuredTool instance or None
        """
        schema = handler.get_function_schema()
        function_def = schema.get("function", {})
        function_name = function_def.get("name")
        function_description = function_def.get("description", "")
        params_schema = function_def.get("parameters", {})
        properties = params_schema.get("properties", {})
        required = params_schema.get("required", [])
        
        # Create Pydantic model for tool arguments
        field_definitions = {}
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string")
            prop_desc = prop_def.get("description", "")
            
            # Map JSON schema types to Python types
            if prop_type == "string":
                field_type = str
            elif prop_type == "integer":
                field_type = int
            elif prop_type == "number":
                field_type = float
            elif prop_type == "boolean":
                field_type = bool
            else:
                field_type = str
            
            # Create field with description
            if prop_name in required:
                field_definitions[prop_name] = (
                    field_type,
                    Field(description=prop_desc)
                )
            else:
                field_definitions[prop_name] = (
                    Optional[field_type],
                    Field(default=None, description=prop_desc)
                )
        
        # Create Pydantic model
        ToolInputModel = create_model(
            f"{function_name}Input",
            **field_definitions
        )
        
        # Create tool function that captures user_id from context
        def tool_func(**kwargs) -> str:
            """Tool function that uses current user_id from context."""
            user_id = self._current_user_id or ""
            try:
                result = handler.handle(kwargs, user_id=user_id)
                # Convert result to JSON string for LangChain
                return json.dumps(result, default=str)
            except Exception as e:
                self._logger.error(f"Error in tool {function_name}: {e}", exc_info=True)
                return json.dumps({"success": False, "error": str(e)})
        
        # Create StructuredTool
        tool = StructuredTool(
            name=function_name,
            description=function_description,
            func=tool_func,
            args_schema=ToolInputModel
        )
        
        return tool
    
    def _build_chain(self):
        """
        Build LangChain chain with tools.
        
        In LangChain 1.0.0, we use bind_tools() instead of agents.
        
        Returns:
            Runnable chain or None
        """
        if not self.tools:
            return None
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Create prompt template
        # Get system prompt with current date
        system_prompt_with_date = self._get_system_prompt_with_date()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_with_date),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        
        # Create chain: prompt -> llm_with_tools
        chain = prompt | llm_with_tools
        
        return chain
    
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Get conversation thread ID for user (backward compatibility).
        
        For LangChain, we use user_id directly as the conversation identifier.
        
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
        Generate AI response using LangChain.
        
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
        try:
            # Set current user_id for tool context
            self._current_user_id = user_id
            
            # Get or create memory for user
            memory = self._get_memory(user_id)
            
            # Add user message to memory first
            memory.add_user_message(message_body)
            
            # Get conversation history
            chat_history = memory.messages
            
            # If we have a chain with tools, use it
            if self.chain:
                # Prepare input for chain
                # Filter out system message from chat history
                filtered_history = [
                    msg for msg in chat_history[:-1]  # Exclude the just-added user message
                    if not isinstance(msg, SystemMessage)
                ]
                
                # Invoke chain
                response = self.chain.invoke({
                    "input": message_body,
                    "chat_history": filtered_history
                })
                
                # Handle tool calls if present
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Execute tool calls and get final response
                    response_text = self._handle_tool_calls(response, chat_history, message_body)
                else:
                    # Extract response text
                    response_text = response.content if hasattr(response, 'content') else str(response)
                
            else:
                # No tools - simple LLM call with memory
                messages = chat_history
                response = self.llm.invoke(messages)
                response_text = response.content
            
            # Add assistant response to memory
            memory.add_ai_message(response_text)
            
            return response_text
            
        except Exception as e:
            self._logger.error(f"Error generating response with LangChain: {e}", exc_info=True)
            raise
        finally:
            # Clear current user_id
            self._current_user_id = None
    
    def _handle_tool_calls(
        self,
        response: Any,
        chat_history: List[BaseMessage],
        user_message: str
    ) -> str:
        """
        Handle tool calls from LLM response.
        
        Args:
            response: LLM response with tool calls
            chat_history: Current conversation history
            user_message: Original user message
            
        Returns:
            Final response text after tool execution
        """
        max_iterations = 10
        iteration = 0
        current_history = chat_history.copy()
        
        # Track executed searches by payload hash to prevent duplicates across iterations
        executed_searches = set()
        # Track all executed tool call IDs across all iterations to prevent re-execution
        all_executed_tool_call_ids = set()
        
        while iteration < max_iterations:
            iteration += 1
            
            self._logger.info(f"Iteration {iteration}: Starting tool call handling")
            
            # Add assistant message with tool calls
            current_history.append(response)
            
            # Execute tool calls
            tool_messages = []
            executed_tool_calls = set()  # Track executed tool calls to avoid duplicates within iteration
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Check if these are the same tool calls we already executed in previous iterations
                current_tool_call_ids = {
                    tool_call.get("id") or f"call_{iteration}_{tool_call.get('name') or tool_call.get('function', {}).get('name', '')}"
                    for tool_call in response.tool_calls
                }
                
                # If we already executed these tool calls in a previous iteration, skip them
                if current_tool_call_ids.intersection(all_executed_tool_call_ids):
                    duplicate_ids = current_tool_call_ids.intersection(all_executed_tool_call_ids)
                    self._logger.warning(
                        f"Iteration {iteration}: Detected tool calls that were already executed in previous iteration. "
                        f"Duplicate IDs: {duplicate_ids}. Skipping and returning final response."
                    )
                    # Return a response instead of continuing
                    final_response = response.content if hasattr(response, 'content') else str(response)
                    if not final_response or final_response.strip() == "":
                        final_response = "I've completed the requested action. Here are the results."
                    return final_response
                
                self._logger.info(f"Iteration {iteration}: Processing {len(response.tool_calls)} tool call(s)")
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
                    tool_call_id = tool_call.get("id", f"call_{iteration}_{tool_name}")
                    
                    # Skip if we've already executed this exact tool call in this iteration
                    if tool_call_id in executed_tool_calls:
                        self._logger.warning(f"Skipping duplicate tool call: {tool_name} (ID: {tool_call_id})")
                        continue
                    
                    # Skip if we've already executed this tool call in a previous iteration
                    if tool_call_id in all_executed_tool_call_ids:
                        self._logger.warning(
                            f"Skipping tool call already executed in previous iteration: {tool_name} (ID: {tool_call_id})"
                        )
                        continue
                    
                    tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
                    
                    # For search_flights, check if we've already executed a similar search
                    if tool_name == "search_flights":
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except json.JSONDecodeError:
                                pass
                        
                        # Create a hash of the search parameters to detect duplicates
                        search_key = json.dumps(tool_args, sort_keys=True, default=str)
                        search_hash = hashlib.md5(search_key.encode()).hexdigest()
                        
                        if search_hash in executed_searches:
                            self._logger.warning(
                                f"Skipping duplicate search_flights call (hash: {search_hash[:8]}) - "
                                f"already executed in this conversation"
                            )
                            # Return a message indicating the search was already done
                            from langchain_core.messages import ToolMessage
                            tool_messages.append(
                                ToolMessage(
                                    content=json.dumps({
                                        "success": False,
                                        "error": "Duplicate search",
                                        "message": "This flight search was already performed. Please wait for the previous search to complete."
                                    }),
                                    tool_call_id=tool_call_id
                                )
                            )
                            continue
                        
                        executed_searches.add(search_hash)
                    
                    self._logger.info(f"Executing tool: {tool_name} (ID: {tool_call_id})")
                    
                    # Find tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        try:
                            # Execute tool
                            if isinstance(tool_args, str):
                                try:
                                    tool_args = json.loads(tool_args)
                                except json.JSONDecodeError:
                                    pass
                            result = tool.invoke(tool_args)
                            executed_tool_calls.add(tool_call_id)  # Mark as executed in this iteration
                            all_executed_tool_call_ids.add(tool_call_id)  # Mark as executed across all iterations
                            
                            # Parse result if it's a JSON string
                            if isinstance(result, str):
                                try:
                                    result = json.loads(result)
                                except json.JSONDecodeError:
                                    # If it's not valid JSON, keep it as string
                                    pass
                            
                            # Try to parse/transform the result using registered parsers
                            parser_registry = get_parser_registry()
                            parsed_result = parser_registry.parse_result(tool_name, result)
                            
                            # Truncate large contexts before creating tool message
                            # For search_flights, truncate all_flights_context if too large
                            if isinstance(parsed_result, dict) and tool_name == "search_flights":
                                if "all_flights_context" in parsed_result:
                                    context_list = parsed_result.get("all_flights_context", [])
                                    if isinstance(context_list, list):
                                        # Use dynamic limit based on model token capacity
                                        max_flights_in_context = self.context_limits["max_flights_in_context"]
                                        if len(context_list) > max_flights_in_context:
                                            self._logger.warning(
                                                f"Truncating flight context from {len(context_list)} to {max_flights_in_context} flights "
                                                f"(based on model {self.model} token limit)"
                                            )
                                            parsed_result["all_flights_context"] = context_list[:max_flights_in_context]
                                    
                                    # Also truncate individual context strings if too long
                                    if isinstance(context_list, list):
                                        max_chars_per_flight = self.context_limits["max_chars_per_flight"]
                                        truncated_list = []
                                        for flight_ctx in context_list:
                                            if isinstance(flight_ctx, str) and len(flight_ctx) > max_chars_per_flight:
                                                truncated_list.append(flight_ctx[:max_chars_per_flight] + "... [truncated]")
                                            else:
                                                truncated_list.append(flight_ctx)
                                        parsed_result["all_flights_context"] = truncated_list
                            
                            # Create tool message
                            from langchain_core.messages import ToolMessage
                            if parsed_result is not None:
                                # Use parsed result if a parser handled it
                                # If there's a formatting instruction, make it prominent
                                if isinstance(parsed_result, dict) and "formatting_instruction" in parsed_result:
                                    # Format the message to make instruction clear to LLM
                                    instruction = parsed_result.get("formatting_instruction")
                                    # Create a copy without the instruction for the JSON result
                                    result_copy = {k: v for k, v in parsed_result.items() if k != "formatting_instruction"}
                                    
                                    # Truncate the entire tool message content if too large
                                    tool_message_content = json.dumps(result_copy)
                                    max_tool_message_size = self.context_limits["max_tool_message_chars"]
                                    if len(tool_message_content) > max_tool_message_size:
                                        estimated_tokens = estimate_tokens_from_chars(tool_message_content)
                                        self._logger.warning(
                                            f"Truncating tool message content from {len(tool_message_content)} chars "
                                            f"(~{estimated_tokens} tokens) to {max_tool_message_size} chars "
                                            f"(~{self.context_limits['max_tool_message_tokens']} tokens)"
                                        )
                                        # Try to preserve the structure while truncating
                                        if "all_flights_context" in result_copy:
                                            # Truncate the context list more aggressively
                                            context_list = result_copy.get("all_flights_context", [])
                                            if isinstance(context_list, list):
                                                # Keep only first 5 flights as last resort
                                                aggressive_limit = 5
                                                result_copy["all_flights_context"] = context_list[:aggressive_limit]
                                                result_copy["message"] = (
                                                    result_copy.get("message", "") + 
                                                    f" [Showing top {aggressive_limit} of {result_copy.get('total_flights_count', 'many')} flights due to context limits]"
                                                )
                                        tool_message_content = json.dumps(result_copy)
                                        if len(tool_message_content) > max_tool_message_size:
                                            # Last resort: truncate the JSON string itself
                                            tool_message_content = tool_message_content[:max_tool_message_size] + "... [truncated]"
                                    
                                    # Prepend instruction as a clear directive
                                    tool_message_content = (
                                        f"FORMATTING_INSTRUCTIONS:\n{instruction}\n\n"
                                        f"TOOL_RESULT:\n{tool_message_content}"
                                    )
                                else:
                                    tool_message_content = json.dumps(parsed_result)
                                    # Truncate if too large
                                    max_tool_message_size = self.context_limits["max_tool_message_chars"]
                                    if len(tool_message_content) > max_tool_message_size:
                                        estimated_tokens = estimate_tokens_from_chars(tool_message_content)
                                        self._logger.warning(
                                            f"Truncating tool message content from {len(tool_message_content)} chars "
                                            f"(~{estimated_tokens} tokens) to {max_tool_message_size} chars"
                                        )
                                        tool_message_content = tool_message_content[:max_tool_message_size] + "... [truncated]"
                            else:
                                # Use original result if no parser handled it or parsing failed
                                tool_message_content = json.dumps(result) if isinstance(result, dict) else str(result)
                                # Truncate if too large
                                max_tool_message_size = self.context_limits["max_tool_message_chars"]
                                if len(tool_message_content) > max_tool_message_size:
                                    estimated_tokens = estimate_tokens_from_chars(tool_message_content)
                                    self._logger.warning(
                                        f"Truncating tool message content from {len(tool_message_content)} chars "
                                        f"(~{estimated_tokens} tokens) to {max_tool_message_size} chars"
                                    )
                                    tool_message_content = tool_message_content[:max_tool_message_size] + "... [truncated]"
                            
                            tool_messages.append(
                                ToolMessage(
                                    content=tool_message_content,
                                    tool_call_id=tool_call_id
                                )
                            )
                        except Exception as e:
                            self._logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                            from langchain_core.messages import ToolMessage
                            tool_messages.append(
                                ToolMessage(
                                    content=f"Error: {str(e)}",
                                    tool_call_id=tool_call_id
                                )
                            )
            
            # Add tool messages to history
            current_history.extend(tool_messages)
            
            # If we executed tool calls, we need to get the LLM's response to those results
            # But only if we actually executed tools (not if we skipped duplicates)
            if tool_messages:
                self._logger.info(f"Iteration {iteration}: Executed {len(tool_messages)} tool message(s), getting LLM response")
                
                # Get next response from LLM
                if self.chain:
                    # Limit history to prevent context overflow
                    # Keep only recent messages and truncate very long tool messages
                    max_history_messages = self.context_limits["max_history_messages"]
                    recent_messages = current_history[-max_history_messages:] if len(current_history) > max_history_messages else current_history
                    
                    # Create a copy of messages and truncate very long tool messages to prevent token overflow
                    # We don't modify the original history, only the copy we send to the LLM
                    # Include: user message, assistant message with tool calls, and tool messages
                    filtered_messages = []
                    
                    # Get messages from recent history, excluding the tool messages we just added
                    # We want: [previous messages..., user_message, assistant_message_with_tool_calls, tool_messages]
                    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
                    
                    # Get all messages except the tool messages we just added (they're at the end)
                    messages_before_tools = recent_messages[:-len(tool_messages)] if tool_messages else recent_messages
                    
                    for msg in messages_before_tools:
                        if isinstance(msg, SystemMessage):
                            continue
                        
                        # Include user messages and assistant messages
                        if isinstance(msg, (HumanMessage, AIMessage)):
                            filtered_messages.append(msg)
                        
                        # Handle existing tool messages (from previous iterations) - truncate if needed
                        if isinstance(msg, ToolMessage) and hasattr(msg, 'content') and isinstance(msg.content, str):
                            try:
                                content_dict = json.loads(msg.content)
                                # If it's a tool message with all_flights_context, truncate it
                                if isinstance(content_dict, dict) and 'all_flights_context' in content_dict:
                                    context_list = content_dict.get('all_flights_context', [])
                                    max_flights = self.context_limits["max_flights_in_context"]
                                    if isinstance(context_list, list) and len(context_list) > max_flights:
                                        # Limit to max flights based on model token capacity
                                        content_dict_copy = content_dict.copy()
                                        content_dict_copy['all_flights_context'] = context_list[:max_flights]
                                        content_dict_copy['message'] = (
                                            content_dict_copy.get('message', '') + 
                                            f" [Showing top {max_flights} of {content_dict_copy.get('total_flights_count', 'many')} flights]"
                                        )
                                        # Create a new message with truncated content
                                        filtered_messages.append(
                                            ToolMessage(
                                                content=json.dumps(content_dict_copy),
                                                tool_call_id=msg.tool_call_id
                                            )
                                        )
                                        self._logger.warning(
                                            f"Truncated flight context from {len(context_list)} to {max_flights} flights "
                                            f"to prevent token overflow (model: {self.model})"
                                        )
                                        continue
                                    elif isinstance(context_list, list):
                                        # Also truncate individual flight strings if too long
                                        max_chars_per_flight = self.context_limits["max_chars_per_flight"]
                                        truncated_list = []
                                        for flight_ctx in context_list:
                                            if isinstance(flight_ctx, str) and len(flight_ctx) > max_chars_per_flight:
                                                truncated_list.append(flight_ctx[:max_chars_per_flight] + "... [truncated]")
                                            else:
                                                truncated_list.append(flight_ctx)
                                        if truncated_list != context_list:
                                            content_dict_copy = content_dict.copy()
                                            content_dict_copy['all_flights_context'] = truncated_list
                                            filtered_messages.append(
                                                ToolMessage(
                                                    content=json.dumps(content_dict_copy),
                                                    tool_call_id=msg.tool_call_id
                                                )
                                            )
                                            self._logger.warning("Truncated individual flight context strings")
                                            continue
                                    
                                    # Also check total message size
                                    msg_content_str = json.dumps(content_dict)
                                    max_tool_message_chars = self.context_limits["max_tool_message_chars"]
                                    if len(msg_content_str) > max_tool_message_chars:
                                        # Aggressively truncate
                                        if isinstance(context_list, list):
                                            aggressive_limit = 5
                                            content_dict_copy = content_dict.copy()
                                            content_dict_copy['all_flights_context'] = context_list[:aggressive_limit]
                                            content_dict_copy['message'] = (
                                                content_dict_copy.get('message', '') + 
                                                f" [Showing top {aggressive_limit} of {content_dict_copy.get('total_flights_count', 'many')} flights due to context limits]"
                                            )
                                            filtered_messages.append(
                                                ToolMessage(
                                                    content=json.dumps(content_dict_copy),
                                                    tool_call_id=msg.tool_call_id
                                                )
                                            )
                                            estimated_tokens = estimate_tokens_from_chars(msg_content_str)
                                            self._logger.warning(
                                                f"Aggressively truncated flight context to prevent token overflow "
                                                f"(message was ~{estimated_tokens} tokens, limit: {self.context_limits['max_tool_message_tokens']})"
                                            )
                                            continue
                            except (json.JSONDecodeError, AttributeError):
                                pass
                            
                            # Include existing tool messages as-is if no truncation needed
                            filtered_messages.append(msg)
                    
                    # Add the tool messages we just created to filtered history
                    filtered_messages.extend(tool_messages)
                    filtered_history = filtered_messages
                    
                    self._logger.debug(
                        f"Iteration {iteration}: Sending to LLM - "
                        f"{len(filtered_history)} messages in history "
                        f"({sum(1 for m in filtered_history if isinstance(m, HumanMessage))} user, "
                        f"{sum(1 for m in filtered_history if isinstance(m, AIMessage))} assistant, "
                        f"{sum(1 for m in filtered_history if isinstance(m, ToolMessage))} tool)"
                    )
                    
                    # After tool execution, invoke the LLM directly with the history
                    # Include the assistant message with tool calls and the tool messages
                    # The LLM should respond to the tool results, not make new tool calls
                    # Use the last user message as context, but the LLM should focus on tool results
                    response = self.chain.invoke({
                        "input": user_message,  # Keep user message for context
                        "chat_history": filtered_history
                    })
                else:
                    response = self.llm.invoke(current_history)
                
                # Check if there are more tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Check if these are the same tool calls we just executed
                    new_tool_call_ids = {
                        tool_call.get("id") or f"call_{iteration}_{tool_call.get('name') or tool_call.get('function', {}).get('name', '')}"
                        for tool_call in response.tool_calls
                    }
                    
                    # If these are the same tool calls we just executed in this iteration, something is wrong
                    if new_tool_call_ids.intersection(executed_tool_calls):
                        self._logger.warning(
                            f"Iteration {iteration}: LLM requested tool calls that were already executed in this iteration. "
                            f"Duplicate IDs: {new_tool_call_ids.intersection(executed_tool_calls)}. "
                            f"Returning final response instead."
                        )
                        # Return the response content instead of making another tool call
                        final_response = response.content if hasattr(response, 'content') else str(response)
                        if not final_response or final_response.strip() == "":
                            # If no content, create a response from tool results
                            final_response = "I've completed the flight search. Here are the results."
                        return final_response
                    
                    # If these are tool calls we executed in a previous iteration, skip them
                    if new_tool_call_ids.intersection(all_executed_tool_call_ids):
                        self._logger.warning(
                            f"Iteration {iteration}: LLM requested tool calls that were already executed in previous iteration. "
                            f"Duplicate IDs: {new_tool_call_ids.intersection(all_executed_tool_call_ids)}. "
                            f"Returning final response instead."
                        )
                        # Return the response content instead of making another tool call
                        final_response = response.content if hasattr(response, 'content') else str(response)
                        if not final_response or final_response.strip() == "":
                            # If no content, create a response from tool results
                            final_response = "I've completed the requested action. Here are the results."
                        return final_response
                    
                    self._logger.info(
                        f"Iteration {iteration}: LLM requested {len(response.tool_calls)} more tool call(s). "
                        f"Tool call IDs: {new_tool_call_ids}"
                    )
                    # Continue loop to handle new tool calls
                    continue
                else:
                    # Final response - no more tool calls
                    final_response = response.content if hasattr(response, 'content') else str(response)
                    self._logger.info(f"Iteration {iteration}: Final response received (no more tool calls)")
                    return final_response
            else:
                # No tool messages were created (all were skipped as duplicates)
                # This shouldn't happen, but if it does, return the original response
                self._logger.warning(f"Iteration {iteration}: No tool messages created, returning original response")
                return response.content if hasattr(response, 'content') else str(response)
        
        # Max iterations reached
        self._logger.warning("Max iterations reached in tool calling")
        return response.content if hasattr(response, 'content') else str(response)
    
    def clear_memory(self, user_id: str) -> None:
        """
        Clear conversation memory for a user.
        
        Args:
            user_id: User identifier
        """
        if user_id in self._memories:
            del self._memories[user_id]
            self._logger.info(f"Cleared memory for user {user_id}")
