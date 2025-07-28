"""
Ansible Tools for LlamaStack Agent Integration
Essential tools that wrap existing Ansible analysis logic for standard LlamaStack usage
"""

from .ansible_lint_tool import ansible_lint_tool

# Ensure tools are properly exported for LlamaStack
__all__ = [
    "ansible_lint_tool"
]

# Validate that all tools are properly decorated and available
import logging
logger = logging.getLogger(__name__)

try:
    # Test that tools can be imported and have docstrings
    # Handle client_tool decorator which makes function non-callable
    if hasattr(ansible_lint_tool, '__wrapped__'):
        # Function is decorated, check the wrapped function
        wrapped_func = getattr(ansible_lint_tool, '__wrapped__')
        assert callable(wrapped_func), "ansible_lint_tool.__wrapped__ is not callable"
        assert wrapped_func.__doc__, "ansible_lint_tool.__wrapped__ missing docstring"
        logger.info(" ansible_lint_tool is properly decorated and available")
    else:
        # Function is not decorated, check directly
        assert callable(ansible_lint_tool), "ansible_lint_tool is not callable"
        assert ansible_lint_tool.__doc__, "ansible_lint_tool missing docstring"
        logger.info(" ansible_lint_tool is callable and available")
    
    logger.info(" All Ansible tools validated successfully")
    
except AssertionError as e:
    logger.error(f" Tool validation failed: {e}")
    # Don't raise - just log the error and continue
    logger.warning("⚠️ Tool validation failed, but continuing with startup")
    
except Exception as e:
    logger.error(f" Unexpected error validating tools: {e}")
    # Don't raise - just log the error and continue
    logger.warning("⚠️ Tool validation error, but continuing with startup") 