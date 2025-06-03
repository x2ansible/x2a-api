"""
Custom exception classes for Chef Analysis Agent.
Provides structured error handling with HTTP status mapping.
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(Enum):
    """Error codes for structured error handling."""
    INVALID_INPUT = "INVALID_INPUT"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    JSON_PARSE_ERROR = "JSON_PARSE_ERROR"
    COOKBOOK_ANALYSIS_ERROR = "COOKBOOK_ANALYSIS_ERROR"


class ChefAnalysisBaseException(Exception):
    """Base exception for Chef Analysis Agent errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": self.details,
                "type": self.__class__.__name__
            }
        }


class InvalidInputError(ChefAnalysisBaseException):
    """Raised when cookbook input is invalid or malformed."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.INVALID_INPUT,
            http_status=400,
            details=details
        )


class LLMServiceError(ChefAnalysisBaseException):
    """Raised when LlamaStack service communication fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.LLM_SERVICE_ERROR,
            http_status=502,
            details=details
        )


class TimeoutError(ChefAnalysisBaseException):
    """Raised when LLM request times out."""
    
    def __init__(self, message: str, timeout_seconds: float, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            http_status=408,
            details=details
        )


class ConfigurationError(ChefAnalysisBaseException):
    """Raised when agent configuration is invalid."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            http_status=500,
            details=details
        )


class JSONParseError(ChefAnalysisBaseException):
    """Raised when LLM response JSON parsing fails."""
    
    def __init__(self, message: str, raw_response: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["raw_response_preview"] = raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
        super().__init__(
            message=message,
            error_code=ErrorCode.JSON_PARSE_ERROR,
            http_status=502,
            details=details
        )


class CookbookAnalysisError(ChefAnalysisBaseException):
    """Raised when cookbook analysis fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.COOKBOOK_ANALYSIS_ERROR,
            http_status=422,
            details=details
        )