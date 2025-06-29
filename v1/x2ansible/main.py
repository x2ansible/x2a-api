# main.py - Production-grade FastAPI application with comprehensive lifecycle management

import logging
import sys
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

# Import our production-grade components
from config.config import ConfigLoader, ConfigValidationError
from app.client_manager import LlamaStackClientManager, LlamaStackConnectionError
from app.agent_registry import UnifiedAgentRegistry, AgentRegistryError
from utils.logging_utils import setup_enhanced_logging
from routes.files import router as files_router

# Configure logging
def setup_logging(config_loader: ConfigLoader) -> None:
    """Setup production-grade logging configuration"""
    try:
        log_config = config_loader.get_logging_config()
        
        logging.basicConfig(
            level=getattr(logging, log_config.get("level", "INFO").upper()),
            format=log_config.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
            handlers=[
                logging.StreamHandler(sys.stdout),
                # Add file handler if needed in production
                # logging.FileHandler("app.log")
            ]
        )
        
        # Set specific logger levels
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
        logger = logging.getLogger(__name__)
        logger.info(" Logging configured successfully")
        
    except Exception as e:
        print(f" Failed to configure logging: {e}")
        # Fallback to basic logging
        logging.basicConfig(level=logging.INFO)

# Global variables for application state
config_loader: ConfigLoader = None
client_manager: LlamaStackClientManager = None
agent_registry: UnifiedAgentRegistry = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Production-grade application lifecycle management with proper initialization,
    health checking, and cleanup
    """
    global config_loader, client_manager, agent_registry
    
    startup_start_time = datetime.utcnow()
    logger = logging.getLogger(__name__)
    
    try:
        # ==================== STARTUP PHASE ====================
        logger.info("🚀 Starting FastAPI application...")
        logger.info("=" * 60)
        
        # Step 1: Load and validate configuration
        logger.info("📋 Step 1: Loading configuration...")
        try:
            config_loader = ConfigLoader("config/config.yaml")
            setup_logging(config_loader)  # Reconfigure logging with loaded config
            
            # Initialize enhanced logging for agent execution
            setup_enhanced_logging(enable_step_printing=True, enable_rich=True)
            
            logger.info(" Configuration loaded and validated successfully")
        except (ConfigValidationError, FileNotFoundError, Exception) as e:
            logger.error(f" Configuration loading failed: {str(e)}")
            raise RuntimeError(f"Cannot start application: Configuration error - {str(e)}")
        
        # Step 2: Initialize LlamaStack client manager
        logger.info("🔗 Step 2: Initializing LlamaStack client...")
        try:
            client_manager = LlamaStackClientManager(
                base_url=config_loader.get_llamastack_base_url(),
                timeout=config_loader.get_llamastack_timeout()
            )
            logger.info(" LlamaStack client initialized and validated")
        except LlamaStackConnectionError as e:
            logger.error(f" LlamaStack connection failed: {str(e)}")
            raise RuntimeError(f"Cannot start application: LlamaStack connection error - {str(e)}")
        except Exception as e:
            logger.error(f" Unexpected error initializing client: {str(e)}")
            raise RuntimeError(f"Cannot start application: Client initialization error - {str(e)}")
        
        # Step 3: Initialize agent registry
        logger.info("🎯 Step 3: Initializing agent registry...")
        try:
            agent_registry = UnifiedAgentRegistry(client_manager, config_loader)
            logger.info(" Agent registry initialized successfully")
        except AgentRegistryError as e:
            logger.error(f" Agent registry initialization failed: {str(e)}")
            raise RuntimeError(f"Cannot start application: Agent registry error - {str(e)}")
        except Exception as e:
            logger.error(f" Unexpected error initializing registry: {str(e)}")
            raise RuntimeError(f"Cannot start application: Registry initialization error - {str(e)}")
        
        # Step 4: Preload all agents for faster API response times
        logger.info("⚡ Step 4: Preloading all agents...")
        try:
            logger.info("🔄 Creating all agents at startup for optimal performance...")
            preload_results = agent_registry.preload_all_agents()
            
            if preload_results['successful'] > 0:
                logger.info(f" Successfully preloaded {preload_results['successful']} agents")
            if preload_results['failed'] > 0:
                logger.error(f" Failed to preload {preload_results['failed']} agents")
                for agent_name, error in preload_results['errors'].items():
                    logger.error(f"   - {agent_name}: {error}")
                
                # If too many agents failed, consider it a critical error
                if preload_results['failed'] >= preload_results['total_agents'] / 2:
                    raise RuntimeError(f"More than half of agents failed to preload ({preload_results['failed']}/{preload_results['total_agents']})")
            
            logger.info(f"🎯 Agent preloading completed: {preload_results['successful']}/{preload_results['total_agents']} agents ready")
            
        except Exception as e:
            logger.error(f" Critical error during agent preloading: {str(e)}")
            raise RuntimeError(f"Agent preloading failed: {str(e)}")
        
        # Step 5: Store components in app state
        app.state.config_loader = config_loader
        app.state.client_manager = client_manager
        app.state.agent_registry = agent_registry
        
        # Calculate startup time
        startup_time = (datetime.utcnow() - startup_start_time).total_seconds()
        
        # Step 6: Final health check
        logger.info("🔍 Step 5: Performing final health check...")
        try:
            registry_status = agent_registry.get_registry_status()
            client_health = client_manager.health_check()
            
            if not registry_status.get("registry_healthy") or client_health.get("status") != "healthy":
                logger.error(" Health check failed during startup")
                raise RuntimeError("Application health check failed")
            
            logger.info(" Final health check passed")
        except Exception as e:
            logger.error(f" Health check failed: {str(e)}")
            raise RuntimeError(f"Application health check failed: {str(e)}")
        
        # Startup complete
        logger.info("=" * 60)
        logger.info(f"🎉 Application startup completed successfully in {startup_time:.2f}s")
        logger.info(f"📊 Registry Status:")
        logger.info(f"   - Total agents configured: {registry_status['total_agents_configured']}")
        logger.info(f"   - Total agents created: {registry_status['total_agents_created']}")
        logger.info(f"   - LlamaStack URL: {config_loader.get_llamastack_base_url()}")
        logger.info(f"   - Available models: {len(client_manager.get_available_models())}")
        logger.info("🚀 Ready to serve requests!")
        logger.info("=" * 60)
        
        # Application is now ready
        yield
        
        # ==================== SHUTDOWN PHASE ====================
        logger.info("🛑 Starting graceful shutdown...")
        
        try:
            # Perform any cleanup if needed
            # For now, our components don't need explicit cleanup
            # but this is where you'd add it
            
            logger.info(" Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f" Error during shutdown: {str(e)}")
        
    except Exception as e:
        logger.error(f" Critical startup error: {str(e)}")
        # Log the error and re-raise to prevent startup
        raise

# Initialize FastAPI application
def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Create temp config loader to get API configuration
    try:
        temp_config = ConfigLoader("config/config.yaml")
        api_config = temp_config.get_api_config()
    except Exception:
        # Fallback configuration if config loading fails
        api_config = {
            "title": "Unified Agent API",
            "version": "2.0.0", 
            "description": "Production-grade multi-agent system"
        }
    
    # Create FastAPI app with lifespan
    app = FastAPI(
        title=api_config.get("title", "Unified Agent API"),
        version=api_config.get("version", "2.0.0"),
        description=api_config.get("description", "Production-grade multi-agent system"),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    return app

# Create the FastAPI application
app = create_application()

# Add CORS middleware
@app.on_event("startup")
async def configure_cors():
    """Configure CORS after config is loaded"""
    if hasattr(app.state, 'config_loader'):
        cors_config = app.state.config_loader.get_cors_config()
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config.get("allow_origins", ["*"]),
            allow_credentials=cors_config.get("allow_credentials", True),
            allow_methods=cors_config.get("allow_methods", ["*"]),
            allow_headers=cors_config.get("allow_headers", ["*"]),
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for production error handling"""
    logger = logging.getLogger(__name__)
    
    # Log the error
    logger.error(f" Unhandled exception in {request.method} {request.url}: {str(exc)}", exc_info=True)
    
    # Return appropriate error response
    if isinstance(exc, (ConfigValidationError, LlamaStackConnectionError, AgentRegistryError)):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "detail": str(exc),
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        )

