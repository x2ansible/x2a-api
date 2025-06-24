import re
import logging
from typing import Optional, Dict, Any, List
import uuid

logger = logging.getLogger(__name__)

class ShellExtractor:
    """Extracts shell script information using pattern matching."""
    
    @staticmethod
    def detect_shell_type(content: str, filename: str = "") -> str:
        """Detect shell script type and purpose."""
        content_lower = content.lower()
        
        # Check shebang first
        if content.startswith('#!/bin/bash') or content.startswith('#!/usr/bin/bash'):
            shell_type = "bash"
        elif content.startswith('#!/bin/zsh') or content.startswith('#!/usr/bin/zsh'):
            shell_type = "zsh"
        elif content.startswith('#!/bin/sh') or content.startswith('#!/usr/bin/sh'):
            shell_type = "sh"
        else:
            shell_type = "bash"  # default
        
        # Determine script purpose from filename and content
        if filename:
            fname_lower = filename.lower()
            if any(word in fname_lower for word in ['install', 'setup']):
                return f"{shell_type}_INSTALLATION"
            elif any(word in fname_lower for word in ['deploy', 'deployment']):
                return f"{shell_type}_DEPLOYMENT"
            elif any(word in fname_lower for word in ['config', 'configure']):
                return f"{shell_type}_CONFIGURATION"
            elif any(word in fname_lower for word in ['monitor', 'check', 'health']):
                return f"{shell_type}_MONITORING"
            elif any(word in fname_lower for word in ['backup', 'cleanup', 'maintenance']):
                return f"{shell_type}_MAINTENANCE"
        
        # Content-based detection
        if any(word in content_lower for word in ['apt-get install', 'yum install', 'package install']):
            return f"{shell_type}_INSTALLATION"
        elif any(word in content_lower for word in ['systemctl', 'service start', 'docker run']):
            return f"{shell_type}_DEPLOYMENT"
        elif any(word in content_lower for word in ['grep', 'ps aux', 'netstat', 'curl -f']):
            return f"{shell_type}_MONITORING"
        else:
            return f"{shell_type}_CONFIGURATION"
    
    @staticmethod
    def extract_shell_metadata(content: str, script_type: str) -> Dict[str, Any]:
        """Extract metadata from shell script content."""
        metadata = {
            "name": ShellExtractor._extract_script_name(content),
            "description": ShellExtractor._extract_description(content),
            "version": ShellExtractor._extract_version(content),
            "author": ShellExtractor._extract_author(content),
            "shell_type": script_type.split('_')[0] if '_' in script_type else 'bash'
        }
        return {k: v for k, v in metadata.items() if v}
    
    @staticmethod
    def _extract_script_name(content: str) -> Optional[str]:
        """Extract script name from comments or filename references."""
        patterns = [
            r'# Script:\s*([^\n]+)',
            r'# Name:\s*([^\n]+)',
            r'# File:\s*([^\n]+)',
            r'echo.*"Script:\s*([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    @staticmethod
    def _extract_description(content: str) -> Optional[str]:
        """Extract description from comments."""
        patterns = [
            r'# Description:\s*([^\n]+)',
            r'# Purpose:\s*([^\n]+)',
            r'# Summary:\s*([^\n]+)',
            r'echo.*"Description:\s*([^"]+)"'
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
            r'# Version:\s*([^\n]+)',
            r'VERSION=[\'"]*([^\'"\n]+)[\'"]*',
            r'version=[\'"]*([^\'"\n]+)[\'"]*'
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
            r'# Author:\s*([^\n]+)',
            r'# Created by:\s*([^\n]+)',
            r'# Maintainer:\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    @staticmethod
    def extract_shell_operations(content: str, script_type: str) -> Dict[str, List[str]]:
        """Extract operations performed by shell script."""
        operations = {
            "packages": [],
            "services": [],
            "files": [],
            "commands": [],
            "network": []
        }
        
        # Package operations
        package_patterns = [
            r'(?:apt-get|apt)\s+install\s+([^\s\n;&&]+)',
            r'yum\s+install\s+([^\s\n;&&]+)',
            r'dnf\s+install\s+([^\s\n;&&]+)',
            r'pip\s+install\s+([^\s\n;&&]+)',
            r'npm\s+install\s+([^\s\n;&&]+)'
        ]
        
        for pattern in package_patterns:
            operations["packages"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Service operations
        service_patterns = [
            r'systemctl\s+(?:start|stop|restart|enable|disable)\s+([^\s\n;&&]+)',
            r'service\s+([^\s\n;&&]+)\s+(?:start|stop|restart)',
            r'docker\s+(?:run|start|stop)\s+[^\s]*\s+([^\s\n;&&]+)'
        ]
        
        for pattern in service_patterns:
            operations["services"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # File operations
        file_patterns = [
            r'(?:cp|copy|mv|move)\s+[^\s]+\s+([^\s\n;&&]+)',
            r'echo.*>\s*([^\s\n;&&]+)',
            r'touch\s+([^\s\n;&&]+)',
            r'mkdir\s+(?:-p\s+)?([^\s\n;&&]+)'
        ]
        
        for pattern in file_patterns:
            operations["files"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Important commands
        command_patterns = [
            r'curl\s+[^\n;&&]*',
            r'wget\s+[^\n;&&]*',
            r'git\s+(?:clone|pull|checkout)[^\n;&&]*',
            r'make\s+[^\n;&&]*',
            r'./configure[^\n;&&]*'
        ]
        
        for pattern in command_patterns:
            operations["commands"].extend(re.findall(pattern, content))
        
        # Network operations
        network_patterns = [
            r'curl\s+[^\s]+\s+([^\s\n;&&]+)',
            r'wget\s+([^\s\n;&&]+)',
            r'nc\s+[^\s]+\s+([0-9]+)',
            r'ping\s+([^\s\n;&&]+)'
        ]
        
        for pattern in network_patterns:
            operations["network"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Clean and deduplicate
        for key in operations:
            operations[key] = list(dict.fromkeys([
                op.strip().replace('"', '').replace("'", '') 
                for op in operations[key] if op.strip()
            ]))[:10]  # Limit results
        
        return operations

def create_correlation_id() -> str:
    """Generate correlation ID for request tracking."""
    return str(uuid.uuid4())[:8]