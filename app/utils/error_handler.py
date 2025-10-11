"""
Error handling utilities for consistent error management across the application.
Provides decorators and utilities for HTTP exception handling, logging, and error formatting.
"""

import functools
import logging
from typing import Callable, Any, Optional, Type, Union
from fastapi import HTTPException, status

from app.config import logger


# ============================================================================
# HTTP EXCEPTION HELPERS
# ============================================================================

def create_http_error(
    status_code: int,
    detail: str,
    error: Optional[Exception] = None,
    log_level: str = "error"
) -> HTTPException:
    """
    Create an HTTPException with consistent logging.
    
    Args:
        status_code: HTTP status code
        detail: Error detail message
        error: Optional original exception
        log_level: Logging level (error, warning, info)
        
    Returns:
        HTTPException with formatted message
    """
    if error:
        full_detail = f"{detail}: {str(error)}"
    else:
        full_detail = detail
    
    # Log the error
    log_func = getattr(logger, log_level, logger.error)
    if error:
        log_func(f"HTTP {status_code}: {full_detail}", exc_info=True)
    else:
        log_func(f"HTTP {status_code}: {full_detail}")
    
    return HTTPException(status_code=status_code, detail=full_detail)


def create_500_error(detail: str, error: Optional[Exception] = None) -> HTTPException:
    """Create a 500 Internal Server Error with logging."""
    return create_http_error(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
        error=error,
        log_level="error"
    )


def create_404_error(detail: str, error: Optional[Exception] = None) -> HTTPException:
    """Create a 404 Not Found error with logging."""
    return create_http_error(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
        error=error,
        log_level="warning"
    )


def create_400_error(detail: str, error: Optional[Exception] = None) -> HTTPException:
    """Create a 400 Bad Request error with logging."""
    return create_http_error(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
        error=error,
        log_level="warning"
    )


def create_403_error(detail: str, error: Optional[Exception] = None) -> HTTPException:
    """Create a 403 Forbidden error with logging."""
    return create_http_error(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        error=error,
        log_level="warning"
    )


# ============================================================================
# DECORATORS
# ============================================================================

def handle_http_errors(
    error_message: str = "An error occurred",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    re_raise_http_errors: bool = True
):
    """
    Decorator to handle exceptions and convert them to HTTPException.
    
    Args:
        error_message: Base error message to use
        status_code: HTTP status code for exceptions
        re_raise_http_errors: Whether to re-raise existing HTTPException
        
    Usage:
        @handle_http_errors("Error processing message")
        async def endpoint_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                if re_raise_http_errors:
                    raise
                raise create_http_error(status_code, error_message)
            except Exception as e:
                raise create_http_error(status_code, error_message, e)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                if re_raise_http_errors:
                    raise
                raise create_http_error(status_code, error_message)
            except Exception as e:
                raise create_http_error(status_code, error_message, e)
        
        # Return appropriate wrapper based on whether function is async
        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def log_errors(
    message: str = "Error occurred",
    log_level: str = "error",
    re_raise: bool = True
):
    """
    Decorator to log errors without converting to HTTPException.
    
    Args:
        message: Log message prefix
        log_level: Logging level (error, warning, info, debug)
        re_raise: Whether to re-raise the exception after logging
        
    Usage:
        @log_errors("Failed to process")
        def some_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{message}: {str(e)}", exc_info=True)
                if re_raise:
                    raise
                return None
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{message}: {str(e)}", exc_info=True)
                if re_raise:
                    raise
                return None
        
        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# SAFE EXECUTION UTILITIES
# ============================================================================

def safe_execute(
    func: Callable,
    default_return: Any = None,
    log_error: bool = True,
    error_message: str = "Error executing function"
) -> Any:
    """
    Safely execute a function and return default value on error.
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        log_error: Whether to log errors
        error_message: Error message prefix for logging
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            logger.error(f"{error_message}: {str(e)}", exc_info=True)
        return default_return


async def safe_execute_async(
    func: Callable,
    default_return: Any = None,
    log_error: bool = True,
    error_message: str = "Error executing async function"
) -> Any:
    """
    Safely execute an async function and return default value on error.
    
    Args:
        func: Async function to execute
        default_return: Value to return on error
        log_error: Whether to log errors
        error_message: Error message prefix for logging
        
    Returns:
        Function result or default_return on error
    """
    try:
        return await func()
    except Exception as e:
        if log_error:
            logger.error(f"{error_message}: {str(e)}", exc_info=True)
        return default_return


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_required(
    value: Any,
    field_name: str,
    error_message: Optional[str] = None
) -> None:
    """
    Validate that a required field is not None or empty.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error message
        error_message: Custom error message
        
    Raises:
        HTTPException: If validation fails
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        msg = error_message or f"{field_name} is required"
        raise create_400_error(msg)


def validate_file_exists(
    file_path: str,
    error_message: Optional[str] = None
) -> None:
    """
    Validate that a file exists.
    
    Args:
        file_path: Path to file
        error_message: Custom error message
        
    Raises:
        HTTPException: If file doesn't exist
    """
    import os
    if not os.path.exists(file_path):
        msg = error_message or f"File not found: {os.path.basename(file_path)}"
        raise create_404_error(msg)


# ============================================================================
# ERROR CONTEXT MANAGER
# ============================================================================

class ErrorContext:
    """
    Context manager for consistent error handling.
    
    Usage:
        with ErrorContext("Error processing data"):
            # Your code here
            pass
    """
    
    def __init__(
        self,
        error_message: str,
        log_level: str = "error",
        re_raise: bool = True,
        default_return: Any = None
    ):
        self.error_message = error_message
        self.log_level = log_level
        self.re_raise = re_raise
        self.default_return = default_return
        self.exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exception = exc_val
            log_func = getattr(logger, self.log_level, logger.error)
            log_func(f"{self.error_message}: {str(exc_val)}", exc_info=True)
            
            if not self.re_raise:
                return True  # Suppress exception
        return False  # Propagate exception


# ============================================================================
# RESPONSE FORMATTERS
# ============================================================================

def success_response(
    message: str,
    data: Optional[dict] = None,
    **kwargs
) -> dict:
    """
    Create a standardized success response.
    
    Args:
        message: Success message
        data: Optional data payload
        **kwargs: Additional fields to include
        
    Returns:
        Standardized success response dict
    """
    response = {
        "status": "success",
        "message": message
    }
    if data:
        response["data"] = data
    response.update(kwargs)
    return response


def error_response(
    message: str,
    error: Optional[Exception] = None,
    **kwargs
) -> dict:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        error: Optional exception
        **kwargs: Additional fields to include
        
    Returns:
        Standardized error response dict
    """
    response = {
        "status": "error",
        "message": message
    }
    if error:
        response["error"] = str(error)
    response.update(kwargs)
    return response

