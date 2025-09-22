"""
Universal Extraction Agent

A single intelligent agent that can detect platforms and extract facts from any
infrastructure code type (Chef, Puppet, Terraform, Ansible, BladeLogic, Salt).

This follows the pure agentic pattern where the LLM decides which tools to use
based on the input, rather than hardcoded routing.
"""

from .agent import create_universal_extraction_agent
from .nodes import universal_extraction_node

__all__ = ["create_universal_extraction_agent", "universal_extraction_node"]
