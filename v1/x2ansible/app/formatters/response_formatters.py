# app/formatters/response_formatters.py
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class BaseResponseFormatter(ABC):
    """Base formatter for agent responses"""
    
    def __init__(self):
        self.formatter_version = "2.0.0"
    
    @abstractmethod
    def process_raw_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process complete raw response"""
        pass
    
    @staticmethod
    def extract_content(obj, paths: List[str] = None) -> Optional[str]:
        """Extract content from response object"""
        if not obj:
            return None
            
        if paths is None:
            paths = ['content', 'step_output', 'output', 'message', 'text',
                    'api_model_response.content', 'model_response.content']
        
        for path in paths:
            try:
                value = obj
                for attr in path.split('.'):
                    if hasattr(value, attr):
                        value = getattr(value, attr)
                    else:
                        value = None
                        break
                        
                if value and isinstance(value, str):
                    return value.strip()
                elif value:
                    return str(value).strip()
            except (AttributeError, TypeError):
                continue
        return None

    @staticmethod
    def safe_json_parse(content: str) -> Optional[Dict]:
        """Parse JSON with fallbacks"""
        if not content:
            return None
            
        content = content.strip()
        
        # Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Extract JSON block
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end+1])
            except json.JSONDecodeError:
                pass
        
        return None

class StandardResponseFormatter(BaseResponseFormatter):
    """Formatter for standard LlamaStack agents"""
    
    def process_raw_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"Processing standard response for {context.get('agent_name')}")
        
        content = self.extract_content(raw_response)
        if not content:
            content = str(raw_response) if raw_response else ""
        
        # Try JSON parsing
        json_data = self.safe_json_parse(content)
        if json_data:
            return {
                "success": True,
                "data": json_data,
                "final_answer": json_data,
                "content_type": "json",
                "agent_name": context.get("agent_name"),
                "execution_time": context.get("execution_time", 0),
                "formatter": "StandardResponseFormatter"
            }
        
        return {
            "success": True,
            "final_answer": content,
            "content_type": "text",
            "agent_name": context.get("agent_name"),
            "execution_time": context.get("execution_time", 0),
            "formatter": "StandardResponseFormatter"
        }

class ReActResponseFormatter(BaseResponseFormatter):
    """Enhanced formatter for ReAct agents with IaC analysis support"""
    
    def __init__(self):
        super().__init__()
        # Import here to avoid circular imports
        try:
            from app.processors.iac_response_processor import IaCResponseProcessor
            self.iac_processor = IaCResponseProcessor()
        except ImportError:
            logger.warning("IaCResponseProcessor not available, using fallback")
            self.iac_processor = None
    
    def process_raw_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"Processing ReAct response for {context.get('agent_name')}")
        
        agent_name = context.get("agent_name", "")
        
        # Check if this is an IaC analysis agent and processor is available
        if agent_name == "iac_phased_analysis_agent" and self.iac_processor:
            return self._process_iac_analysis_response(raw_response, context)
        else:
            return self._process_general_react_response(raw_response, context)
    
    def _process_iac_analysis_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process IaC analysis ReAct response using specialized processor"""
        try:
            # Use the specialized IaC processor
            result = self.iac_processor.process_react_response(raw_response, context)
            
            # Add ReAct-specific metadata
            result["agent_name"] = context.get("agent_name")
            result["execution_time"] = context.get("execution_time", 0)
            result["formatter"] = "ReActResponseFormatter"
            result["content_type"] = "structured_iac_analysis"
            
            return result
            
        except Exception as e:
            logger.error(f"IaC analysis processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"IaC analysis processing failed: {str(e)}",
                "agent_name": context.get("agent_name"),
                "formatter": "ReActResponseFormatter"
            }
    
    def _process_general_react_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process general ReAct response (original logic)"""
        if not hasattr(raw_response, 'steps') or not raw_response.steps:
            return {
                "success": False,
                "error": "No steps in ReAct response",
                "agent_name": context.get("agent_name"),
                "formatter": "ReActResponseFormatter"
            }
        
        # Process steps with enhanced ReAct step analysis
        steps_info = []
        reasoning_phases = []
        
        for i, step in enumerate(raw_response.steps):
            step_content = self.extract_content(step)
            step_info = {
                "step": i + 1,
                "type": type(step).__name__,
                "content": step_content,
                "has_tools": hasattr(step, 'tool_responses') and bool(getattr(step, 'tool_responses', [])),
                "thought": self._extract_thought_from_content(step_content),
                "action": self._extract_action_from_content(step_content),
                "observation": self._extract_observation_from_content(step_content)
            }
            steps_info.append(step_info)
            
            # Identify reasoning phase
            if step_content:
                phase = self._identify_reasoning_phase(step_content)
                if phase:
                    reasoning_phases.append({
                        "step": i + 1,
                        "phase": phase
                    })
        
        # Extract final result
        last_step = raw_response.steps[-1]
        final_content = self.extract_content(last_step, [
            'step_output', 'output', 'api_model_response.content', 'content'
        ])
        
        if not final_content:
            return {
                "success": False,
                "error": "Could not extract final result",
                "steps": steps_info,
                "agent_name": context.get("agent_name"),
                "formatter": "ReActResponseFormatter"
            }
        
        # Parse final result
        json_result = self.safe_json_parse(final_content)
        if json_result:
            # Handle ReAct answer structure
            if isinstance(json_result, dict) and 'answer' in json_result:
                answer = json_result['answer']
                if isinstance(answer, str) and answer.startswith('{'):
                    final_answer = self.safe_json_parse(answer) or answer
                else:
                    final_answer = answer
            else:
                final_answer = json_result
        else:
            final_answer = final_content
        
        return {
            "success": True,
            "final_answer": final_answer,
            "data": final_answer if isinstance(final_answer, dict) else {"answer": final_answer},
            "steps": steps_info,
            "total_steps": len(steps_info),
            "reasoning_phases": reasoning_phases,
            "agent_name": context.get("agent_name"),
            "execution_time": context.get("execution_time", 0),
            "formatter": "ReActResponseFormatter"
        }
    
    def _extract_thought_from_content(self, content: str) -> Optional[str]:
        """Extract thought from step content"""
        if not content:
            return None
            
        patterns = [
            r'(?:THOUGHT|Thought):\s*(.+?)(?=(?:ACTION|Action):|$)',
            r'(?:Think|THINK):\s*(.+?)(?=(?:ACT|Act):|$)',
            r'"thought":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_action_from_content(self, content: str) -> Optional[str]:
        """Extract action from step content"""
        if not content:
            return None
            
        patterns = [
            r'(?:ACTION|Action):\s*(.+?)(?=(?:OBSERVATION|Observation):|$)',
            r'(?:ACT|Act):\s*(.+?)(?=(?:OBSERVE|Observe):|$)',
            r'"action":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_observation_from_content(self, content: str) -> Optional[str]:
        """Extract observation from step content"""
        if not content:
            return None
            
        patterns = [
            r'(?:OBSERVATION|Observation):\s*(.+?)$',
            r'(?:OBSERVE|Observe):\s*(.+?)$',
            r'"observation":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _identify_reasoning_phase(self, content: str) -> Optional[str]:
        """Identify the reasoning phase from step content"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ["extract", "identify", "analyze files", "examine code"]):
            return "extraction"
        elif any(word in content_lower for word in ["assess", "evaluate", "determine complexity", "analyze"]):
            return "analysis"
        elif any(word in content_lower for word in ["recommend", "suggest", "migration", "modernize"]):
            return "recommendation"
        
        return "reasoning"

class ResponseFormatterManager:
    """Manages all response formatters"""
    
    def __init__(self):
        self.formatters = {
            'standard': StandardResponseFormatter(),
            'react': ReActResponseFormatter()
        }
    
    def process_response(self, raw_response: Any, agent_name: str, agent_type: str, **context) -> Dict[str, Any]:
        """Process response with appropriate formatter"""
        formatter = self.formatters.get(agent_type.lower(), self.formatters['standard'])
        
        processing_context = {
            "agent_name": agent_name,
            "agent_type": agent_type,
            **context
        }
        
        try:
            return formatter.process_raw_response(raw_response, processing_context)
        except Exception as e:
            logger.error(f"Formatter error: {e}")
            return {
                "success": False,
                "error": f"Formatter error: {str(e)}",
                "agent_name": agent_name,
                "agent_type": agent_type
            }