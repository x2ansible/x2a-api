"""
Agent-to-Agent Communication Clients

HTTP clients for communicating with Context Agent and Infrastructure Analysis Agent.
"""

import aiohttp
import asyncio
import json
import re
from typing import Dict, Any


class ContextAgentClient:
    """Client to communicate with Context Agent via HTTP"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:2024"):
        self.base_url = base_url
        self.context_agent_id = None  # Will be fetched dynamically
    
    async def get_context_agent_id(self):
        """Get the Context Agent assistant ID"""
        if self.context_agent_id:
            return self.context_agent_id
            
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/assistants/search",
                    json={}
                ) as response:
                    if response.status == 200:
                        assistants = await response.json()
                        for assistant in assistants:
                            if assistant.get("graph_id") == "context_agent":
                                self.context_agent_id = assistant["assistant_id"]
                                return self.context_agent_id
                        raise ValueError("Context Agent not found")
                    else:
                        raise ValueError(f"Failed to get assistants: {response.status}")
            except Exception as e:
                print(f" Error finding Context Agent: {e}")
                raise
    
    async def ask_context_agent(self, question: str) -> str:
        """Call Context Agent with a question and get best practices"""
        try:
            print(f"🔄 Calling Context Agent: {question[:100]}...")
            
            # Get assistant ID
            assistant_id = await self.get_context_agent_id()
            
            # Create thread and send message
            async with aiohttp.ClientSession() as session:
                # Create a new thread
                thread_data = {
                    "messages": [{"role": "user", "content": question}]
                }
                
                # Stream the conversation
                async with session.post(
                    f"{self.base_url}/threads/{assistant_id}/runs/stream",
                    json={
                        "assistant_id": assistant_id,
                        "input": thread_data,
                        "stream_mode": ["messages"]
                    }
                ) as response:
                    if response.status == 200:
                        # Process streaming response
                        full_response = ""
                        async for line in response.content:
                            if line:
                                try:
                                    line_text = line.decode('utf-8').strip()
                                    if line_text.startswith('data: '):
                                        data_text = line_text[6:]  # Remove 'data: ' prefix
                                        if data_text and data_text != '[DONE]':
                                            try:
                                                event_data = json.loads(data_text)
                                                # Extract assistant messages
                                                if isinstance(event_data, list) and len(event_data) >= 2:
                                                    message_type, message_data = event_data
                                                    if message_type == "messages/partial" or message_type == "messages/complete":
                                                        if isinstance(message_data, dict) and "content" in message_data:
                                                            if hasattr(message_data, 'get') and message_data.get("type") == "ai":
                                                                full_response = message_data["content"]
                                            except json.JSONDecodeError:
                                                continue
                                except UnicodeDecodeError:
                                    continue
                        
                        if full_response:
                            print(f" Context Agent response: {len(full_response)} characters")
                            return full_response
                        else:
                            return "Context Agent returned empty response"
                    else:
                        error_text = await response.text()
                        raise ValueError(f"Context Agent call failed: {response.status} - {error_text}")
                        
        except Exception as e:
            print(f" Error calling Context Agent: {e}")
            return f"Error getting best practices: {str(e)}"
    
    def ask_context_agent_sync(self, question: str) -> str:
        """Synchronous wrapper for ask_context_agent"""
        return asyncio.run(self.ask_context_agent(question))


class InfrastructureAnalysisClient:
    """Client to communicate with Infrastructure Analysis Agent for specifications"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:2024"):
        self.base_url = base_url
        self.infra_agent_id = None  # Will be fetched dynamically
    
    async def get_infra_agent_id(self):
        """Get the Infrastructure Analysis Agent assistant ID"""
        if self.infra_agent_id:
            return self.infra_agent_id
            
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/assistants/search",
                    json={}
                ) as response:
                    if response.status == 200:
                        assistants = await response.json()
                        for assistant in assistants:
                            if assistant.get("graph_id") == "infrastructure_analysis":
                                self.infra_agent_id = assistant["assistant_id"]
                                return self.infra_agent_id
                        raise ValueError("Infrastructure Analysis Agent not found")
                    else:
                        raise ValueError(f"Failed to get assistants: {response.status}")
            except Exception as e:
                print(f" Error finding Infrastructure Analysis Agent: {e}")
                raise
    
    async def detect_platform_and_analyze(self, infrastructure_code: str) -> dict:
        """Detect platform and perform comprehensive analysis using Infrastructure Analysis tools"""
        try:
            print(f"🔍 Calling Infrastructure Analysis Agent for platform detection and analysis...")
            
            # Get assistant ID
            assistant_id = await self.get_infra_agent_id()
            
            # Create thread and send message
            async with aiohttp.ClientSession() as session:
                # Create thread
                async with session.post(f"{self.base_url}/threads") as response:
                    if response.status == 200:
                        thread_data = await response.json()
                        thread_id = thread_data["thread_id"]
                    else:
                        raise ValueError(f"Failed to create thread: {response.status}")
                
                # Send analysis request to existing Infrastructure Analysis Agent
                analysis_message = f"""Please analyze this infrastructure code for migration to Ansible:

```
{infrastructure_code}
```

Perform your standard infrastructure analysis workflow including:
- Platform detection and classification
- Extract structured facts using appropriate tools (chef_facts_extractor, etc.)
- Generate formal infrastructure specifications
- Store results with deduplication
- Provide migration recommendations

Return comprehensive analysis suitable for code generation."""

                message_data = {
                    "content": analysis_message,
                    "role": "user"
                }
                
                async with session.post(
                    f"{self.base_url}/threads/{thread_id}/runs",
                    json={
                        "assistant_id": assistant_id,
                        "input": message_data,
                        "stream": False
                    }
                ) as response:
                    if response.status == 200:
                        run_data = await response.json()
                        
                        # Extract specification from response
                        messages = run_data.get("messages", [])
                        if messages:
                            # Look for the assistant's response
                            for message in reversed(messages):
                                if message.get("role") == "assistant":
                                    content = message.get("content")
                                    if isinstance(content, list) and content:
                                        # Extract text content
                                        text_content = ""
                                        for item in content:
                                            if isinstance(item, dict) and item.get("type") == "text":
                                                text_content += item.get("text", "")
                                        
                                        if text_content:
                                            print(f" Infrastructure analysis received: {len(text_content)} characters")
                                            # Parse the comprehensive analysis
                                            return self._parse_infrastructure_analysis(text_content)
                                    elif isinstance(content, str):
                                        print(f" Infrastructure analysis received: {len(content)} characters")
                                        return self._parse_infrastructure_analysis(content)
                            
                            return {
                                "platform": "unknown",
                                "analysis": "Infrastructure Analysis Agent returned no content",
                                "specification": "",
                                "error": "No analysis content found"
                            }
                        else:
                            return {
                                "platform": "unknown", 
                                "analysis": "Infrastructure Analysis Agent returned no messages",
                                "specification": "",
                                "error": "No messages returned"
                            }
                    else:
                        error_text = await response.text()
                        raise ValueError(f"Infrastructure Analysis call failed: {response.status} - {error_text}")
                        
        except Exception as e:
            print(f" Error calling Infrastructure Analysis Agent: {e}")
            return {
                "platform": "unknown",
                "analysis": f"Error analyzing infrastructure: {str(e)}",
                "specification": "",
                "error": str(e)
            }
    
    def _parse_infrastructure_analysis(self, analysis_text: str) -> dict:
        """Parse Infrastructure Analysis Agent response to extract structured information"""
        
        # Try to extract platform first
        detected_platform = "unknown"
        
        # Look for platform indicators in the analysis
        platform_patterns = {
            'chef': [r'chef\s+cookbook', r'chef\s+recipe', r'chef\s+attributes', r'\.rb\s+files?'],
            'puppet': [r'puppet\s+manifest', r'puppet\s+module', r'\.pp\s+files?'],
            'terraform': [r'terraform\s+configuration', r'\.tf\s+files?', r'hcl\s+configuration'],
            'bladelogic': [r'bladelogic\s+script', r'\.nsh\s+files?', r'blcli\s+command']
        }
        
        analysis_lower = analysis_text.lower()
        for platform, patterns in platform_patterns.items():
            if any(re.search(pattern, analysis_lower) for pattern in patterns):
                detected_platform = platform
                break
        
        # Try to extract specification section
        specification = ""
        
        # Look for specification markers
        spec_patterns = [
            r'## Infrastructure Specification[:\n](.+?)(?=##|$)',
            r'# Infrastructure Specification[:\n](.+?)(?=#|$)',
            r'Infrastructure Specification[:\n](.+?)(?=\n\n|\n#|$)',
            r'Specification[:\n](.+?)(?=\n\n|\n#|$)'
        ]
        
        for pattern in spec_patterns:
            match = re.search(pattern, analysis_text, re.DOTALL | re.IGNORECASE)
            if match:
                specification = match.group(1).strip()
                break
        
        # If no formal specification found, look for structured analysis
        if not specification:
            # Look for any structured content that could serve as specification
            structured_patterns = [
                r'## Analysis Results[:\n](.+?)(?=##|$)',
                r'## Summary[:\n](.+?)(?=##|$)',
                r'## Findings[:\n](.+?)(?=##|$)'
            ]
            
            for pattern in structured_patterns:
                match = re.search(pattern, analysis_text, re.DOTALL | re.IGNORECASE)
                if match:
                    specification = match.group(1).strip()
                    break
        
        return {
            "platform": detected_platform,
            "analysis": analysis_text,
            "specification": specification,
            "error": None
        }
    
    def detect_platform_and_analyze_sync(self, infrastructure_code: str) -> dict:
        """Synchronous wrapper for detect_platform_and_analyze"""
        return asyncio.run(self.detect_platform_and_analyze(infrastructure_code))