# Dependency to get agent registry
def get_agent_registry(request: Request) -> UnifiedAgentRegistry:
    """Dependency to get agent registry with error handling"""
    if not hasattr(request.app.state, 'agent_registry') or not request.app.state.agent_registry:
        raise HTTPException(
            status_code=503, 
            detail="Agent registry not available - application may still be starting up"
        )
    return request.app.state.agent_registry

# Dependency to get client manager
def get_client_manager(request: Request) -> LlamaStackClientManager:
    """Dependency to get client manager with error handling"""
    if not hasattr(request.app.state, 'client_manager') or not request.app.state.client_manager:
        raise HTTPException(
            status_code=503,
            detail="Client manager not available - application may still be starting up"
        )
    return request.app.state.client_manager

# Dependency to get config loader
def get_config_loader(request: Request) -> ConfigLoader:
    """Dependency to get config loader with error handling"""
    if not hasattr(request.app.state, 'config_loader') or not request.app.state.config_loader:
        raise HTTPException(
            status_code=503,
            detail="Configuration not available - application may still be starting up"
        )
    return request.app.state.config_loader

# ==================== CORE API ENDPOINTS ====================

@app.get("/")
async def root(registry: UnifiedAgentRegistry = Depends(get_agent_registry)):
    """Root endpoint with application status"""
    try:
        status = registry.get_registry_status()
        return {
            "message": "🎉 Unified Agent API - Production Ready",
            "status": "running",
            "version": app.version,
            "timestamp": datetime.utcnow().isoformat(),
            "registry_status": status
        }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error in root endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving application status")

