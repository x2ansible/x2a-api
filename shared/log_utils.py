"""
Logging utilities for Chef Analysis Agent.
Provides rich logging, step tracking, and LlamaStack integration.
"""
import json
import logging
import sys
from json import JSONDecodeError
from typing import List, Any, Dict, Optional
from datetime import datetime
import uuid

try:
    from rich.pretty import pprint
    from rich.console import Console
    from rich.logging import RichHandler
    from termcolor import cprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from llama_stack_client import AgentEventLogger
    LLAMASTACK_LOGGER_AVAILABLE = True
except ImportError:
    LLAMASTACK_LOGGER_AVAILABLE = False


def create_correlation_id() -> str:
    """Create a unique correlation ID for request tracking."""
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

class ChefAnalysisLogger:
    """Custom logger for Chef analysis with correlation ID tracking."""
    
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"chef_analysis_{correlation_id}")
        self.logger.setLevel(logging.INFO)
        
        # Create console handler if not already exists
        if not self.logger.handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Add correlation ID to log records
        for handler in self.logger.handlers:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s'
            ))
    
    def _log_with_correlation(self, level: str, message: str):
        """Log message with correlation ID."""
        extra = {'correlation_id': self.correlation_id}
        if level == 'info':
            self.logger.info(message, extra=extra)
        elif level == 'warning':
            self.logger.warning(message, extra=extra)
        elif level == 'error':
            self.logger.error(message, extra=extra)
        elif level == 'debug':
            self.logger.debug(message, extra=extra)
    
    def info(self, message: str):
        """Log info message."""
        self._log_with_correlation('info', message)
    
    def warning(self, message: str):
        """Log warning message."""
        self._log_with_correlation('warning', message)
    
    def error(self, message: str):
        """Log error message."""
        self._log_with_correlation('error', message)
    
    def debug(self, message: str):
        """Log debug message."""
        self._log_with_correlation('debug', message)
    
    def log_cookbook_analysis_start(self, cookbook_name: str, file_count: int):
        """Log the start of cookbook analysis."""
        self.info(f"Starting analysis of cookbook '{cookbook_name}' with {file_count} files")
    
    def log_analysis_completion(self, result: Dict[str, Any], total_time: float):
        """Log analysis completion with summary."""
        success = result.get('success', False)
        method = result.get('analysis_method', 'unknown')
        resources = result.get('tree_sitter_facts', {}).get('total_resources', 0)
        
        if success:
            self.info(f"Analysis completed successfully in {total_time:.3f}s using {method} method")
            self.info(f"Extracted {resources} resources from cookbook")
        else:
            self.error(f"Analysis failed after {total_time:.3f}s")
    
    def log_step_completion(self, step_name: str, step_number: int, total_steps: int):
        """Log step completion with progress."""
        progress = (step_number / total_steps) * 100
        self.info(f"Completed {step_name} ({step_number}/{total_steps} - {progress:.1f}%)")


def step_printer(steps: List[Any], logger: Optional[ChefAnalysisLogger] = None):
    """
    Print the steps of an agent's response in a formatted way.
    Enhanced version with Chef Analysis specific logging.
    
    Args:
        steps: List of steps from an agent's response
        logger: Optional ChefAnalysisLogger instance
    """
    if not steps:
        if logger:
            logger.warning("No steps to print")
        return
    
    print_func = logger.info if logger else print
    
    if logger:
        logger.info(f"🔄 Processing {len(steps)} agent steps")
    
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        
        if RICH_AVAILABLE and logger and logger.console:
            logger.console.print(f"\n[bold blue]{'─' * 10} 📍 Step {i+1}: {step_type} {'─' * 10}[/]")
        else:
            print(f"\n{'-' * 10} 📍 Step {i+1}: {step_type} {'-' * 10}")
        
        if step_type == "ToolExecutionStep":
            if logger:
                logger.info("🔧 Executing tool...")
            else:
                print("🔧 Executing tool...")
            
            try:
                tool_response = step.tool_responses[0].content
                if RICH_AVAILABLE:
                    pprint(json.loads(tool_response))
                else:
                    print(json.dumps(json.loads(tool_response), indent=2))
            except (TypeError, JSONDecodeError, AttributeError):
                # Tool response is not a valid JSON object
                if RICH_AVAILABLE:
                    pprint(tool_response)
                else:
                    print(tool_response)
        else:
            # Handle model response steps
            if hasattr(step, 'api_model_response'):
                if step.api_model_response.content:
                    if logger:
                        logger.info("🤖 Model Response:")
                    else:
                        print("🤖 Model Response:")
                    
                    if RICH_AVAILABLE:
                        cprint(f"{step.api_model_response.content}\n", "magenta")
                    else:
                        print(f"{step.api_model_response.content}\n")
                
                elif hasattr(step.api_model_response, 'tool_calls') and step.api_model_response.tool_calls:
                    tool_call = step.api_model_response.tool_calls[0]
                    
                    if logger:
                        logger.info("🛠️ Tool call generated:")
                    else:
                        print("🛠️ Tool call Generated:")
                    
                    try:
                        args = json.loads(tool_call.arguments_json)
                        tool_info = f"Tool call: {tool_call.tool_name}, Arguments: {args}"
                    except (JSONDecodeError, AttributeError):
                        tool_info = f"Tool call: {getattr(tool_call, 'tool_name', 'unknown')}"
                    
                    if RICH_AVAILABLE:
                        cprint(tool_info, "magenta")
                    else:
                        print(tool_info)
    
    if RICH_AVAILABLE and logger and logger.console:
        logger.console.print(f"\n[bold green]{'=' * 10} Query processing completed {'=' * 10}[/]\n")
    else:
        print(f"\n{'=' * 10} Query processing completed {'=' * 10}\n")


def create_chef_logger(correlation_id: str) -> ChefAnalysisLogger:
    """Create a Chef analysis logger with correlation ID."""
    return ChefAnalysisLogger(correlation_id)


def setup_logging(level: str = "INFO") -> None:
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def get_logger(name: str) -> logging.Logger:
    """Get a standard logger."""
    return logging.getLogger(name)