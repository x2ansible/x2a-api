"""
Context Agent State Management

State management for Agentic RAG workflow with memory and learning capabilities.
Follows LangGraph best practices with MessagesState foundation plus context-specific extensions.

Key Features:
- MessagesState foundation for LangGraph Studio compatibility
- User preference tracking and learning patterns
- Query pattern analysis for improvement
- Memory management for successful retrievals
- Type-safe configuration and utility functions
"""

from langgraph.graph import MessagesState
from langchain_core.runnables import RunnableConfig
from typing import Optional, Any, Dict, List
from typing_extensions import TypedDict

# Make BaseStore import optional for compatibility across LangGraph versions
try:
    from langgraph.store.base import BaseStore
except ImportError:
    # Fallback for older LangGraph versions  
    BaseStore = Any


# ============================================================================
# STATE SCHEMA DEFINITIONS
# ============================================================================

class UserPreferences(TypedDict, total=False):
    """User preference schema for personalized context retrieval."""
    detail_level: str                    # "brief", "normal", "detailed"
    preferred_topics: List[str]          # User's frequent topic areas
    last_query_type: str                 # "ansible_automation", "general", etc.
    last_activity: str                   # ISO timestamp
    retrieval_history_count: int         # Number of successful retrievals


class QueryMetrics(TypedDict, total=False):
    """Query analysis metrics for learning and optimization."""
    query_length: int                    # Character count
    query_complexity: str                # "simple", "medium", "complex"
    topics_identified: List[str]         # Detected topic areas
    retrieval_success: bool              # Whether retrieval was successful
    relevance_score: float               # Document relevance score (0-1)


# Note: We use MessagesState as the foundation since it provides:
# - messages: List of conversation messages (with proper reducers)
# - LangGraph Studio compatibility  
# - Standard message handling patterns
# 
# For context-specific state, we use utility functions and memory stores
# rather than extending the state schema unnecessarily. This keeps the
# workflow simple while enabling advanced features through the store layer.

# ============================================================================
# CONFIGURATION AND USER MANAGEMENT
# ============================================================================

def get_user_id_from_config(config: Optional[RunnableConfig]) -> str:
    """
    Extract user ID from LangGraph configuration with robust fallback.
    
    Args:
        config: LangGraph runtime configuration object
        
    Returns:
        User ID string, defaults to "anonymous" if not found
    """
    if not config:
        return "anonymous"
    
    configurable = config.get("configurable", {})
    return configurable.get("user_id", "anonymous")


def get_user_preferences(store: Optional[BaseStore], user_id: str) -> UserPreferences:
    """
    Retrieve user preferences from memory store.
    
    Args:
        store: LangGraph memory store instance
        user_id: User identifier
        
    Returns:
        UserPreferences object with defaults if not found
    """
    if not store:
        return UserPreferences()
    
    try:
        user_namespace = (user_id, "context_preferences")
        prefs = store.get(user_namespace, "profile")
        
        if prefs:
            return UserPreferences(**prefs.value) if hasattr(prefs, 'value') else UserPreferences(**prefs)
        else:
            # Return sensible defaults
            return UserPreferences(
                detail_level="normal",
                preferred_topics=[],
                last_query_type="general",
                retrieval_history_count=0
            )
    except Exception as e:
        print(f"⚠️ Failed to retrieve user preferences: {e}")
        return UserPreferences()


# ============================================================================
# QUERY PATTERN ANALYSIS AND LEARNING
# ============================================================================

