"""
Chef Analysis Tools for LlamaStack Agent Integration
Essential tools that wrap existing Chef analysis logic for standard LlamaStack usage
"""

from .complexity_tool import chef_complexity_calculator
from .formatting_tool import chef_content_formatter

# Ensure tools are properly exported for LlamaStack
__all__ = [
    "chef_complexity_calculator", 
    "chef_content_formatter"
]

# Validate that all tools are callable
import logging
logger = logging.getLogger(__name__)

try:
    # Test that tools can be imported and have docstrings
    assert callable(chef_complexity_calculator), "chef_complexity_calculator is not callable"
    assert callable(chef_content_formatter), "chef_content_formatter is not callable"
    
    assert chef_complexity_calculator.__doc__, "chef_complexity_calculator missing docstring"
    assert chef_content_formatter.__doc__, "chef_content_formatter missing docstring"
    
    logger.info(" All Chef analysis tools validated successfully")
    
except AssertionError as e:
    logger.error(f" Tool validation failed: {e}")
    raise

except Exception as e:
    logger.error(f" Unexpected error validating tools: {e}")
    raise