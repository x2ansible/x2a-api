"""
Utility functions for Chef Analysis Agent.
Focuses on JSON extraction from LLM responses with streaming support.
"""
import json
import re
import logging
from typing import Optional, Dict, Any, Generator, List
from shared.exceptions import JSONParseError

logger = logging.getLogger(__name__)


class JSONExtractor:
    """Extracts JSON from LLM responses with streaming support."""
    
    @staticmethod
    def extract_json_from_text(text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM text response.
        Handles common LLM response formats with JSON embedded in text.
        """
        if not text or not text.strip():
            raise JSONParseError("Empty response text", text)
        
        # Try direct JSON parsing first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON block in text
        json_patterns = [
            # JSON code blocks
            r'```json\s*(\{.*?\})\s*```',
            # JSON without code blocks
            r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',
            # Simple JSON objects
            r'(\{.*?\})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    cleaned_json = JSONExtractor._clean_json_string(match)
                    return json.loads(cleaned_json)
                except json.JSONDecodeError:
                    continue
        
        raise JSONParseError(f"No valid JSON found in response", text)
    
    @staticmethod
    def _clean_json_string(json_str: str) -> str:
        """Clean common issues in LLM-generated JSON strings."""
        # Remove leading/trailing whitespace
        json_str = json_str.strip()
        
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix unescaped quotes in string values
        json_str = re.sub(r'(?<!\\)"(?=[^,}\]:]*(?:[,}\]:]|$))', r'\\"', json_str)
        
        return json_str
    
    @staticmethod
    def extract_partial_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to extract partial JSON from incomplete streaming response.
        Returns None if no valid partial JSON can be extracted.
        """
        try:
            # Look for opening brace and try to find valid partial structure
            start_idx = text.find('{')
            if start_idx == -1:
                return None
            
            # Find the last complete key-value pair
            partial_text = text[start_idx:]
            
            # Try to create valid JSON by adding closing brace
            for i in range(len(partial_text) - 1, -1, -1):
                if partial_text[i] in ',}':
                    test_json = partial_text[:i+1]
                    if not test_json.endswith(','):
                        test_json += '}'
                    else:
                        test_json = test_json[:-1] + '}'
                    
                    try:
                        return json.loads(test_json)
                    except json.JSONDecodeError:
                        continue
            
            return None
        except Exception:
            return None


class InputValidator:
    """Validates input data for Chef cookbook analysis."""
    
    @staticmethod
    def validate_cookbook_input(cookbook_data: Dict[str, Any]) -> None:
        """
        Basic validation of cookbook input structure.
        Lets LLM handle semantic validation of Chef cookbook content.
        """
        if not isinstance(cookbook_data, dict):
            raise ValueError("Cookbook data must be a dictionary")
        
        if "files" not in cookbook_data:
            raise ValueError("Cookbook data must contain 'files' key")
        
        files = cookbook_data["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("Files must be a non-empty dictionary")
        
        # Basic file content validation
        for filename, content in files.items():
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError(f"Invalid filename: {filename}")
            
            if not isinstance(content, str):
                raise ValueError(f"File content must be string for {filename}")
            
            if len(content.strip()) == 0:
                raise ValueError(f"File content cannot be empty for {filename}")
    
    @staticmethod
    def sanitize_cookbook_name(name: str) -> str:
        """Sanitize cookbook name for safe processing."""
        if not name or not isinstance(name, str):
            return "unknown-cookbook"
        
        # Remove potentially problematic characters
        sanitized = re.sub(r'[^\w\-\.]', '_', name.strip())
        return sanitized[:100]  # Limit length


def create_correlation_id() -> str:
    """Generate correlation ID for request tracking."""
    import uuid
    return str(uuid.uuid4())[:8]


def format_cookbook_for_analysis(cookbook_data: Dict[str, Any]) -> str:
    """
    Format cookbook files into text suitable for LLM analysis.
    Minimal formatting - lets LLM understand Chef structure naturally.
    """
    InputValidator.validate_cookbook_input(cookbook_data)
    
    files = cookbook_data["files"]
    cookbook_name = cookbook_data.get("name", "unknown")
    
    # Simple format that preserves file structure
    formatted_parts = [f"Cookbook: {cookbook_name}", ""]
    
    for filename, content in files.items():
        formatted_parts.extend([
            f"=== File: {filename} ===",
            content.strip(),
            ""
        ])
    
    return "\n".join(formatted_parts)