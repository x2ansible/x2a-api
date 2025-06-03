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


class ChefAnalysisLogger:
    """
    Enhanced logger for Chef Analysis Agent with step tracking and rich formatting.
    """
    
    def __init__(self, name: str = "chef_analysis", correlation_id: Optional[str] = None):
        self.name = name
        self.correlation_id = correlation_id
        self.console = Console() if RICH_AVAILABLE else None
        self.logger = self._setup_logger()
        
        if LLAMASTACK_LOGGER_AVAILABLE:
            self.agent_event_logger = AgentEventLogger()
        else:
            self.agent_event_logger = None
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with rich formatting if available."""
        logger = logging.getLogger(self.name)
        
        if logger.handlers:
            return logger
        
        logger.setLevel(logging.INFO)
        
        if RICH_AVAILABLE:
            # Use Rich handler for beautiful formatting
            handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=True,
                markup=True,
                rich_tracebacks=True
            )
            formatter = logging.Formatter(
                fmt="[bold blue]{name}[/] - {message}",
                style="{"
            )
        else:
            # Fallback to standard handler
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    def info(self, message: str, **kwargs):
        """Log info message with correlation ID."""
        formatted_message = self._format_message(message, **kwargs)
        self.logger.info(formatted_message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with correlation ID."""
        formatted_message = self._format_message(message, **kwargs)
        self.logger.debug(formatted_message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with correlation ID."""
        formatted_message = self._format_message(message, **kwargs)
        self.logger.warning(formatted_message)
    
    def error(self, message: str, **kwargs):
        """Log error message with correlation ID."""
        formatted_message = self._format_message(message, **kwargs)
        self.logger.error(formatted_message)
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with correlation ID and additional context."""
        parts = []
        
        if self.correlation_id:
            parts.append(f"[{self.correlation_id}]")
        
        parts.append(message)
        
        if kwargs:
            context_parts = []
            for key, value in kwargs.items():
                if isinstance(value, dict):
                    context_parts.append(f"{key}={json.dumps(value, indent=2)}")
                else:
                    context_parts.append(f"{key}={value}")
            
            if context_parts:
                parts.append(f"({', '.join(context_parts)})")
        
        return " ".join(parts)
    
    def log_cookbook_analysis_start(self, cookbook_name: str, file_count: int):
        """Log cookbook analysis start with details."""
        self.info(
            f"🍳 Starting cookbook analysis: [bold green]{cookbook_name}[/]",
            file_count=file_count,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_llamastack_request(self, session_id: str, model: str, content_preview: str):
        """Log LlamaStack request details."""
        preview = content_preview[:100] + "..." if len(content_preview) > 100 else content_preview
        self.info(
            f"🚀 Sending LlamaStack request",
            session_id=session_id,
            model=model,
            content_preview=preview
        )
    
    def log_llamastack_response(self, response_length: int, processing_time: float):
        """Log LlamaStack response details."""
        self.info(
            f" Received LlamaStack response",
            response_length=response_length,
            processing_time_seconds=round(processing_time, 3)
        )
    
    def log_json_extraction(self, success: bool, extracted_sections: List[str]):
        """Log JSON extraction results."""
        if success:
            self.info(
                f"🔍 Successfully extracted JSON analysis",
                sections_found=extracted_sections
            )
        else:
            self.warning(f"⚠️ Failed to extract valid JSON from response")
    
    def log_analysis_completion(self, analysis_result: Dict[str, Any], total_time: float):
        """Log analysis completion with summary."""
        summary = self._create_analysis_summary(analysis_result)
        self.info(
            f"🎉 Chef cookbook analysis completed",
            total_time_seconds=round(total_time, 3),
            **summary
        )
    
    def _create_analysis_summary(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of analysis results for logging."""
        summary = {}
        
        # Version requirements summary
        version_req = analysis.get("version_requirements", {})
        if version_req:
            summary["chef_version"] = version_req.get("min_chef_version", "unknown")
            summary["ruby_version"] = version_req.get("min_ruby_version", "unknown")
            summary["migration_effort"] = version_req.get("migration_effort", "unknown")
        
        # Dependencies summary
        deps = analysis.get("dependencies", {})
        if deps:
            summary["is_wrapper"] = deps.get("is_wrapper", False)
            summary["dependency_count"] = len(deps.get("direct_deps", []))
        
        # Functionality summary
        func = analysis.get("functionality", {})
        if func:
            summary["primary_purpose"] = func.get("primary_purpose", "unknown")
            summary["reusability"] = func.get("reusability", "unknown")
        
        # Recommendations summary
        rec = analysis.get("recommendations", {})
        if rec:
            summary["recommendation"] = rec.get("consolidation_action", "unknown")
        
        return summary


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
    """Factory function to create ChefAnalysisLogger with correlation ID."""
    return ChefAnalysisLogger(name="chef_analysis", correlation_id=correlation_id)


def setup_root_logging():
    """Setup root logging configuration for the application."""
    if RICH_AVAILABLE:
        # Use Rich for beautiful logs
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)]
        )
    else:
        # Fallback to standard logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


# Global setup
setup_root_logging()