# utils/logging_utils.py - Enhanced logging utilities with step printer

import json
import logging
from json import JSONDecodeError
from typing import Any, List, Optional, Dict
from datetime import datetime

try:
    from rich.pretty import pprint
    from termcolor import cprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Fallback implementations
    def pprint(obj):
        print(json.dumps(obj, indent=2) if isinstance(obj, (dict, list)) else str(obj))
    
    def cprint(text, color=None):
        print(text)

logger = logging.getLogger(__name__)

class AgentStepPrinter:
    """Enhanced step printer for agent responses with rich formatting"""
    
    def __init__(self, enable_rich: bool = True):
        self.enable_rich = enable_rich and RICH_AVAILABLE
        self.step_count = 0
    
    def print_steps(self, steps: List[Any], agent_name: str = "Unknown") -> None:
        """
        Print the steps of an agent's response in a formatted way.
        Note: stream needs to be set to False to use this function.
        
        Args:
            steps: List of steps from an agent's response
            agent_name: Name of the agent for context
        """
        if not steps:
            print(f"📋 No steps found for agent '{agent_name}'")
            return
        
        print(f"\n{'='*20} 🚀 Agent Execution Steps: {agent_name} {'='*20}")
        print(f"📊 Total Steps: {len(steps)}")
        print(f"⏰ Execution Time: {datetime.now().strftime('%H:%M:%S')}")
        
        for i, step in enumerate(steps):
            self._print_single_step(step, i + 1)
        
        print(f"{'='*20}  Query Processing Completed {'='*20}\n")
    
    def _print_single_step(self, step: Any, step_number: int) -> None:
        """Print a single step with appropriate formatting"""
        step_type = type(step).__name__
        
        print(f"\n{'-' * 10} 📍 Step {step_number}: {step_type} {'-' * 10}")
        
        if step_type == "ToolExecutionStep":
            self._print_tool_execution_step(step)
        elif hasattr(step, 'api_model_response'):
            self._print_model_response_step(step)
        else:
            self._print_generic_step(step)
    
    def _print_tool_execution_step(self, step: Any) -> None:
        """Print tool execution step details"""
        print("🔧 Executing tool...")
        
        if hasattr(step, 'tool_responses') and step.tool_responses:
            for i, tool_response in enumerate(step.tool_responses):
                print(f"   🛠️  Tool Response {i+1}:")
                try:
                    if hasattr(tool_response, 'content'):
                        content = tool_response.content
                        # Try to parse as JSON for pretty printing
                        try:
                            parsed_content = json.loads(content)
                            print("   📄 JSON Response:")
                            pprint(parsed_content)
                        except (TypeError, JSONDecodeError):
                            print("   📄 Text Response:")
                            if self.enable_rich:
                                cprint(f"   {content}", "cyan")
                            else:
                                print(f"   {content}")
                    else:
                        pprint(tool_response)
                except Exception as e:
                    print(f"   ⚠️  Error displaying tool response: {e}")
                    print(f"   Raw response: {tool_response}")
    
    def _print_model_response_step(self, step: Any) -> None:
        """Print model response step details"""
        api_response = step.api_model_response
        
        if hasattr(api_response, 'content') and api_response.content:
            print("🤖 Model Response:")
            content = api_response.content
            
            # Try to format JSON content nicely
            try:
                if content.strip().startswith(('{', '[')):
                    parsed = json.loads(content)
                    print("   📋 Structured Response:")
                    pprint(parsed)
                else:
                    if self.enable_rich:
                        cprint(f"   {content}", "magenta")
                    else:
                        print(f"   {content}")
            except (TypeError, JSONDecodeError):
                if self.enable_rich:
                    cprint(f"   {content}", "magenta")
                else:
                    print(f"   {content}")
        
        elif hasattr(api_response, 'tool_calls') and api_response.tool_calls:
            print("🛠️  Tool Calls Generated:")
            for i, tool_call in enumerate(api_response.tool_calls):
                try:
                    tool_name = getattr(tool_call, 'tool_name', 'Unknown')
                    
                    # Handle different argument formats
                    arguments = None
                    if hasattr(tool_call, 'arguments_json'):
                        try:
                            arguments = json.loads(tool_call.arguments_json)
                        except (TypeError, JSONDecodeError):
                            arguments = tool_call.arguments_json
                    elif hasattr(tool_call, 'arguments'):
                        arguments = tool_call.arguments
                    
                    call_info = f"Tool: {tool_name}"
                    if arguments:
                        call_info += f", Arguments: {arguments}"
                    
                    if self.enable_rich:
                        cprint(f"   {i+1}. {call_info}", "magenta")
                    else:
                        print(f"   {i+1}. {call_info}")
                        
                except Exception as e:
                    print(f"   ⚠️  Error displaying tool call {i+1}: {e}")
                    print(f"   Raw tool call: {tool_call}")
        else:
            print("   ℹ️  No content or tool calls in this step")
    
    def _print_generic_step(self, step: Any) -> None:
        """Print generic step information"""
        print("📦 Generic Step:")
        try:
            # Try to extract useful information from the step
            if hasattr(step, '__dict__'):
                step_dict = {k: v for k, v in step.__dict__.items() 
                           if not k.startswith('_') and v is not None}
                if step_dict:
                    pprint(step_dict)
                else:
                    print(f"   Raw step: {step}")
            else:
                print(f"   Raw step: {step}")
        except Exception as e:
            print(f"   ⚠️  Error displaying step: {e}")
            print(f"   Step type: {type(step)}")

