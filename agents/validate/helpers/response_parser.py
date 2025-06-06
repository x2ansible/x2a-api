"""
Fixed Response Parser - Direct Response Processing

This version processes the LlamaStack response directly without relying on EventLogger,
which may not be available or may have changed in different versions.
"""

import logging
import json
from typing import Dict, Any, List, Tuple, Optional, Union

logger = logging.getLogger("ResponseParser")

class ValidationResponseParser:
    """
    Parser for LlamaStack agent responses that works directly with response objects.
    No dependency on EventLogger which may not be available.
    """
    
    def __init__(self):
        self.target_tool_name = "ansible_lint_tool"

    def parse_agent_response(self, response) -> Tuple[Optional[Dict], str, Dict[str, Any]]:
        """
        Parse LlamaStack agent response directly without EventLogger.
        
        Args:
            response: LlamaStack agent response object
            
        Returns:
            Tuple of (validation_result_or_none, agent_text, debug_info)
        """
        if not response:
            logger.error(" No response provided to parser")
            return None, "", {"error": "no_response_provided", "extraction_successful": False}
        
        logger.info("🔍 Starting direct response parsing")
        
        try:
            agent_text = ""
            tool_results = []
            events_processed = 0
            
            # Try different ways to access the response data
            validation_result = None
            
            # Method 1: Direct response iteration (if response is iterable)
            if hasattr(response, '__iter__'):
                try:
                    for item in response:
                        events_processed += 1
                        logger.debug(f"🔍 Processing response item {events_processed}: {type(item)}")
                        
                        # Try to extract from item
                        result = self._extract_from_response_item(item)
                        if result:
                            tool_results.append(result)
                            
                        # Extract text
                        text = self._extract_text_from_item(item)
                        if text:
                            agent_text += text
                            
                except Exception as e:
                    logger.debug(f"Response iteration failed: {e}")
            
            # Method 2: Direct attribute access
            if not tool_results:
                direct_result = self._extract_from_direct_attributes(response)
                if direct_result:
                    tool_results.append(direct_result)
                    events_processed += 1
            
            # Method 3: Try to access response as string and parse
            if not tool_results:
                string_result = self._extract_from_string_representation(response)
                if string_result:
                    tool_results.append(string_result)
                    events_processed += 1
            
            # Method 4: Check for streaming response format
            if not tool_results:
                stream_result = self._extract_from_streaming_response(response)
                if stream_result:
                    tool_results.append(stream_result)
                    events_processed += 1
            
            # Find the best validation result
            validation_result = self._find_best_validation_result(tool_results)
            
            # Compile debug information
            debug_info = {
                "tool_results_found": len(tool_results),
                "events_processed": events_processed,
                "agent_text_length": len(agent_text),
                "parsing_mode": "direct_response_processing",
                "extraction_successful": validation_result is not None,
                "response_type": str(type(response))
            }
            
            # Log parsing summary
            logger.info(f"📋 Direct parsing summary:")
            logger.info(f"   - Agent text: {len(agent_text)} chars")
            logger.info(f"   - Tool results found: {len(tool_results)}")
            logger.info(f"   - Events processed: {events_processed}")
            logger.info(f"   - Response type: {type(response)}")
            
            if validation_result:
                logger.info(" Successfully extracted validation result!")
            else:
                logger.warning("⚠️ No validation result found")
                if tool_results:
                    logger.debug(f"🔍 Available tool results: {tool_results}")
            
            return validation_result, agent_text.strip(), debug_info
            
        except Exception as e:
            logger.error(f" Critical response parsing failure: {e}")
            logger.exception("Full parsing exception details:")
            
            return None, "", {
                "error": "critical_parsing_failure",
                "error_message": str(e),
                "extraction_successful": False,
                "parsing_mode": "error_recovery"
            }

    def _extract_from_response_item(self, item) -> Optional[Dict]:
        """Extract validation result from a response item."""
        try:
            # Check if item is directly a dict with validation result
            if isinstance(item, dict) and 'validation_passed' in item:
                logger.info(" Found validation result in direct dict item")
                return item
            
            # Check if item has tool execution info
            item_str = str(item)
            if self.target_tool_name in item_str and 'validation_passed' in item_str:
                # Try to extract JSON from the string representation
                result = self._extract_json_from_string(item_str)
                if result:
                    logger.info(" Found validation result in item string")
                    return result
            
            # Check for specific attributes that might contain the result
            if hasattr(item, 'tool_result'):
                if isinstance(item.tool_result, dict) and 'validation_passed' in item.tool_result:
                    logger.info(" Found validation result in item.tool_result")
                    return item.tool_result
            
            if hasattr(item, 'content'):
                if isinstance(item.content, dict) and 'validation_passed' in item.content:
                    logger.info(" Found validation result in item.content")
                    return item.content
                elif isinstance(item.content, str):
                    result = self._extract_json_from_string(item.content)
                    if result:
                        logger.info(" Found validation result in parsed item.content")
                        return result
            
            # Check for payload attribute
            if hasattr(item, 'payload'):
                if isinstance(item.payload, dict) and 'validation_passed' in item.payload:
                    logger.info(" Found validation result in item.payload")
                    return item.payload
                    
        except Exception as e:
            logger.debug(f"Error extracting from response item: {e}")
            
        return None

    def _extract_from_direct_attributes(self, response) -> Optional[Dict]:
        """Extract from direct response attributes."""
        try:
            # Check common attribute names
            attributes_to_check = [
                'result', 'tool_result', 'validation_result', 
                'content', 'data', 'payload', 'output'
            ]
            
            for attr_name in attributes_to_check:
                if hasattr(response, attr_name):
                    attr_value = getattr(response, attr_name)
                    
                    if isinstance(attr_value, dict) and 'validation_passed' in attr_value:
                        logger.info(f" Found validation result in response.{attr_name}")
                        return attr_value
                    
                    elif isinstance(attr_value, str):
                        result = self._extract_json_from_string(attr_value)
                        if result:
                            logger.info(f" Found validation result in parsed response.{attr_name}")
                            return result
                            
        except Exception as e:
            logger.debug(f"Error extracting from direct attributes: {e}")
            
        return None

    def _extract_from_string_representation(self, response) -> Optional[Dict]:
        """Extract from string representation of response."""
        try:
            response_str = str(response)
            
            if self.target_tool_name in response_str and 'validation_passed' in response_str:
                result = self._extract_json_from_string(response_str)
                if result:
                    logger.info(" Found validation result in response string representation")
                    return result
                    
        except Exception as e:
            logger.debug(f"Error extracting from string representation: {e}")
            
        return None

    def _extract_from_streaming_response(self, response) -> Optional[Dict]:
        """Extract from streaming response format."""
        try:
            # Check if response has a streaming format
            if hasattr(response, 'events'):
                for event in response.events:
                    result = self._extract_from_response_item(event)
                    if result:
                        logger.info(" Found validation result in streaming event")
                        return result
                        
            # Check for other streaming attributes
            if hasattr(response, 'stream'):
                for item in response.stream:
                    result = self._extract_from_response_item(item)
                    if result:
                        logger.info(" Found validation result in stream item")
                        return result
                        
        except Exception as e:
            logger.debug(f"Error extracting from streaming response: {e}")
            
        return None

    def _extract_text_from_item(self, item) -> Optional[str]:
        """Extract agent text from response item."""
        try:
            # Convert item to string and check for inference text
            item_str = str(item)
            
            # Look for inference patterns
            if item_str.startswith("inference> ") and not item_str.startswith("inference> ["):
                text = item_str[len("inference> "):]
                if text.strip() and not text.startswith("call_id="):  # Skip tool calls
                    return text + "\n"
            
            # Check for message attributes
            if hasattr(item, 'message') and item.message:
                message = str(item.message).strip()
                if message and not message.startswith('[') and not message.startswith('{'):
                    return message + "\n"
            
            # Check for content attributes
            if hasattr(item, 'content') and isinstance(item.content, str):
                content = item.content.strip()
                if content and not content.startswith('{') and not content.startswith('['):
                    return content + "\n"
                    
        except Exception as e:
            logger.debug(f"Error extracting text from item: {e}")
            
        return None

    def _extract_json_from_string(self, text: str) -> Optional[Dict]:
        """Extract JSON objects from text that contain validation results."""
        try:
            # Find JSON-like structures
            json_candidates = []
            i = 0
            
            while i < len(text):
                if text[i] == '{':
                    # Find matching closing brace
                    brace_count = 1
                    j = i + 1
                    
                    while j < len(text) and brace_count > 0:
                        if text[j] == '{':
                            brace_count += 1
                        elif text[j] == '}':
                            brace_count -= 1
                        j += 1
                    
                    if brace_count == 0:
                        json_candidate = text[i:j]
                        json_candidates.append(json_candidate)
                    
                    i = j
                else:
                    i += 1
            
            # Try to parse each candidate
            for candidate in json_candidates:
                try:
                    # Clean up the JSON string
                    cleaned = self._clean_json_string(candidate)
                    parsed = json.loads(cleaned)
                    
                    if isinstance(parsed, dict) and 'validation_passed' in parsed:
                        return parsed
                        
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting JSON from string: {e}")
            
        return None

    def _clean_json_string(self, json_str: str) -> str:
        """Clean up JSON string for parsing."""
        # Remove common prefixes/suffixes
        json_str = json_str.strip()
        
        # Remove quotes if the entire string is quoted
        if json_str.startswith('"') and json_str.endswith('"'):
            json_str = json_str[1:-1]
        
        # Unescape common escape sequences
        json_str = json_str.replace('\\"', '"')
        json_str = json_str.replace('\\\\n', '\n')
        json_str = json_str.replace('\\\\t', '\t')
        json_str = json_str.replace('\\n', '\n')
        json_str = json_str.replace('\\t', '\t')
        
        return json_str

    def _find_best_validation_result(self, tool_results: List) -> Optional[Dict]:
        """Find the best validation result from collected tool results."""
        for i, tool_result in enumerate(tool_results):
            logger.debug(f"🔍 Checking tool result {i}: {type(tool_result)}")
            
            # Direct dict with validation_passed
            if isinstance(tool_result, dict) and 'validation_passed' in tool_result:
                logger.info(f" Found validation result: passed={tool_result.get('validation_passed')}")
                return tool_result
            
            # Check for alternative status fields
            elif isinstance(tool_result, dict) and 'passed' in tool_result:
                # Convert 'passed' to 'validation_passed' for consistency
                tool_result['validation_passed'] = tool_result['passed']
                logger.info(f" Found validation result with 'passed' field: {tool_result.get('passed')}")
                return tool_result
                
            # Object with content attribute
            elif hasattr(tool_result, 'content') and isinstance(tool_result.content, dict):
                if 'validation_passed' in tool_result.content:
                    logger.info(" Found validation result in content attribute")
                    return tool_result.content
        
        return None

    def get_parser_stats(self) -> Dict[str, Any]:
        """Get parser statistics and configuration."""
        return {
            "target_tool_name": self.target_tool_name,
            "parser_version": "2.2.0",
            "uses_event_logger": False,
            "extraction_methods": 4
        }