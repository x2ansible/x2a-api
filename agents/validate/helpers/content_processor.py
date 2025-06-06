"""
Content Processor Helper for ValidationAgent

Handles all playbook content preprocessing, cleaning, and validation
before sending to ansible-lint service.
"""

import logging
import re
import yaml
from typing import Tuple, Optional

logger = logging.getLogger("ContentProcessor")

class ContentProcessor:
    """Handles preprocessing of Ansible playbook content."""
    
    def __init__(self, enable_prevalidation: bool = False):
        self.enable_prevalidation = enable_prevalidation
    
    def process_playbook_content(self, raw_playbook: str) -> Tuple[str, Optional[dict]]:
        """
        Process raw playbook content for validation.
        
        Args:
            raw_playbook: Raw playbook content from user input
            
        Returns:
            Tuple of (cleaned_content, error_result_or_none)
            If error_result is not None, processing failed.
        """
        logger.info(f"📥 Processing playbook: {len(raw_playbook)} chars")
        logger.info(f"📝 Raw input preview: {repr(raw_playbook[:100])}")
        
        try:
            # Step 1: Basic cleaning
            cleaned = self._clean_content(raw_playbook)
            
            # Step 2: Remove wrapper quotes 
            cleaned = self._remove_wrapper_quotes(cleaned)
            
            # Step 3: Fix escaped characters
            cleaned = self._fix_escaped_characters(cleaned)
            
            # Step 4: Ensure proper YAML document marker
            cleaned = self._ensure_yaml_document_marker(cleaned)
            
            # Step 5: Optional pre-validation
            if self.enable_prevalidation:
                validation_error = self._validate_yaml_structure(cleaned)
                if validation_error:
                    return cleaned, validation_error
            
            logger.info(f"🧹 Content processed successfully: {len(cleaned)} chars")
            logger.info("🧾 Processed preview (first 10 lines):")
            for i, line in enumerate(cleaned.split('\n')[:10], 1):
                logger.info(f"  {i:2d}: {line}")
                
            return cleaned, None
            
        except Exception as e:
            logger.error(f" Content processing failed: {e}")
            error_result = self._create_processing_error(str(e))
            return raw_playbook, error_result
    
    def _clean_content(self, content: str) -> str:
        """Basic content cleaning."""
        return content.strip()
    
    def _remove_wrapper_quotes(self, content: str) -> str:
        """Remove wrapper quotes if entire content is quoted."""
        original_length = len(content)
        
        # Remove triple quotes
        if content.startswith("'''") and content.endswith("'''"):
            content = content[3:-3].strip()
            logger.info("🧹 Removed triple single quotes")
        elif content.startswith('"""') and content.endswith('"""'):
            content = content[3:-3].strip()
            logger.info("🧹 Removed triple double quotes")
        # Remove single/double quotes (only for multi-line content)
        elif content.startswith("'") and content.endswith("'") and content.count('\n') > 1:
            content = content[1:-1].strip()
            logger.info("🧹 Removed single quotes")
        elif content.startswith('"') and content.endswith('"') and content.count('\n') > 1:
            content = content[1:-1].strip()
            logger.info("🧹 Removed double quotes")
        
        if len(content) != original_length:
            logger.info(f"🧹 Quote removal: {original_length} → {len(content)} chars")
            
        return content
    
    def _fix_escaped_characters(self, content: str) -> str:
        """Fix JSON-escaped characters from LlamaStack tool calls."""
        if '\\n' in content and content.count('\\n') > content.count('\n'):
            logger.info("🔧 Fixing escaped newlines and tabs")
            content = content.replace('\\n', '\n').replace('\\t', '\t')
        return content
    
    def _ensure_yaml_document_marker(self, content: str) -> str:
        """Ensure proper YAML document marker."""
        # Remove existing document markers
        content = re.sub(r"^('?-{3,}'?\n?)+", '', content, flags=re.MULTILINE)
        
        # Add single document marker
        if not content.startswith('---'):
            content = '---\n' + content.lstrip()
            logger.info("📝 Added YAML document marker")
        
        return content
    
    def _validate_yaml_structure(self, content: str) -> Optional[dict]:
        """
        Validate YAML structure before sending to lint service.
        
        Returns:
            Error result dict if validation fails, None if passes
        """
        try:
            parsed = yaml.safe_load(content)
            
            if parsed is None:
                return self._create_validation_error("Parsed YAML is empty")
            
            if not isinstance(parsed, list):
                return self._create_validation_error(
                    f"Playbook must be a list of plays, got {type(parsed).__name__}"
                )
            
            # Validate each play
            for i, play in enumerate(parsed):
                if not isinstance(play, dict):
                    return self._create_validation_error(
                        f"Play {i+1} must be a dictionary, got {type(play).__name__}"
                    )
                
                if 'hosts' not in play and 'import_playbook' not in play:
                    return self._create_validation_error(
                        f"Play {i+1} must have 'hosts' or 'import_playbook' defined"
                    )
            
            logger.info(f" YAML pre-validation passed: {len(parsed)} plays found")
            return None
            
        except yaml.YAMLError as e:
            return self._create_validation_error(f"Invalid YAML syntax: {str(e)}")
        except Exception as e:
            logger.warning(f"⚠️ YAML pre-validation warning: {e}")
            return None  # Continue anyway
    
    def _create_validation_error(self, error_message: str) -> dict:
        """Create error result for YAML validation failures."""
        return {
            "validation_passed": False,
            "exit_code": -10,
            "message": f" YAML validation failed: {error_message}",
            "summary": {
                "passed": False,
                "violations": 1,
                "warnings": 0,
                "total_issues": 1,
                "error": True,
                "error_type": "yaml_validation"
            },
            "issues": [{
                "rule": "yaml-syntax",
                "category": "syntax",
                "description": error_message,
                "severity": "fatal",
                "file": "playbook.yml"
            }],
            "recommendations": [{
                "issue": "yaml-syntax",
                "recommendation": "Fix YAML syntax errors",
                "action": "Check YAML structure and formatting",
                "example": "Ensure proper indentation and no syntax errors"
            }],
            "raw_output": {"stdout": "", "stderr": error_message}
        }
    
    def _create_processing_error(self, error_message: str) -> dict:
        """Create error result for processing failures."""
        return {
            "validation_passed": False,
            "exit_code": -20,
            "message": f" Content processing failed: {error_message}",
            "summary": {
                "passed": False,
                "violations": 1,
                "warnings": 0,
                "total_issues": 1,
                "error": True,
                "error_type": "processing_error"
            },
            "issues": [{
                "rule": "content-processing",
                "category": "system",
                "description": error_message,
                "severity": "fatal",
                "file": "system"
            }],
            "recommendations": [],
            "raw_output": {"stdout": "", "stderr": error_message}
        }