class EnhancedAgentLogger:
    """Enhanced logger for agent operations"""
    
    def __init__(self, enable_step_printing: bool = True, enable_rich: bool = True):
        self.step_printer = AgentStepPrinter(enable_rich) if enable_step_printing else None
        self.logger = logging.getLogger("agent_execution")
    
    def log_agent_execution_start(self, agent_name: str, query: str) -> None:
        """Log the start of agent execution"""
        self.logger.info(f"🚀 Starting execution for agent '{agent_name}'")
        self.logger.debug(f"Query preview: {query[:100]}{'...' if len(query) > 100 else ''}")
    
    def log_agent_execution_complete(self, agent_name: str, execution_time: float, success: bool) -> None:
        """Log the completion of agent execution"""
        status = " SUCCESS" if success else " FAILED"
        self.logger.info(f"{status} Agent '{agent_name}' execution completed in {execution_time:.2f}s")
    
    def log_agent_steps(self, steps: List[Any], agent_name: str) -> None:
        """Log agent execution steps with pretty printing"""
        if self.step_printer and steps:
            try:
                self.step_printer.print_steps(steps, agent_name)
            except Exception as e:
                self.logger.error(f" Error printing steps for agent '{agent_name}': {e}")
                self.logger.debug(f"Raw steps: {steps}")
    
    def log_response_analysis(self, response: Any, agent_name: str) -> None:
        """Log response analysis"""
        try:
            if hasattr(response, 'steps') and response.steps:
                self.logger.info(f"📊 Agent '{agent_name}' executed {len(response.steps)} steps")
                self.log_agent_steps(response.steps, agent_name)
            elif hasattr(response, 'output_message'):
                self.logger.info(f"📝 Agent '{agent_name}' produced direct output")
                content = getattr(response.output_message, 'content', str(response.output_message))
                self.logger.debug(f"Output preview: {content[:200]}{'...' if len(content) > 200 else ''}")
            else:
                self.logger.info(f"📋 Agent '{agent_name}' response format: {type(response).__name__}")
        except Exception as e:
            self.logger.error(f" Error analyzing response for agent '{agent_name}': {e}")

# Global enhanced logger instance
enhanced_logger = EnhancedAgentLogger()

def setup_enhanced_logging(enable_step_printing: bool = True, enable_rich: bool = True) -> EnhancedAgentLogger:
    """Setup enhanced logging with optional step printing"""
    global enhanced_logger
    enhanced_logger = EnhancedAgentLogger(enable_step_printing, enable_rich)
    return enhanced_logger

def get_enhanced_logger() -> EnhancedAgentLogger:
    """Get the global enhanced logger instance"""
    return enhanced_logger

# Utility functions for backward compatibility
def step_printer(steps: List[Any], agent_name: str = "Unknown") -> None:
    """
    Print the steps of an agent's response in a formatted way.
    Note: stream needs to be set to False to use this function.
    
    Args:
        steps: List of steps from an agent's response
        agent_name: Name of the agent for context
    """
    printer = AgentStepPrinter()
    printer.print_steps(steps, agent_name)

def log_agent_execution(response: Any, agent_name: str, execution_time: float = 0) -> None:
    """Log complete agent execution with steps"""
    enhanced_logger.log_agent_execution_start(agent_name, "Query executed")
    enhanced_logger.log_response_analysis(response, agent_name)
    enhanced_logger.log_agent_execution_complete(agent_name, execution_time, True)