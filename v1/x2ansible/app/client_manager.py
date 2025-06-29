# app/client_manager.py - Production-grade LlamaStack client management
import logging
import time
from typing import Optional, Dict, Any, List
from llama_stack_client import LlamaStackClient
from llama_stack_client.types import Model
import httpx

logger = logging.getLogger(__name__)

class LlamaStackConnectionError(Exception):
    """Custom exception for LlamaStack connection issues"""
    pass

class LlamaStackClientManager:
    """
    Production-grade LlamaStack client manager with connection validation,
    health checking, and error handling
    """
    
    def __init__(self, base_url: str, timeout: int = 180):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.timeout = timeout
        self.client: Optional[LlamaStackClient] = None
        self._last_health_check: Optional[float] = None
        self._health_check_interval = 300  # 5 minutes
        self._available_models: List[str] = []
        
        # Initialize and validate connection
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize LlamaStack client with connection validation"""
        try:
            logger.info(f"🔗 Initializing LlamaStack client...")
            logger.info(f"   Base URL: {self.base_url}")
            logger.info(f"   Timeout: {self.timeout}s")
            
            # Create client
            self.client = LlamaStackClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
            
            # Validate connection
            self._validate_connection()
            
            # Load available models
            self._load_available_models()
            
            logger.info(" LlamaStack client initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize LlamaStack client: {str(e)}"
            logger.error(f" {error_msg}")
            raise LlamaStackConnectionError(error_msg) from e

    def _validate_connection(self) -> None:
        """Validate connection to LlamaStack server"""
        try:
            logger.info("🔍 Validating LlamaStack connection...")
            
            # Test basic connectivity with a simple API call
            # Try to list models as a connectivity test
            response = self.client.models.list()
            
            # Check if we got a valid response
            if response is None:
                raise LlamaStackConnectionError("Received null response from LlamaStack server")
            
            logger.info(" LlamaStack connection validated successfully")
            self._last_health_check = time.time()
            
        except httpx.ConnectError as e:
            raise LlamaStackConnectionError(
                f"Cannot connect to LlamaStack server at {self.base_url}. "
                f"Please check if the server is running and the URL is correct. "
                f"Error: {str(e)}"
            ) from e
        
        except httpx.TimeoutException as e:
            raise LlamaStackConnectionError(
                f"Connection to LlamaStack server timed out after {self.timeout}s. "
                f"Server may be overloaded or URL may be incorrect. "
                f"Error: {str(e)}"
            ) from e
        
        except httpx.HTTPStatusError as e:
            raise LlamaStackConnectionError(
                f"LlamaStack server returned HTTP error {e.response.status_code}. "
                f"Please check server status and authentication. "
                f"Error: {str(e)}"
            ) from e
        
        except Exception as e:
            raise LlamaStackConnectionError(
                f"Unexpected error validating LlamaStack connection: {str(e)}"
            ) from e

    def _load_available_models(self) -> None:
        """Load and cache available models from LlamaStack"""
        try:
            logger.info("📋 Loading available models...")
            
            models_response = self.client.models.list()
            
            if not models_response:
                logger.warning("No models returned from LlamaStack server")
                self._available_models = []
                return
            
            # Extract model identifiers
            self._available_models = []
            model_count = 0
            
            for model in models_response:
                if hasattr(model, 'identifier'):
                    self._available_models.append(model.identifier)
                    model_count += 1
                elif hasattr(model, 'id'):
                    self._available_models.append(model.id)
                    model_count += 1
                elif isinstance(model, str):
                    self._available_models.append(model)
                    model_count += 1
                else:
                    logger.debug(f"Unknown model format: {model}")
            
            logger.info(f" Loaded {model_count} available models:")
            for model in self._available_models[:5]:  # Log first 5 models
                logger.info(f"   - {model}")
            if len(self._available_models) > 5:
                logger.info(f"   ... and {len(self._available_models) - 5} more")
                
        except Exception as e:
            logger.warning(f"Could not load available models: {str(e)}")
            self._available_models = []

    def get_client(self) -> LlamaStackClient:
        """Get the LlamaStack client instance"""
        if not self.client:
            raise LlamaStackConnectionError("LlamaStack client is not initialized")
        
        # Perform periodic health check
        self._periodic_health_check()
        
        return self.client

    def _periodic_health_check(self) -> None:
        """Perform periodic health check if enough time has passed"""
        current_time = time.time()
        
        if (self._last_health_check is None or 
            current_time - self._last_health_check > self._health_check_interval):
            
            try:
                logger.debug("🔍 Performing periodic health check...")
                self._validate_connection()
                logger.debug(" Periodic health check passed")
            except Exception as e:
                logger.error(f" Periodic health check failed: {str(e)}")
                # Don't raise exception for periodic checks, just log the error

    def validate_model(self, model_name: str) -> bool:
        """
        Validate if a model is available on the LlamaStack server
        
        Args:
            model_name: Name of the model to validate
            
        Returns:
            True if model is available, False otherwise
        """
        if not model_name:
            return False
        
        # If we have cached models, check against cache
        if self._available_models:
            is_available = model_name in self._available_models
            if not is_available:
                logger.warning(
                    f"Model '{model_name}' not found in available models. "
                    f"Available models: {self._available_models[:3]}..."
                )
            return is_available
        
        # If no cached models, try to validate by making a test call
        try:
            # Refresh model list
            self._load_available_models()
            return model_name in self._available_models
        except Exception as e:
            logger.warning(f"Could not validate model '{model_name}': {str(e)}")
            return True  # Assume it's valid if we can't check

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        if not self._available_models:
            try:
                self._load_available_models()
            except Exception as e:
                logger.warning(f"Could not refresh model list: {str(e)}")
        
        return self._available_models.copy()

    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check and return status
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            "status": "unknown",
            "base_url": self.base_url,
            "timeout": self.timeout,
            "client_initialized": self.client is not None,
            "last_health_check": self._last_health_check,
            "available_models_count": len(self._available_models),
            "errors": []
        }
        
        try:
            # Test connection
            self._validate_connection()
            health_status["status"] = "healthy"
            health_status["connection"] = "ok"
            
        except LlamaStackConnectionError as e:
            health_status["status"] = "unhealthy"
            health_status["connection"] = "failed"
            health_status["errors"].append(f"Connection error: {str(e)}")
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["connection"] = "error"
            health_status["errors"].append(f"Unexpected error: {str(e)}")
        
        # Test model listing
        try:
            if health_status["status"] == "healthy":
                self._load_available_models()
                health_status["models"] = "ok"
                health_status["available_models_count"] = len(self._available_models)
        except Exception as e:
            health_status["models"] = "failed"
            health_status["errors"].append(f"Model listing error: {str(e)}")
        
        return health_status

    def reconnect(self) -> None:
        """Reconnect to LlamaStack server"""
        logger.info("🔄 Reconnecting to LlamaStack server...")
        self.client = None
        self._last_health_check = None
        self._available_models = []
        self._initialize_client()

    def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed connection information"""
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "client_initialized": self.client is not None,
            "last_health_check": self._last_health_check,
            "health_check_interval": self._health_check_interval,
            "available_models": self._available_models.copy(),
            "connection_status": "connected" if self.client else "disconnected"
        }

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup if needed"""
        # LlamaStackClient doesn't need explicit cleanup
        # but we can reset our state
        self._last_health_check = None