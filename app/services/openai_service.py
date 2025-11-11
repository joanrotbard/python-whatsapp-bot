"""OpenAI Assistant service with optimized performance and caching."""
import os
import time
import logging
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv

from app.repositories.thread_repository import ThreadRepository


class OpenAIService:
    """Service for interacting with OpenAI Assistants API with performance optimizations."""
    
    def __init__(self, thread_repository: ThreadRepository):
        """
        Initialize OpenAI service.
        
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
        
        # Caching for performance
        self._assistant_cache = None  # Cache assistant to avoid repeated API calls
    
    def _get_assistant(self):
        """Get assistant with caching - only fetch once."""
        if self._assistant_cache is None:
            self._assistant_cache = self.client.beta.assistants.retrieve(self.assistant_id)
        return self._assistant_cache
    
    def _wait_for_active_runs(self, thread_id: str, max_wait_time: int = 60) -> None:
        """
        Wait for all active runs in thread to complete before proceeding.
        
        This prevents errors when trying to add messages while a run is active.
        Instead of cancelling, we wait for the run to finish.
        
        Args:
            thread_id: OpenAI thread ID
            max_wait_time: Maximum time to wait in seconds (default: 60)
        """
        try:
            start_time = time.time()
            check_interval = 0.5  # Check every 500ms
            
            while time.time() - start_time < max_wait_time:
                # List all runs for the thread
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=10)
                
                # Find active runs (queued, in_progress, requires_action)
                active_statuses = ["queued", "in_progress", "requires_action"]
                active_runs = [run for run in runs.data if run.status in active_statuses]
                
                if not active_runs:
                    # No active runs, safe to proceed
                    return
                
                # Wait before checking again
                time.sleep(check_interval)
            
            # If we've waited too long, log a warning
            # The API call will fail with a clear error if run is still active
            self._logger.warning(f"Active runs still present after {max_wait_time}s wait in thread {thread_id}")
        except Exception:
            pass  # Non-critical - continue even if we can't check runs
    
    def generate_response(self, message_body: str, wa_id: str, name: str) -> str:
        """
        Generate a response using OpenAI Assistant with optimized API calls.
        
        Args:
            message_body: User's message
            wa_id: WhatsApp user ID
            name: User's name
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If OpenAI API call fails
        """
        # Get or create thread (optimized - avoid unnecessary API calls)
        thread_id = None
        try:
            thread_id = self.thread_repository.get_thread_id(wa_id)
        except Exception as e:
            self._logger.warning(f"Could not get thread from repository: {e}, creating new thread")
        
        if thread_id is None:
            # Create thread
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            try:
                self.thread_repository.save_thread_id(wa_id, thread_id)
            except Exception:
                pass  # Non-critical
        else:
            # Extend TTL when thread is used
            try:
                self.thread_repository.extend_ttl(wa_id)
            except Exception:
                pass  # Non-critical
            
            # Wait for any active runs to complete before adding new message
            self._wait_for_active_runs(thread_id)
        
        # Add user message to thread
        # Retry if there's still an active run (race condition)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=message_body
                )
                break  # Success, exit retry loop
            except Exception as e:
                # If error is about active run, wait and retry
                if "active" in str(e).lower() and "run" in str(e).lower():
                    if attempt < max_retries - 1:
                        self._logger.warning(f"Active run detected, waiting and retrying (attempt {attempt + 1}/{max_retries})...")
                        self._wait_for_active_runs(thread_id, max_wait_time=10)
                    else:
                        # Last attempt failed, raise the error
                        raise
                else:
                    # Different error, raise immediately
                    raise
        
        # Run assistant and get response (optimized polling)
        response = self._run_assistant_optimized(thread_id)
        return response
    
    def _run_assistant_optimized(self, thread_id: str) -> str:
        """
        Run the assistant with optimized polling strategy.
        
        Uses faster initial polling and checks for completion more efficiently.
        
        Args:
            thread_id: OpenAI thread ID
            
        Returns:
            Assistant's response text
        """
        assistant = self._get_assistant()
        
        # Create run
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant.id
        )
        
        # Optimized polling strategy:
        # Balance between fast detection and API call efficiency
        # - Start with moderate intervals to reduce API calls
        # - Increase gradually if response is taking longer
        # - Check for terminal states early
        
        max_attempts = 120
        attempt = 0
        start_time = time.time()
        
        while run.status not in ["completed", "failed", "cancelled", "expired"] and attempt < max_attempts:
            # Adaptive polling based on elapsed time and attempt number
            elapsed = time.time() - start_time
            
            if elapsed < 1.0:
                # First second: check every 200ms (5 calls max)
                poll_interval = 0.2
            elif elapsed < 3.0:
                # Next 2 seconds: check every 300ms
                poll_interval = 0.3
            elif elapsed < 10.0:
                # Next 7 seconds: check every 500ms
                poll_interval = 0.5
            else:
                # After 10 seconds: check every 1s
                poll_interval = 1.0
            
            time.sleep(poll_interval)
            
            # Retrieve run status
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
            raise TimeoutError(f"Assistant run did not complete. Status: {run.status} after {attempt} attempts")
        
        # Optimized message retrieval - only get the latest message
        # Use limit=1 to reduce payload size
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=1,  # Only get the latest message
            order="desc"  # Most recent first
        )
        
        if not messages.data:
            raise ValueError("No messages returned from assistant")
        
        response_text = messages.data[0].content[0].text.value
        return response_text
