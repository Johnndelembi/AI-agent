"""
Utility functions and helpers for the AI Agent application.

The primary utilities are in error_handler.py for consistent error handling.
The async_helpers.py module is available for advanced async patterns if needed.
"""

from src.utils.error_handler import (
    create_http_error,
    create_500_error,
    create_404_error,
    create_400_error,
    create_403_error,
    handle_http_errors,
    log_errors,
    safe_execute,
    safe_execute_async,
    validate_required,
    validate_file_exists,
    ErrorContext,
    success_response,
    error_response,
)

# async_helpers is available but not exported by default
# Import directly if needed: from src.utils.async_helpers import ExecutorManager

__all__ = [
    # Error handling (primary utilities)
    "create_http_error",
    "create_500_error",
    "create_404_error",
    "create_400_error",
    "create_403_error",
    "handle_http_errors",
    "log_errors",
    "safe_execute",
    "safe_execute_async",
    "validate_required",
    "validate_file_exists",
    "ErrorContext",
    "success_response",
    "error_response",
]

