"""
Utility functions for BladeLogic Analysis Agent.
Pattern-based extraction for BladeLogic objects (Jobs, Packages, Policies, Scripts).
"""
import re
import logging
from typing import Optional, Dict, Any, List
import uuid

# Create a simple exception class since shared.exceptions might not exist yet
class JSONParseError(Exception):
    """JSON parsing error"""
    pass

logger = logging.getLogger(__name__)

class BladeLogicExtractor:
    """Extracts BladeLogic information using pattern matching."""
    
    @staticmethod
    def detect_bladelogic_type(content: str, filename: str = "") -> str:
        """
        Detect BladeLogic object type from content.
        Returns: JOB, PACKAGE, POLICY, SCRIPT, UNKNOWN
        """
        content_lower = content.lower()
        
        # Check filename first
        if filename:
            fname_lower = filename.lower()
            if "job" in fname_lower:
                return "JOB"
            elif "package" in fname_lower or "pkg" in fname_lower:
                return "PACKAGE"
            elif "policy" in fname_lower or "pol" in fname_lower:
                return "POLICY"
            elif fname_lower.endswith(('.nsh', '.sh')):
                return "SCRIPT"
        
        # Content-based detection
        job_indicators = [
            'blcli job',
            'nexec',
            'blcli_execute',
            'job create',
            'job run'
        ]
        
        package_indicators = [
            'blpackage',
            'package create',
            'software package',
            'depot object'
        ]
        
        policy_indicators = [
            'blpolicy',
            'compliance policy',
            'policy create',
            'compliance rule'
        ]
        
        script_indicators = [
            '#!/bin/nsh',
            'nsh -c',
            'blcli ',
            'nexec -f'
        ]
        
        for indicator in job_indicators:
            if indicator in content_lower:
                return "JOB"
        
        for indicator in package_indicators:
            if indicator in content_lower:
                return "PACKAGE"
        
        for indicator in policy_indicators:
            if indicator in content_lower:
                return "POLICY"
        
        for indicator in script_indicators:
            if indicator in content_lower:
                return "SCRIPT"
        
        return "UNKNOWN"
    
    @staticmethod
    def extract_bladelogic_metadata(content: str, object_type: str) -> Dict[str, Any]:
        """Extract metadata from BladeLogic content."""
        metadata = {
            "name": BladeLogicExtractor._extract_object_name(content, object_type),
            "description": BladeLogicExtractor._extract_description(content),
            "version": BladeLogicExtractor._extract_version(content),
            "author": BladeLogicExtractor._extract_author(content),
            "target_platforms": BladeLogicExtractor._extract_target_platforms(content)
        }
        return {k: v for k, v in metadata.items() if v}
    
    @staticmethod
    def _extract_object_name(content: str, object_type: str) -> Optional[str]:
        """Extract object name based on type."""
        patterns = {
            "JOB": [
                r'job\s+create\s+["\']([^"\']+)["\']',
                r'JobName[:\s=]+["\']?([^"\'\\n]+)["\']?',
                r'blcli\s+job\s+["\']([^"\']+)["\']'
            ],
            "PACKAGE": [
                r'package\s+create\s+["\']([^"\']+)["\']',
                r'PackageName[:\s=]+["\']?([^"\'\\n]+)["\']?',
                r'blpackage\s+["\']([^"\']+)["\']'
            ],
            "POLICY": [
                r'policy\s+create\s+["\']([^"\']+)["\']',
                r'PolicyName[:\s=]+["\']?([^"\'\\n]+)["\']?',
                r'blpolicy\s+["\']([^"\']+)["\']'
            ],
            "SCRIPT": [
                r'# Script:\s*([^\\n]+)',
                r'# Name:\s*([^\\n]+)',
                r'echo\s+["\']Script:\s*([^"\']+)["\']'
            ]
        }
        
        for pattern in patterns.get(object_type, []):
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    @staticmethod
    def _extract_description(content: str) -> Optional[str]:
        """Extract description from content."""
        patterns = [
            r'Description[:\s=]+["\']?([^"\'\\n]+)["\']?',
            r'# Description:\s*([^\\n]+)',
            r'# Purpose:\s*([^\\n]+)',
            r'echo\s+["\']Description:\s*([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    @staticmethod
    def _extract_version(content: str) -> Optional[str]:
        """Extract version information."""
        patterns = [
            r'Version[:\s=]+["\']?([^"\'\\n]+)["\']?',
            r'# Version:\s*([^\\n]+)',
            r'blcli.*version\s+([\\d\\.]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    @staticmethod
    def _extract_author(content: str) -> Optional[str]:
        """Extract author information."""
        patterns = [
            r'Author[:\s=]+["\']?([^"\'\\n]+)["\']?',
            r'# Author:\s*([^\\n]+)',
            r'# Created by:\s*([^\\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    @staticmethod
    def _extract_target_platforms(content: str) -> List[str]:
        """Extract target platforms."""
        platforms = []
        platform_patterns = {
            'Windows': r'(?i)(windows|win32|win64|microsoft)',
            'Linux': r'(?i)(linux|rhel|centos|ubuntu|debian|suse)',
            'AIX': r'(?i)(aix|unix)',
            'Solaris': r'(?i)(solaris|sunos)',
            'HPUX': r'(?i)(hpux|hp-ux)'
        }
        
        for platform, pattern in platform_patterns.items():
            if re.search(pattern, content):
                platforms.append(platform)
        
        return platforms
    
    @staticmethod
    def extract_bladelogic_operations(content: str, object_type: str) -> Dict[str, List[str]]:
        """Extract operations performed by BladeLogic object."""
        operations = {
            "services": [],
            "packages": [],
            "files": [],
            "commands": [],
            "policies": []
        }
        
        # Service operations
        service_patterns = [
            r'service\s+([\\w\\-\\.]+)\s+(?:start|stop|restart|enable|disable)',
            r'systemctl\s+(?:start|stop|restart|enable|disable)\s+([\\w\\-\\.]+)',
            r'net\s+(?:start|stop)\s+([\\w\\-\\.]+)'
        ]
        
        for pattern in service_patterns:
            operations["services"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Package operations
        package_patterns = [
            r'(?:yum|apt-get|rpm)\s+install\s+([\\w\\-\\.]+)',
            r'msiexec.*["\']([^"\']+\\.msi)["\']',
            r'software\s+package\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in package_patterns:
            operations["packages"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # File operations
        file_patterns = [
            r'(?:copy|cp|move|mv)\s+["\']?([^"\'\\s]+)["\']?',
            r'echo\s+.*>\s*["\']?([^"\'\\s]+)["\']?',
            r'blcli\s+file\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in file_patterns:
            operations["files"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Commands
        command_patterns = [
            r'nexec\s+-c\s+["\']([^"\']+)["\']',
            r'blcli_execute\s+["\']([^"\']+)["\']',
            r'system\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in command_patterns:
            operations["commands"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Deduplicate and clean
        for key in operations:
            operations[key] = list(dict.fromkeys([op.strip() for op in operations[key] if op.strip()]))
            # Limit to reasonable number
            operations[key] = operations[key][:10]
        
        return operations

class BladeLogicValidator:
    """Validates BladeLogic input data."""
    
    @staticmethod
    def validate_bladelogic_input(bladelogic_data: Dict[str, Any]) -> None:
        """Validate BladeLogic input structure."""
        if not isinstance(bladelogic_data, dict):
            raise ValueError("BladeLogic data must be a dictionary")
        
        if "files" not in bladelogic_data:
            raise ValueError("BladeLogic data must contain 'files' key")
        
        files = bladelogic_data["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("Files must be a non-empty dictionary")
        
        for filename, content in files.items():
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError(f"Invalid filename: {filename}")
            
            if not isinstance(content, str):
                raise ValueError(f"File content must be string for {filename}")

def create_correlation_id() -> str:
    """Generate correlation ID for request tracking."""
    import uuid
    return str(uuid.uuid4())[:8]

def format_bladelogic_for_analysis(bladelogic_data: Dict[str, Any]) -> str:
    """Format BladeLogic files for LLM analysis."""
    BladeLogicValidator.validate_bladelogic_input(bladelogic_data)
    
    files = bladelogic_data["files"]
    object_name = bladelogic_data.get("name", "unknown")
    
    formatted_parts = [f"BladeLogic Object: {object_name}", ""]
    
    for filename, content in files.items():
        object_type = BladeLogicExtractor.detect_bladelogic_type(content, filename)
        formatted_parts.extend([
            f"=== File: {filename} (Type: {object_type}) ===",
            content.strip(),
            ""
        ])
    
    return "\\n".join(formatted_parts)