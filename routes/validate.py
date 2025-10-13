#!/usr/bin/env python3

import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

# Import from our agent module
from agents.validate.validate import (
    PlaybookValidationRequest,
    PlaybookValidationResponse,
    create_ansible_lint_agent,
    process_playbook_validation
)

# Import ConfigLoader for proper configuration
from config.config import ConfigLoader

# Set up logging
logger = logging.getLogger(__name__)

# Create the router
router = APIRouter(tags=["ansible-validation"])

# Initialize ConfigLoader and agent once when the module loads
try:
    config_loader = ConfigLoader("config.yaml")
    ansible_agent = create_ansible_lint_agent(config_loader)
    logger.info("Ansible validation agent initialized successfully with ConfigLoader")
except Exception as e:
    logger.error(f"Failed to initialize Ansible validation agent: {e}")
    ansible_agent = None

@router.get("/validate/health")
def ansible_validation_health_check():
    """Health check endpoint for Ansible validation service."""
    if ansible_agent is None:
        raise HTTPException(status_code=503, detail="Ansible validation agent not available")
    
    return {
        "status": "healthy",
        "service": "ansible-validation",
        "agent_ready": ansible_agent is not None
    }

@router.post("/validate/playbook/stream")
async def validate_playbook_stream(request: PlaybookValidationRequest, http_request: Request):
    """Validate an Ansible playbook with streaming response."""
    
    # Log the incoming validation request
    logger.info("=== VALIDATION REQUEST RECEIVED (STREAM) ===")
    logger.info(f"Request method: {http_request.method}")
    logger.info(f"Request URL: {http_request.url}")
    logger.info(f"User-Agent: {http_request.headers.get('user-agent', 'Not provided')}")
    logger.info(f"Content-Type: {http_request.headers.get('content-type', 'Not provided')}")
    logger.info(f"Playbook content length: {len(request.playbook_content)} characters")
    logger.info(f"Playbook content preview (first 500 chars): {request.playbook_content[:500]}")
    if len(request.playbook_content) > 500:
        logger.info(f"Playbook content preview (last 500 chars): {request.playbook_content[-500:]}")
    logger.info("=== END VALIDATION REQUEST LOG ===")
    
    if ansible_agent is None:
        raise HTTPException(status_code=503, detail="Ansible validation agent not available")
    
    async def event_generator():
        try:
            # Start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting playbook validation...'})}\n\n"
            
            # Progress event
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Running ansible-lint validation...'})}\n\n"
            
            # Run agent validation in executor to avoid blocking
            validation_result = await asyncio.get_event_loop().run_in_executor(
                None, 
                process_playbook_validation,
                ansible_agent,
                request.playbook_content
            )
            
            # Send results
            result_data = {
                'type': 'result',
                'data': validation_result
            }
            
            yield f"data: {json.dumps(result_data)}\n\n"
            
            # End event
            yield f"data: {json.dumps({'type': 'end', 'message': 'Validation complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Validation failed: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@router.post("/validate/playbook")
async def validate_playbook_sync(request: PlaybookValidationRequest, http_request: Request) -> PlaybookValidationResponse:
    """Validate an Ansible playbook with synchronous response."""
    
    # Log the incoming validation request
    logger.info("=== VALIDATION REQUEST RECEIVED (SYNC) ===")
    logger.info(f"Request method: {http_request.method}")
    logger.info(f"Request URL: {http_request.url}")
    logger.info(f"User-Agent: {http_request.headers.get('user-agent', 'Not provided')}")
    logger.info(f"Content-Type: {http_request.headers.get('content-type', 'Not provided')}")
    logger.info(f"Playbook content length: {len(request.playbook_content)} characters")
    logger.info(f"Playbook content preview (first 500 chars): {request.playbook_content[:500]}")
    if len(request.playbook_content) > 500:
        logger.info(f"Playbook content preview (last 500 chars): {request.playbook_content[-500:]}")
    logger.info("=== END VALIDATION REQUEST LOG ===")
    
    if ansible_agent is None:
        raise HTTPException(status_code=503, detail="Ansible validation agent not available")
    
    try:
        # Run agent validation in executor to avoid blocking
        validation_result = await asyncio.get_event_loop().run_in_executor(
            None, 
            process_playbook_validation,
            ansible_agent,
            request.playbook_content
        )
        
        return PlaybookValidationResponse(**validation_result)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")