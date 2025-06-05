import logging
import re
from typing import List, Dict, Any, Optional
from llama_stack_client import LlamaStackClient

logger = logging.getLogger("LlamaStackSessionManager")

class LlamaStackSessionManager:
    """
    Reusable session manager for LlamaStack agents.
    Handles finding agents, listing sessions, and extracting content from sessions.
    Used by Context Agent, Code Generation Agent, and any other agents that need session data.
    """
    
    def __init__(self, client: LlamaStackClient):
        self.client = client
    
    def find_agent_by_name(self, agent_name: str) -> Optional[str]:
        """Find agent ID by agent name using LlamaStack API
        
        Args:
            agent_name: Name of the agent to find (e.g., "chef_analysis_agent")
            
        Returns:
            str: Agent ID if found, None otherwise
        """
        try:
            # GET /v1/agents to list all agents
            response = self.client._client.get("agents")
            
            if response.status_code != 200:
                logger.error(f"Failed to list agents: HTTP {response.status_code}")
                return None
                
            data = response.json()
            agents = data.get('data', [])
            
            # Search for agent by name
            for agent in agents:
                agent_config = agent.get('agent_config', {})
                if agent_config.get('name') == agent_name:
                    agent_id = agent.get('agent_id')
                    logger.info(f"📋 Found agent '{agent_name}': {agent_id}")
                    return agent_id
            
            logger.warning(f"Agent '{agent_name}' not found in {len(agents)} agents")
            return None
            
        except Exception as e:
            logger.error(f"Error finding agent by name '{agent_name}': {e}")
            return None

    def get_agent_sessions(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions for a specific agent ID using LlamaStack API
        
        Args:
            agent_id: ID of the agent
            limit: Maximum number of sessions to retrieve
            
        Returns:
            List of session dictionaries
        """
        try:
            # GET /v1/agents/{agent_id}/sessions
            response = self.client._client.get(f"agents/{agent_id}/sessions", params={"limit": limit})
            
            if response.status_code == 200:
                data = response.json()
                sessions = data.get('data', [])
                logger.info(f"📋 Found {len(sessions)} sessions for agent {agent_id}")
                return sessions
            else:
                logger.error(f"Failed to get sessions: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting sessions for agent {agent_id}: {e}")
            return []

    def get_session_details(self, agent_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session data including turns and messages
        
        Args:
            agent_id: ID of the agent
            session_id: Session ID to get details for
            
        Returns:
            Session data dictionary or None if not found
        """
        try:
            # GET /v1/agents/{agent_id}/session/{session_id}
            response = self.client._client.get(f"agents/{agent_id}/session/{session_id}")
            
            if response.status_code != 200:
                logger.error(f"Failed to get session {session_id}: HTTP {response.status_code}")
                return None
                
            session_data = response.json()
            logger.debug(f"📋 Retrieved session {session_id} with {len(session_data.get('turns', []))} turns")
            return session_data
            
        except Exception as e:
            logger.error(f"Error getting session details {session_id}: {e}")
            return None

    def extract_input_code_from_session(self, agent_id: str, session_id: str, 
                                      patterns: Optional[List[str]] = None) -> Optional[str]:
        """Extract input code from a session using configurable patterns
        
        Args:
            agent_id: ID of the agent
            session_id: Session ID to extract from
            patterns: Optional list of patterns to look for. If None, uses default chef patterns.
            
        Returns:
            Extracted code string or None if not found
        """
        session_data = self.get_session_details(agent_id, session_id)
        if not session_data:
            return None
        
        turns = session_data.get('turns', [])
        
        # Look through turns for code content
        for turn in turns:
            input_messages = turn.get('input_messages', [])
            for message in input_messages:
                code = self._extract_code_from_message(message, patterns)
                if code:
                    return code
        
        return None

    def find_sessions_by_correlation_id(self, agent_id: str, correlation_id: str) -> List[Dict[str, Any]]:
        """Find sessions that match a correlation ID pattern
        
        Args:
            agent_id: ID of the agent
            correlation_id: Correlation ID to search for
            
        Returns:
            List of matching sessions
        """
        sessions = self.get_agent_sessions(agent_id)
        
        target_session_patterns = [
            f"chef_analysis_{correlation_id}",
            f"simple_{correlation_id}",
            f"code_gen_{correlation_id}",
            correlation_id  # Also check for direct correlation_id match
        ]
        
        matching_sessions = []
        for session_info in sessions:
            session_name = session_info.get('session_name', '')
            if any(pattern in session_name for pattern in target_session_patterns):
                matching_sessions.append(session_info)
        
        return matching_sessions

    def get_recent_sessions_with_code(self, agent_id: str, 
                                    session_patterns: Optional[List[str]] = None,
                                    code_patterns: Optional[List[str]] = None,
                                    max_sessions: int = 10) -> List[Dict[str, Any]]:
        """Get recent sessions that contain code matching specified patterns
        
        Args:
            agent_id: ID of the agent
            session_patterns: Session name patterns to look for
            code_patterns: Code content patterns to look for
            max_sessions: Maximum number of sessions to check
            
        Returns:
            List of sessions with extracted code
        """
        sessions = self.get_agent_sessions(agent_id)
        
        # Default patterns for chef analysis
        if session_patterns is None:
            session_patterns = ['chef_analysis_', 'simple_', 'code_gen_']
        
        # Sort sessions by started_at time (most recent first)
        sorted_sessions = sorted(sessions, 
                               key=lambda x: x.get('started_at', ''), 
                               reverse=True)
        
        sessions_with_code = []
        
        # Check recent sessions for code
        for session_info in sorted_sessions[:max_sessions]:
            session_id = session_info.get('session_id')
            session_name = session_info.get('session_name', '')
            
            # Check if session name matches patterns
            if any(pattern in session_name for pattern in session_patterns):
                code = self.extract_input_code_from_session(agent_id, session_id, code_patterns)
                if code:
                    session_info['extracted_code'] = code
                    session_info['code_length'] = len(code)
                    sessions_with_code.append(session_info)
                    logger.info(f"📋 Found code in session: {session_name}")
        
        return sessions_with_code

    def get_code_from_correlation_id(self, agent_name: str, correlation_id: str,
                                   code_patterns: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get code from a specific correlation ID
        
        Args:
            agent_name: Name of the source agent
            correlation_id: Correlation ID to search for
            code_patterns: Optional code patterns to look for
            
        Returns:
            Dict with code and metadata, or None if not found
        """
        # Find agent
        agent_id = self.find_agent_by_name(agent_name)
        if not agent_id:
            return None
        
        # Find sessions with correlation ID
        matching_sessions = self.find_sessions_by_correlation_id(agent_id, correlation_id)
        
        for session_info in matching_sessions:
            session_id = session_info['session_id']
            code = self.extract_input_code_from_session(agent_id, session_id, code_patterns)
            if code:
                return {
                    'code': code,
                    'session_id': session_id,
                    'session_name': session_info.get('session_name'),
                    'agent_id': agent_id,
                    'agent_name': agent_name,
                    'correlation_id': correlation_id
                }
        
        return None

    def get_most_recent_code(self, agent_name: str, 
                           session_patterns: Optional[List[str]] = None,
                           code_patterns: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get code from the most recent session
        
        Args:
            agent_name: Name of the source agent
            session_patterns: Session name patterns to look for
            code_patterns: Code content patterns to look for
            
        Returns:
            Dict with code and metadata, or None if not found
        """
        # Find agent
        agent_id = self.find_agent_by_name(agent_name)
        if not agent_id:
            return None
        
        # Get recent sessions with code
        sessions_with_code = self.get_recent_sessions_with_code(
            agent_id, session_patterns, code_patterns, max_sessions=10
        )
        
        if sessions_with_code:
            latest_session = sessions_with_code[0]  # Already sorted by most recent
            return {
                'code': latest_session['extracted_code'],
                'session_id': latest_session['session_id'],
                'session_name': latest_session.get('session_name'),
                'agent_id': agent_id,
                'agent_name': agent_name,
                'code_length': latest_session['code_length']
            }
        
        return None

    def list_all_agents(self) -> Dict[str, Any]:
        """List all available agents for debugging/discovery
        
        Returns:
            Dict with agent information
        """
        try:
            response = self.client._client.get("agents")
            
            if response.status_code != 200:
                return {"error": f"Failed to list agents: HTTP {response.status_code}"}
                
            data = response.json()
            agents = data.get('data', [])
            
            agent_list = []
            for agent in agents:
                agent_config = agent.get('agent_config', {})
                agent_list.append({
                    'agent_id': agent.get('agent_id'),
                    'name': agent_config.get('name', 'unnamed'),
                    'model': agent_config.get('model'),
                    'created_at': agent.get('created_at'),
                    'session_count': len(self.get_agent_sessions(agent.get('agent_id')))
                })
            
            return {
                "total_agents": len(agent_list),
                "agents": agent_list
            }
            
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return {"error": str(e)}

    def get_agent_session_summary(self, agent_name: str, 
                                session_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get summary of sessions for an agent
        
        Args:
            agent_name: Name of the agent
            session_patterns: Session patterns to filter by
            
        Returns:
            Summary dictionary
        """
        try:
            # Find agent ID by name
            agent_id = self.find_agent_by_name(agent_name)
            if not agent_id:
                return {"error": f"Agent '{agent_name}' not found"}
            
            all_sessions = self.get_agent_sessions(agent_id)
            
            # Filter sessions by patterns
            if session_patterns is None:
                session_patterns = ['chef_analysis_', 'simple_', 'code_gen_']
            
            filtered_sessions = []
            sessions_with_code = 0
            
            for session in all_sessions:
                session_id = session.get('session_id', '')
                session_name = session.get('session_name', '')
                
                # Check if session matches patterns
                if any(pattern in session_name for pattern in session_patterns):
                    has_code = bool(self.extract_input_code_from_session(agent_id, session_id))
                    if has_code:
                        sessions_with_code += 1
                    
                    filtered_sessions.append({
                        'session_id': session_id,
                        'session_name': session_name,
                        'started_at': session.get('started_at'),
                        'has_code': has_code
                    })
            
            return {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "total_sessions": len(all_sessions),
                "filtered_sessions": len(filtered_sessions),
                "sessions_with_code": sessions_with_code,
                "recent_sessions": filtered_sessions[:10]  # Return last 10 for inspection
            }
            
        except Exception as e:
            logger.error(f"Error getting session summary for {agent_name}: {e}")
            return {"error": str(e)}

    def _extract_code_from_message(self, message: Dict[str, Any], 
                                 patterns: Optional[List[str]] = None) -> Optional[str]:
        """Extract code from a message using configurable patterns
        
        Args:
            message: Message dictionary from session turn
            patterns: Optional list of patterns to look for
            
        Returns:
            Extracted code string or None
        """
        content = ""
        
        # Handle different message content formats
        if isinstance(message.get('content'), str):
            content = message['content']
        elif isinstance(message.get('content'), list):
            # Handle multimodal content
            for item in message['content']:
                if isinstance(item, dict) and item.get('type') == 'text':
                    content += item.get('text', '')
        
        if not content:
            return None
        
        # Use provided patterns or default chef patterns
        if patterns is None:
            patterns = self._get_default_chef_patterns()
        
        return self._apply_extraction_patterns(content, patterns)

    def _get_default_chef_patterns(self) -> List[str]:
        """Get default patterns for extracting chef cookbook code"""
        return [
            'cookbook_with_files',  # Cookbook: name with === File: patterns
            'cookbook_tags',        # <COOKBOOK>...</COOKBOOK>
            'chef_file_structure',  # metadata.rb, recipes/, etc.
            'chef_code_indicators'  # include_recipe, package, service, etc.
        ]

    def _apply_extraction_patterns(self, content: str, patterns: List[str]) -> Optional[str]:
        """Apply extraction patterns to content
        
        Args:
            content: Content to extract from
            patterns: List of pattern names to apply
            
        Returns:
            Extracted code or None
        """
        for pattern in patterns:
            if pattern == 'cookbook_with_files':
                # Pattern 1: Look for cookbook content starting with "Cookbook: name"
                if content.startswith('Cookbook:') and ('=== ' in content or 'metadata.rb' in content):
                    return content.strip()
            
            elif pattern == 'cookbook_tags':
                # Pattern 2: Look for <COOKBOOK> tags
                cookbook_pattern = r'<COOKBOOK>(.*?)</COOKBOOK>'
                cookbook_matches = re.findall(cookbook_pattern, content, re.DOTALL)
                if cookbook_matches:
                    return cookbook_matches[0].strip()
            
            elif pattern == 'chef_file_structure':
                # Pattern 3: Look for Chef file structure indicators
                if any(indicator in content for indicator in ['=== ', 'metadata.rb', 'recipes/', 'attributes/']):
                    if len(content.strip()) > 100:  # Only return substantial content
                        return content.strip()
            
            elif pattern == 'chef_code_indicators':
                # Pattern 4: Look for Chef code indicators
                if any(indicator in content.lower() for indicator in ['cookbook:', 'include_recipe', 'package ', 'service ', 'template ']):
                    if len(content.strip()) > 100:  # Only return substantial content
                        return content.strip()
            
            elif pattern == 'any_substantial_code':
                # Pattern 5: Any substantial code content
                if len(content.strip()) > 50:
                    return content.strip()
        
        return None

    def create_custom_patterns(self, **kwargs) -> List[str]:
        """Create custom extraction patterns for specific use cases
        
        Example usage:
            patterns = session_manager.create_custom_patterns(
                languages=['python', 'javascript'],
                frameworks=['flask', 'fastapi'],
                file_extensions=['.py', '.js'],
                keywords=['class', 'function', 'import']
            )
        """
        patterns = []
        
        if 'languages' in kwargs:
            patterns.append('language_specific')
            
        if 'frameworks' in kwargs:
            patterns.append('framework_specific')
            
        if 'file_extensions' in kwargs:
            patterns.append('file_extension_based')
            
        if 'keywords' in kwargs:
            patterns.append('keyword_based')
            
        # Store the pattern config for later use
        self._custom_pattern_config = kwargs
        
        return patterns

    def get_session_statistics(self, agent_name: str) -> Dict[str, Any]:
        """Get detailed statistics about sessions for an agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Statistics dictionary
        """
        try:
            agent_id = self.find_agent_by_name(agent_name)
            if not agent_id:
                return {"error": f"Agent '{agent_name}' not found"}
            
            sessions = self.get_agent_sessions(agent_id)
            
            stats = {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "total_sessions": len(sessions),
                "session_types": {},
                "sessions_with_code": 0,
                "recent_activity": [],
                "code_extraction_success_rate": 0
            }
            
            # Analyze session types and code extraction
            code_successes = 0
            for session in sessions:
                session_name = session.get('session_name', '')
                
                # Count session types
                if 'chef_analysis_' in session_name:
                    stats["session_types"]["chef_analysis"] = stats["session_types"].get("chef_analysis", 0) + 1
                elif 'simple_' in session_name:
                    stats["session_types"]["simple"] = stats["session_types"].get("simple", 0) + 1
                elif 'code_gen_' in session_name:
                    stats["session_types"]["code_generation"] = stats["session_types"].get("code_generation", 0) + 1
                else:
                    stats["session_types"]["other"] = stats["session_types"].get("other", 0) + 1
                
                # Check for code extraction success
                session_id = session.get('session_id')
                if self.extract_input_code_from_session(agent_id, session_id):
                    stats["sessions_with_code"] += 1
                    code_successes += 1
            
            # Calculate success rate
            if len(sessions) > 0:
                stats["code_extraction_success_rate"] = (code_successes / len(sessions)) * 100
            
            # Get recent activity (last 5 sessions)
            recent_sessions = sorted(sessions, key=lambda x: x.get('started_at', ''), reverse=True)[:5]
            for session in recent_sessions:
                stats["recent_activity"].append({
                    "session_name": session.get('session_name'),
                    "started_at": session.get('started_at'),
                    "has_code": bool(self.extract_input_code_from_session(agent_id, session.get('session_id')))
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting session statistics for {agent_name}: {e}")
            return {"error": str(e)}