def analyze_query_metrics(query_text: str) -> QueryMetrics:
    """
    Analyze query to extract metrics for learning and optimization.
    
    Args:
        query_text: The user's query text
        
    Returns:
        QueryMetrics with analyzed information
    """
    # Basic query analysis
    query_length = len(query_text)
    
    # Determine complexity based on length and structure
    if query_length < 20:
        complexity = "simple"
    elif query_length < 100:
        complexity = "medium"
    else:
        complexity = "complex"
    
    # Identify topics (can be enhanced with NLP)
    topics = []
    ansible_keywords = ["ansible", "playbook", "role", "task", "module", "inventory"]
    if any(keyword in query_text.lower() for keyword in ansible_keywords):
        topics.append("ansible_automation")
    
    if any(keyword in query_text.lower() for keyword in ["best practice", "recommendation", "how to"]):
        topics.append("guidance")
    
    return QueryMetrics(
        query_length=query_length,
        query_complexity=complexity,
        topics_identified=topics,
        retrieval_success=False,  # Will be updated later
        relevance_score=0.0       # Will be updated after grading
    )


def log_query_pattern(store: Optional[BaseStore], user_id: str, query: Any) -> None:
    """
    Log user query pattern for learning and personalization.
    
    Args:
        store: LangGraph memory store instance  
        user_id: User identifier
        query: Query in various formats (string, message object, etc.)
    """
    if not store:
        return
        
    try:
        import uuid
        from datetime import datetime
        
        # Normalize query to text
        if isinstance(query, list):
            query_text = " ".join(str(item) for item in query)
        elif hasattr(query, 'content'):
            query_text = str(query.content)
        else:
            query_text = str(query)
        
        # Analyze query metrics
        metrics = analyze_query_metrics(query_text)
        
        # Create query log entry
        query_namespace = (user_id, "query_patterns")
        query_log = {
            "query": query_text[:200],  # Truncate for storage efficiency
            "timestamp": datetime.now().isoformat(),
            "query_type": "ansible_automation" if "ansible" in query_text.lower() else "general",
            "metrics": dict(metrics)
        }
        
        store.put(query_namespace, str(uuid.uuid4()), query_log)
        
    except Exception as e:
        print(f"⚠️ Query pattern logging error: {e}")


def save_successful_retrieval(store: Optional[BaseStore], user_id: str, query: str, response: str, relevance_score: float = 1.0) -> None:
    """
    Save successful query-response pair for learning and user preference updates.
    
    Args:
        store: LangGraph memory store instance
        user_id: User identifier  
        query: Original user query
        response: Generated response
        relevance_score: Document relevance score (0-1)
    """
    if not store:
        return
        
    try:
        import uuid
        import hashlib
        from datetime import datetime
        
        # Create content hash for deduplication
        content_hash = hashlib.sha256(f"{query}{response}".encode()).hexdigest()[:12]
        
        # Save successful retrieval record
        retrieval_namespace = (user_id, "successful_retrievals")
        retrieval_record = {
            "query": query[:200],
            "response": response[:500],
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "relevance_score": relevance_score,
            "content_hash": content_hash
        }
        store.put(retrieval_namespace, str(uuid.uuid4()), retrieval_record)
        
        # Update user preferences with learning
        current_prefs = get_user_preferences(store, user_id)
        updated_prefs = UserPreferences(
            detail_level=current_prefs.get("detail_level", "normal"),
            preferred_topics=current_prefs.get("preferred_topics", []),
            last_query_type="ansible_automation" if "ansible" in query.lower() else "general",
            last_activity=datetime.now().isoformat(),
            retrieval_history_count=current_prefs.get("retrieval_history_count", 0) + 1
        )
        
        user_namespace = (user_id, "context_preferences")
        store.put(user_namespace, "profile", dict(updated_prefs))
        
    except Exception as e:
        print(f"⚠️ Successful retrieval save error: {e}")


# ============================================================================
# STATE UTILITY FUNCTIONS
# ============================================================================

def create_empty_messages_state() -> MessagesState:
    """
    Create an empty MessagesState for testing and initialization.
    
    Returns:
        Empty MessagesState with proper structure
    """
    return MessagesState(messages=[])


def validate_messages_state(state: MessagesState) -> bool:
    """
    Validate that a MessagesState object has the required structure.
    
    Args:
        state: MessagesState object to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check that state has messages key
        if "messages" not in state:
            return False
            
        # Check that messages is a list
        if not isinstance(state["messages"], list):
            return False
            
        return True
    except Exception:
        return False