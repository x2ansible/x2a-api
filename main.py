"""
FastAPI application entry point for Chef Analysis Agent.
Production-grade setup with proper logging, error handling, and monitoring.
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from agents.chef_analysis.routes import router as chef_router
from shared.exceptions import ChefAnalysisBaseException
from config.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

# Global configuration
config_loader = ConfigLoader()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown operations.
    """
    # Startup
    logger.info("Starting Chef Analysis Agent API")
    logger.info(f"Active profile: {config_loader.get_profile()}")
    logger.info(f"LlamaStack URL: {config_loader.get_llamastack_base_url()}")
    logger.info(f"Model: {config_loader.get_llamastack_model()}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Chef Analysis Agent API")


# Create FastAPI application
app = FastAPI(
    title="Chef Analysis Agent API",
    description="Production-grade Chef cookbook analysis using agentic AI patterns",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all incoming requests for monitoring.
    Adds correlation tracking and performance metrics.
    """
    import time
    import uuid
    
    # Generate correlation ID
    correlation_id = str(uuid.uuid4())[:8]
    
    # Add correlation ID to request state
    request.state.correlation_id = correlation_id
    
    # Log request start
    start_time = time.time()
    logger.info(
        f"Request start [{correlation_id}]: {request.method} {request.url.path}"
    )
    
    # Process request
    try:
        response = await call_next(request)
        
        # Log request completion
        process_time = time.time() - start_time
        logger.info(
            f"Request complete [{correlation_id}]: "
            f"{response.status_code} in {process_time:.3f}s"
        )
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
        
    except Exception as e:
        # Log request error
        process_time = time.time() - start_time
        logger.error(
            f"Request error [{correlation_id}]: {str(e)} after {process_time:.3f}s"
        )
        raise


@app.exception_handler(ChefAnalysisBaseException)
async def chef_analysis_exception_handler(request: Request, exc: ChefAnalysisBaseException):
    """
    Handle Chef Analysis specific exceptions.
    Returns structured error responses with proper HTTP status codes.
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.error(
        f"Chef analysis exception [{correlation_id}]: {exc.error_code.value} - {exc.message}"
    )
    
    error_response = exc.to_dict()
    error_response["correlation_id"] = correlation_id
    
    return JSONResponse(
        status_code=exc.http_status,
        content=error_response
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle standard HTTP exceptions.
    Adds correlation tracking to error responses.
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        f"HTTP exception [{correlation_id}]: {exc.status_code} - {exc.detail}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "correlation_id": correlation_id
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions.
    Prevents sensitive information from leaking in error responses.
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.error(
        f"Unexpected exception [{correlation_id}]: {type(exc).__name__} - {str(exc)}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id
            }
        }
    )


# Include routers
app.include_router(chef_router)


@app.get("/", summary="API Root", description="API information and health status")
async def root() -> Dict[str, Any]:
    """
    API root endpoint.
    Provides basic API information and health status.
    """
    return {
        "service": "Chef Analysis Agent API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "cookbook_analysis": "/chef/analyze",
            "streaming_analysis": "/chef/analyze/stream", 
            "health_check": "/chef/health",
            "agent_config": "/chef/config"
        }
    }


@app.get("/health", summary="System Health Check")
async def system_health() -> Dict[str, Any]:
    """
    System-wide health check.
    Verifies overall application health and dependencies.
    """
    try:
        # Basic system health checks
        health_status = {
            "status": "healthy",
            "service": "chef_analysis_api",
            "version": "1.0.0",
            "timestamp": "2025-06-02T12:00:00Z",
            "components": {
                "api": "healthy",
                "configuration": "healthy" if config_loader else "unhealthy",
                "llamastack_config": "configured" if config_loader.get_llamastack_base_url() else "missing"
            }
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"System health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2025-06-02T12:00:00Z"
            }
        )


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )