"""
Context Agent State Definitions

Simple state management following the Agentic RAG tutorial pattern.
"""

from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig
from typing import Optional


# Use simple MessagesState as per tutorial
# No custom state needed - MessagesState contains messages list which is sufficient

def get_user_id_from_config(config: RunnableConfig) -> str:
    """Extract user ID from config, with fallback to anonymous"""
    if not config:
        return "anonymous"
    return config.get("configurable", {}).get("user_id", "anonymous")


def log_query_pattern(store: BaseStore, user_id: str, query) -> None:
    """Log user query pattern for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        from datetime import datetime
        
        # Handle different query formats (string, list, or object)
        if isinstance(query, list):
            query_text = " ".join(str(item) for item in query)
        elif hasattr(query, 'content'):
            query_text = str(query.content)
        else:
            query_text = str(query)
        
        query_namespace = (user_id, "query_patterns")
        query_log = {
            "query": query_text[:200],
            "timestamp": datetime.now().isoformat(),
            "query_type": "ansible_automation" if "ansible" in query_text.lower() else "general"
        }
        store.put(query_namespace, str(uuid.uuid4()), query_log)
    except Exception as e:
        print(f"⚠️ Query logging error: {e}")


def save_successful_retrieval(store: BaseStore, user_id: str, query: str, response: str) -> None:
    """Save successful query-response pair for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        import hashlib
        from datetime import datetime
        
        # Save successful query-context pair for learning
        retrieval_namespace = (user_id, "successful_retrievals")
        query_context_pair = {
            "query": query[:200],
            "context": response[:500],
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "pattern_hash": hashlib.sha256(f"{query}{response}".encode()).hexdigest()[:12]
        }
        store.put(retrieval_namespace, str(uuid.uuid4()), query_context_pair)
        
        # Update user preferences
        user_namespace = (user_id, "context_preferences")
        prefs = {
            "detail_level": "normal",
            "last_query_type": "ansible_automation" if "ansible" in query.lower() else "general",
            "last_activity": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        store.put(user_namespace, "profile", prefs)
        
    except Exception as e:
        print(f"⚠️ Retrieval save error: {e}")