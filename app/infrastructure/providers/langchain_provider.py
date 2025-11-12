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
        self.system_prompt = system_prompt or os.getenv(
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
            
            # Add system message at the beginning
            memory.add_message(SystemMessage(content=self.system_prompt))
            
            self._memories[user_id] = memory
            self._logger.debug(f"Created new memory for user {user_id}")
        
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
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
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
        
        while iteration < max_iterations:
            iteration += 1
            
            # Add assistant message with tool calls
            current_history.append(response)
            
            # Execute tool calls
            tool_messages = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
                    tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
                    
                    # Find tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        try:
                            # Execute tool
                            if isinstance(tool_args, str):
                                tool_args = json.loads(tool_args)
                            result = tool.invoke(tool_args)
                            
                            # Create tool message
                            from langchain_core.messages import ToolMessage
                            tool_messages.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call.get("id", f"call_{iteration}")
                                )
                            )
                        except Exception as e:
                            self._logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                            from langchain_core.messages import ToolMessage
                            tool_messages.append(
                                ToolMessage(
                                    content=f"Error: {str(e)}",
                                    tool_call_id=tool_call.get("id", f"call_{iteration}")
                                )
                            )
            
            # Add tool messages to history
            current_history.extend(tool_messages)
            
            # Get next response from LLM
            if self.chain:
                # Use last few messages for context
                recent_messages = current_history[-10:] if len(current_history) > 10 else current_history
                filtered_history = [msg for msg in recent_messages[:-len(tool_messages)-1] if not isinstance(msg, SystemMessage)]
                
                response = self.chain.invoke({
                    "input": user_message,
                    "chat_history": filtered_history
                })
            else:
                response = self.llm.invoke(current_history)
            
            # Check if there are more tool calls
            if not (hasattr(response, 'tool_calls') and response.tool_calls):
                # Final response
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
