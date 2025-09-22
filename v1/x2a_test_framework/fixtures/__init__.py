"""
x2a Test Framework Fixtures

Real-system test fixtures and infrastructure code samples for x2a agent testing.
Provides comprehensive test codes for production validation.

Key Components:
- Sample infrastructure codes for all supported platforms (Chef, Terraform, Puppet, etc.)
- Real workflow test scenarios for integration testing
- Platform-specific test codes with varying complexity levels

Focus: Real-system testing for production validation, not mocked components.
"""

from .sample_codes import PlatformTestCodes, WorkflowTestData, X2ATestCodes

__all__ = [
    # Real Infrastructure Test Codes
    "PlatformTestCodes",
    "WorkflowTestData", 
    "X2ATestCodes"
]
