"""
Minimal utility functions for Salt Analysis Agent.
Simple correlation ID generation only.
"""
import uuid

def create_correlation_id() -> str:
    """Generate correlation ID for request tracking."""
    return str(uuid.uuid4())[:8]