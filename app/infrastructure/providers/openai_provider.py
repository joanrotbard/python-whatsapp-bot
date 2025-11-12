"""OpenAI provider implementation (Strategy Pattern)."""
import os
import time
import logging
from typing import Optional
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv

from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository


class OpenAIProvider(IAIProvider):
    """
    OpenAI Assistants API provider implementation.
    
    Implements IAIProvider interface following Strategy Pattern.
    """
    
    def __init__(self, thread_repository: IThreadRepository):
        """
        Initialize OpenAI provider.
        
        Args:
            thread_repository: Repository for thread storage
        """
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        if not self.assistant_id:
            raise ValueError("OPENAI_ASSISTANT_ID not found in environment")
        
        self.client = OpenAI(api_key=self.api_key)
        self.thread_repository = thread_repository
        self._logger = logging.getLogger(__name__)
        self._assistant_cache = None
    
    def _get_assistant(self):
        """Get assistant with caching."""
        if self._assistant_cache is None:
            self._assistant_cache = self.client.beta.assistants.retrieve(self.assistant_id)
        return self._assistant_cache
    
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Get conversation thread ID for user.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Thread ID if exists, None otherwise
        """
        return self.thread_repository.get_thread_id(user_id)
    
    def generate_response(self, message_body: str, user_id: str, user_name: str) -> str:
        """
        Generate AI response to user message.
        
        Args:
            message_body: User's message text
            user_id: Unique user identifier
            user_name: User's display name
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If AI service call fails
        """
        # Get or create thread
        thread_id = self.thread_repository.get_thread_id(user_id)
        
        if thread_id is None:
            # Create new thread
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            try:
                self.thread_repository.save_thread_id(user_id, thread_id)
            except Exception:
                pass  # Non-critical
        else:
            # Check if thread has messages from the last hour
            if not self._has_recent_messages(thread_id, hours=1):
                # Thread is too old, create a new one
                self._logger.info(f"Thread {thread_id} has no recent messages, creating new thread for {user_id}")
                try:
                    self.thread_repository.delete_thread(user_id)
                except Exception:
                    pass  # Non-critical
                
                thread = self.client.beta.threads.create()
                thread_id = thread.id
                try:
                    self.thread_repository.save_thread_id(user_id, thread_id)
                except Exception:
                    pass  # Non-critical
            else:
                # Thread has recent messages, use it
                # Extend TTL when thread is used
                try:
                    self.thread_repository.extend_ttl(user_id)
                except Exception:
                    pass  # Non-critical
                
                # Wait for any active runs to complete
                self._wait_for_active_runs(thread_id)
        
        # Add user message to thread with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=message_body
                )
                break
            except Exception as e:
                if "active" in str(e).lower() and "run" in str(e).lower():
                    if attempt < max_retries - 1:
                        self._wait_for_active_runs(thread_id, max_wait_time=10)
                    else:
                        raise
                else:
                    raise
        
        # Run assistant and get response
        response = self._run_assistant_optimized(thread_id)
        return response
    
    def _has_recent_messages(self, thread_id: str, hours: int = 1) -> bool:
        """
        Check if thread has messages from the last N hours.
        
        Args:
            thread_id: OpenAI thread ID
            hours: Number of hours to look back (default: 1)
            
        Returns:
            True if thread has messages from the last hour, False otherwise
        """
        try:
            # Calculate cutoff time (1 hour ago)
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # Get recent messages (limit to last 10 for efficiency)
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                limit=10,
                order="desc"
            )
            
            if not messages.data:
                return False
            
            # Check if any message is from the last hour
            for message in messages.data:
                # Message created_at is a Unix timestamp (integer)
                message_timestamp = message.created_at
                # Convert to int if it's not already (handles different formats)
                if isinstance(message_timestamp, (int, float)):
                    message_ts = int(message_timestamp)
                else:
                    # If it's a datetime object or string, parse it
                    try:
                        if hasattr(message_timestamp, 'timestamp'):
                            message_ts = int(message_timestamp.timestamp())
                        else:
                            # Assume it's already a timestamp
                            message_ts = int(message_timestamp)
                    except (ValueError, TypeError):
                        continue  # Skip this message if we can't parse it
                
                if message_ts >= cutoff_timestamp:
                    return True
            
            return False
        except Exception as e:
            self._logger.warning(f"Error checking recent messages for thread {thread_id}: {e}")
            # If we can't check, assume thread is valid to avoid breaking functionality
            return True
    
    def _wait_for_active_runs(self, thread_id: str, max_wait_time: int = 60) -> None:
        """Wait for all active runs in thread to complete."""
        try:
            start_time = time.time()
            check_interval = 0.5
            
            while time.time() - start_time < max_wait_time:
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=10)
                active_statuses = ["queued", "in_progress", "requires_action"]
                active_runs = [run for run in runs.data if run.status in active_statuses]
                
                if not active_runs:
                    return
                
                time.sleep(check_interval)
            
            self._logger.warning(f"Active runs still present after {max_wait_time}s wait")
        except Exception:
            pass
    
    def _run_assistant_optimized(self, thread_id: str) -> str:
        """Run the assistant with optimized polling strategy."""
        assistant = self._get_assistant()
        
        # Create run
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant.id
        )
        
        # Poll for completion
        max_attempts = 120
        attempt = 0
        start_time = time.time()
        
        while run.status not in ["completed", "failed", "cancelled", "expired"] and attempt < max_attempts:
            elapsed = time.time() - start_time
            
            if elapsed < 1.0:
                poll_interval = 0.2
            elif elapsed < 3.0:
                poll_interval = 0.3
            elif elapsed < 10.0:
                poll_interval = 0.5
            else:
                poll_interval = 1.0
            
            time.sleep(poll_interval)
            
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            attempt += 1
        
        # Handle terminal states
        if run.status == "failed":
            error_msg = getattr(run, 'last_error', {}).get('message', 'Unknown error')
            raise RuntimeError(f"Assistant run failed: {error_msg}")
        
        if run.status in ["cancelled", "expired"]:
            raise RuntimeError(f"Assistant run {run.status}: {run.id}")
        
        if run.status != "completed":
            raise TimeoutError(f"Assistant run did not complete. Status: {run.status}")
        
        # Retrieve response message
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=1,
            order="desc"
        )
        
        if not messages.data:
            raise ValueError("No messages returned from assistant")
        
        return messages.data[0].content[0].text.value

