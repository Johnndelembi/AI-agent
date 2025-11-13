"""
Async utilities for advanced asynchronous patterns.

⚠️ NOTE: Most async patterns in this codebase use native async/await.
This module is kept for advanced use cases but is not actively used.

RECOMMENDATION: 
- For I/O-bound operations: Use native async/await
- For CPU-bound operations: Use `asyncio.to_thread()` (Python 3.9+)
- This module: Only for complex executor management or legacy code

Provides helpers for ThreadPoolExecutor management and async execution patterns.
"""

import asyncio
from typing import Callable, Any, TypeVar, Optional
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from src.config import logger


T = TypeVar('T')


# ============================================================================
# ASYNC EXECUTION HELPERS
# ============================================================================

async def run_in_executor(
    func: Callable[..., T],
    *args,
    executor: Optional[ThreadPoolExecutor] = None,
    **kwargs
) -> T:
    """
    Run a synchronous function in a thread pool executor.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        executor: Optional executor (uses default if None)
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function
    """
    loop = asyncio.get_running_loop()
    
    # Create a wrapper that handles kwargs
    def _wrapper():
        return func(*args, **kwargs)
    
    return await loop.run_in_executor(executor, _wrapper)


def async_wrap(func: Callable[..., T]) -> Callable[..., asyncio.Future[T]]:
    """
    Decorator to wrap a sync function to run in executor.
    
    Usage:
        @async_wrap
        def sync_function(x):
            return x * 2
            
        result = await sync_function(5)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_executor(func, *args, **kwargs)
    return wrapper


# ============================================================================
# EXECUTOR MANAGEMENT
# ============================================================================

class ExecutorManager:
    """
    Manages ThreadPoolExecutor lifecycle with proper cleanup.
    
    Usage:
        executor_manager = ExecutorManager(max_workers=4, thread_name_prefix="my_service")
        result = await executor_manager.execute(some_function, arg1, arg2)
        await executor_manager.shutdown()
    """
    
    def __init__(self, max_workers: int = 4, thread_name_prefix: str = "worker"):
        """
        Initialize the executor manager.
        
        Args:
            max_workers: Maximum number of worker threads
            thread_name_prefix: Prefix for thread names
        """
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self._lock = asyncio.Lock()
        self._is_shutdown = False
        logger.debug(f"ExecutorManager initialized with {max_workers} workers")
    
    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute a function in the thread pool.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result of the function
            
        Raises:
            RuntimeError: If executor is shutdown
        """
        if self._is_shutdown:
            raise RuntimeError("Executor is shutdown")
        
        return await run_in_executor(func, *args, executor=self._executor, **kwargs)
    
    async def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        """
        Shutdown the executor.
        
        Args:
            wait: Whether to wait for pending tasks
            cancel_futures: Whether to cancel pending futures
        """
        async with self._lock:
            if not self._is_shutdown:
                self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
                self._is_shutdown = True
                logger.debug("ExecutorManager shutdown complete")
    
    @property
    def is_shutdown(self) -> bool:
        """Check if executor is shutdown."""
        return self._is_shutdown


# ============================================================================
# LAZY INITIALIZATION
# ============================================================================

class AsyncLazy:
    """
    Lazy initialization wrapper for async resources with thread safety.
    
    Usage:
        lazy_resource = AsyncLazy(lambda: SomeHeavyResource())
        resource = await lazy_resource.get()
    """
    
    def __init__(self, factory: Callable[[], T]):
        """
        Initialize lazy wrapper.
        
        Args:
            factory: Factory function that creates the resource
        """
        self._factory = factory
        self._instance: Optional[T] = None
        self._lock = asyncio.Lock()
    
    async def get(self) -> T:
        """
        Get the instance, creating it if necessary (thread-safe).
        
        Returns:
            The lazily-initialized instance
        """
        if self._instance is None:
            async with self._lock:
                if self._instance is None:
                    loop = asyncio.get_running_loop()
                    self._instance = await loop.run_in_executor(None, self._factory)
        return self._instance
    
    def is_initialized(self) -> bool:
        """Check if the instance has been initialized."""
        return self._instance is not None
    
    async def reset(self) -> None:
        """Reset the instance (clear it)."""
        async with self._lock:
            self._instance = None


# ============================================================================
# RETRY LOGIC
# ============================================================================

async def retry_async(
    func: Callable[..., T],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    *args,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch and retry
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function
        
    Returns:
        Result of the function
        
    Raises:
        Last exception if all attempts fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                    f"Retrying in {current_delay}s..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor
            else:
                logger.error(f"All {max_attempts} attempts failed")
    
    raise last_exception


# ============================================================================
# TIMEOUT HELPERS
# ============================================================================

async def with_timeout(
    coro,
    timeout: float,
    timeout_message: str = "Operation timed out"
) -> Any:
    """
    Execute a coroutine with a timeout.
    
    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        timeout_message: Error message for timeout
        
    Returns:
        Result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"{timeout_message} (timeout: {timeout}s)")
        raise asyncio.TimeoutError(timeout_message)


# ============================================================================
# BATCH PROCESSING
# ============================================================================

async def process_batch(
    items: list,
    processor: Callable,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> list:
    """
    Process items in batches with concurrency control.
    
    Args:
        items: List of items to process
        processor: Async function to process each item
        batch_size: Number of items per batch
        max_concurrent: Maximum concurrent tasks
        
    Returns:
        List of results
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(item):
        async with semaphore:
            return await processor(item)
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[process_with_semaphore(item) for item in batch],
            return_exceptions=True
        )
        results.extend(batch_results)
    
    return results