@app.get("/health")
async def health_check(
    registry: UnifiedAgentRegistry = Depends(get_agent_registry),
    client_manager: LlamaStackClientManager = Depends(get_client_manager)
):
    """Comprehensive health check endpoint"""
    try:
        registry_status = registry.get_registry_status()
        client_health = client_manager.health_check()
        
        is_healthy = (
            registry_status.get("registry_healthy", False) and
            client_health.get("status") == "healthy"
        )
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "registry": registry_status,
            "client": client_health,
            "application": {
                "version": app.version,
                "title": app.title
            }
        }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/agents")
async def list_agents(registry: UnifiedAgentRegistry = Depends(get_agent_registry)):
    """List all available agents with their status"""
    try:
        agents = registry.list_available_agents()
        return {
            "agents": agents,
            "total_agents": len(agents),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error listing agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving agent list")

@app.get("/agents/{agent_name}/status")
async def get_agent_status(
    agent_name: str,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Get detailed status for a specific agent"""
    try:
        status = registry.get_agent_status(agent_name)
        return status
    except AgentRegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error getting agent status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving agent status")

@app.get("/config/summary")
async def get_config_summary(config_loader: ConfigLoader = Depends(get_config_loader)):
    """Get configuration summary for debugging"""
    try:
        summary = config_loader.get_config_summary()
        return summary
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error getting config summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving configuration summary")

@app.post("/admin/reload-config")
async def reload_configuration(registry: UnifiedAgentRegistry = Depends(get_agent_registry)):
    """Reload configuration from file (admin endpoint)"""
    try:
        result = registry.reload_configuration()
        return result
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error reloading configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Error reloading configuration")

@app.post("/admin/preload-agents")
async def preload_agents(registry: UnifiedAgentRegistry = Depends(get_agent_registry)):
    """Preload all agents (admin endpoint)"""
    try:
        result = registry.preload_all_agents()
        return result
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f" Error preloading agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Error preloading agents")

# ==================== READY FOR ROUTE INTEGRATION ====================
# Import and include analysis routes
try:
    from routes.analysis import router as analysis_router
    app.include_router(analysis_router)
    print(" Analysis routes integrated successfully")
except ImportError as e:
    print(f"⚠️  Analysis routes not found: {e}")
    print("ℹ️  Create routes/analysis.py to enable analysis endpoints")

if __name__ == "__main__":
    import uvicorn
    
    # Production-grade server configuration
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to False in production
        access_log=True,
        log_level="info"
    )