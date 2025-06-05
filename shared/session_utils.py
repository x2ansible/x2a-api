# shared/session_utils.py

import httpx
import logging
from typing import Optional

logger = logging.getLogger("session_utils")

async def fetch_input_code_from_session(
    base_url: str,
    agent_id: str,
    session_id: str,
    message_index: int = 0
) -> Optional[str]:
    """
    Fetch the original user input code from a previous agent session.
    Args:
        base_url: LlamaStack API base URL (no trailing /)
        agent_id: The agent name or agent UUID as registered with LlamaStack
        session_id: The session UUID
        message_index: Which user message to extract (usually 0)
    Returns:
        The code/input content (str) or None if not found.
    """
    url = f"{base_url}/v1/agents/{agent_id}/session/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            logger.info(f"Fetching session data from: {url}")
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            logger.debug(f"Session response structure: {list(data.keys())}")
            
            # Extract user input from the LlamaStack session structure
            user_input = _extract_user_input_from_llamastack_session(data, message_index)
            
            if user_input:
                logger.info(f"Successfully extracted input code ({len(user_input)} characters)")
                return user_input
            else:
                logger.warning("No user input code found in session response")
                return None
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching session {session_id}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching input code from session: {e}")
    return None

def _extract_user_input_from_llamastack_session(data: dict, message_index: int = 0) -> Optional[str]:
    """
    Extract user input from LlamaStack session response structure.
    
    Expected structure:
    {
        "session_id": "...",
        "turns": [
            {
                "input_messages": [
                    {
                        "role": "user",
                        "content": "USER_INPUT_HERE",
                        "context": null
                    }
                ],
                ...
            }
        ],
        ...
    }
    """
    
    # Check if we have the expected structure
    if not isinstance(data, dict):
        logger.error("Session data is not a dictionary")
        return None
    
    if "turns" not in data:
        logger.error("No 'turns' found in session data")
        return None
    
    turns = data["turns"]
    if not isinstance(turns, list) or not turns:
        logger.error("No turns found in session data")
        return None
    
    # Get the first turn (or specified turn index)
    turn = turns[0]  # Usually we want the first turn
    if not isinstance(turn, dict):
        logger.error("Turn is not a dictionary")
        return None
    
    # Look for input_messages in the turn
    if "input_messages" not in turn:
        logger.error("No 'input_messages' found in turn")
        return None
    
    input_messages = turn["input_messages"]
    if not isinstance(input_messages, list) or not input_messages:
        logger.error("No input messages found in turn")
        return None
    
    # Find user message at the specified index
    if len(input_messages) <= message_index:
        logger.error(f"Not enough input messages (requested index {message_index}, but only {len(input_messages)} available)")
        return None
    
    message = input_messages[message_index]
    if not isinstance(message, dict):
        logger.error("Input message is not a dictionary")
        return None
    
    # Verify it's a user message and extract content
    if message.get("role") != "user":
        logger.warning(f"Message role is '{message.get('role')}', expected 'user'")
    
    content = message.get("content")
    if not content:
        logger.error("No content found in user message")
        return None
    
    logger.debug(f"Successfully extracted user input: {content[:100]}...")
    return content