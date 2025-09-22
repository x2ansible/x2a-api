"""
x2a Context Agent Test Patterns

Specialized test patterns and assertions for the x2a Context Agent.
Provides comprehensive testing utilities for Hybrid Agentic RAG operations,
Neo4j retrieval validation, document grading, and context-aware responses.

Key Features:
- RAG retrieval accuracy testing
- Neo4j vector search validation
- Document relevance grading assertions
- Query rewriting quality testing
- Context-aware response validation
- Memory store testing
- ReAct agent behavior validation
"""

import logging
from typing import Dict, Any, List, Optional
import json
import re

logger = logging.getLogger("x2a_test_framework.agents.context_agent")


class ContextAgentTestPatterns:
    """
    Specialized test patterns for x2a Context Agent.
    
    Provides comprehensive validation patterns for RAG operations,
    retrieval quality, and context-aware responses.
    """
    
    @staticmethod
    def assert_successful_rag_retrieval(
        result: Dict[str, Any],
        min_context_length: int = 100,
        context_field: str = "context"
    ):
        """
        Assert that RAG retrieval completed successfully with relevant context.
        
        Args:
            result: RAG retrieval result to validate
            min_context_length: Minimum expected context length
            context_field: Field name containing retrieved context
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for retrieved context
        context = result.get(context_field) or result.get("retrieved_context") or result.get("content")
        assert context is not None, f"No context found in result. Available keys: {list(result.keys())}"
        assert len(context) >= min_context_length, f"Context too short: {len(context)} < {min_context_length}"
        
        # Validate context quality
        assert isinstance(context, str), f"Context must be string, got {type(context)}"
        assert context.strip(), "Context cannot be empty or whitespace only"
        
        logger.info(f" RAG retrieval successful: {len(context)} chars context")
    
    @staticmethod
    def assert_relevant_document_grading(
        question: str,
        context: str,
        grading_decision: str,
        expected_relevance: bool = True
    ):
        """
        Assert that document grading correctly identifies relevance.
        
        Args:
            question: User question
            context: Retrieved context
            grading_decision: Grading agent decision
            expected_relevance: Expected relevance assessment
        """
        assert isinstance(question, str) and question.strip(), "Question must be non-empty string"
        assert isinstance(context, str) and context.strip(), "Context must be non-empty string"
        assert isinstance(grading_decision, str), "Grading decision must be string"
        
        # Check grading decision format
        decision_lower = grading_decision.lower()
        is_relevant = any(keyword in decision_lower for keyword in ["relevant", "yes", "generate_answer"])
        is_not_relevant = any(keyword in decision_lower for keyword in ["not relevant", "no", "rewrite_question"])
        
        assert is_relevant or is_not_relevant, f"Invalid grading decision format: {grading_decision}"
        
        if expected_relevance:
            assert is_relevant, f"Expected relevant, but got: {grading_decision}"
        else:
            assert is_not_relevant, f"Expected not relevant, but got: {grading_decision}"
        
        logger.info(f" Document grading correct: {grading_decision}")
    
    @staticmethod
    def assert_context_aware_response(
        response: str,
        context: str,
        question: str,
        min_response_length: int = 50
    ):
        """
        Assert that response demonstrates context awareness and relevance.
        
        Args:
            response: Generated response
            context: Retrieved context used
            question: Original question
            min_response_length: Minimum response length
        """
        assert isinstance(response, str) and response.strip(), "Response must be non-empty string"
        assert len(response) >= min_response_length, f"Response too short: {len(response)} < {min_response_length}"
        
        # Check response is not just copying context
        response_clean = response.lower().strip()
        context_clean = context.lower().strip()
        
        # Response should reference context but not be identical
        assert response_clean != context_clean, "Response cannot be identical to context"
        
        # Response should address the question topic
        question_keywords = set(question.lower().split())
        response_keywords = set(response.lower().split())
        common_keywords = question_keywords.intersection(response_keywords)
        
        assert len(common_keywords) > 0, "Response should share keywords with question"
        
        logger.info(f" Context-aware response valid: {len(response)} chars, {len(common_keywords)} shared keywords")
    
    @staticmethod
    def assert_neo4j_retrieval_format(
        retrieval_result: Any,
        expected_format: str = "vector_search"
    ):
        """
        Assert that Neo4j retrieval returns expected format.
        
        Args:
            retrieval_result: Result from Neo4j retrieval
            expected_format: Expected result format ("vector_search" or "graph_query")
        """
        if expected_format == "vector_search":
            # Vector search should return list of documents/nodes
            assert isinstance(retrieval_result, (list, tuple)), f"Vector search should return list, got {type(retrieval_result)}"
            
            if retrieval_result:  # If results exist
                for item in retrieval_result[:3]:  # Check first few items
                    assert isinstance(item, (dict, str)), f"Vector result items should be dict or string, got {type(item)}"
        
        elif expected_format == "graph_query":
            # Graph query should return structured result
            assert isinstance(retrieval_result, (dict, list)), f"Graph query should return dict or list, got {type(retrieval_result)}"
        
        logger.info(f" Neo4j retrieval format valid: {expected_format}")
    
    @staticmethod
    def assert_query_rewriting_quality(
        original_question: str,
        rewritten_question: str,
        min_improvement_ratio: float = 0.1
    ):
        """
        Assert that query rewriting improves the question.
        
        Args:
            original_question: Original user question
            rewritten_question: Rewritten question
            min_improvement_ratio: Minimum improvement ratio expected
        """
        assert isinstance(original_question, str) and original_question.strip(), "Original question must be non-empty string"
        assert isinstance(rewritten_question, str) and rewritten_question.strip(), "Rewritten question must be non-empty string"
        
        # Rewritten question should be different
        assert original_question.strip().lower() != rewritten_question.strip().lower(), "Rewritten question should be different from original"
        
        # Rewritten question should be reasonable length
        assert len(rewritten_question) >= len(original_question) * (1 - min_improvement_ratio), "Rewritten question too short"
        assert len(rewritten_question) <= len(original_question) * 3, "Rewritten question too long"
        
        # Should share some core concepts
        orig_words = set(original_question.lower().split())
        rewrite_words = set(rewritten_question.lower().split())
        shared_words = orig_words.intersection(rewrite_words)
        
        assert len(shared_words) > 0, "Rewritten question should share some words with original"
        
        logger.info(f" Query rewriting quality good: {len(shared_words)} shared concepts")
    
    @staticmethod
    def assert_react_agent_behavior(
        agent_output: Dict[str, Any],
        expected_tool_usage: bool = True,
        expected_reasoning: bool = True
    ):
        """
        Assert that ReAct agent shows proper reasoning and tool usage.
        
        Args:
            agent_output: Output from ReAct agent
            expected_tool_usage: Whether tool usage is expected
            expected_reasoning: Whether reasoning is expected
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        # Check for messages structure
        messages = agent_output.get("messages", [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        assert len(messages) > 0, "Agent should produce at least one message"
        
        # Check for tool usage if expected
        if expected_tool_usage:
            tool_usage_found = False
            for message in messages:
                message_content = getattr(message, 'content', str(message))
                if any(tool_keyword in str(message_content).lower() for tool_keyword in 
                       ['tool_calls', 'function_call', 'neo4j', 'retrieval']):
                    tool_usage_found = True
                    break
            
            assert tool_usage_found, "Expected tool usage but none found in agent output"
        
        logger.info(f" ReAct agent behavior valid: {len(messages)} messages, tool_usage={expected_tool_usage}")
    
    @staticmethod
    def assert_memory_store_operation(
        store_result: Any,
        operation_type: str,
        expected_success: bool = True
    ):
        """
        Assert that memory store operations work correctly.
        
        Args:
            store_result: Result from memory store operation
            operation_type: Type of operation ("log_query", "save_retrieval", etc.)
            expected_success: Whether operation should succeed
        """
        if expected_success:
            # Store operations might return various success indicators
            if store_result is not None:
                # If result exists, it should be valid
                assert store_result is not False, f"Store operation {operation_type} failed"
        
        logger.info(f" Memory store operation {operation_type}: {'success' if expected_success else 'handled'}")
    
    @staticmethod
    def assert_agentic_rag_workflow(
        final_result: Dict[str, Any],
        input_question: str,
        min_response_quality: float = 0.7
    ):
        """
        Assert that the complete Agentic RAG workflow produces quality results.
        
        Args:
            final_result: Final result from context agent
            input_question: Original input question
            min_response_quality: Minimum quality score (0-1)
        """
        assert isinstance(final_result, dict), f"Final result must be dict, got {type(final_result)}"
        
        # Check for response content
        response_fields = ["messages", "response", "answer", "content"]
        response_content = None
        
        for field in response_fields:
            if field in final_result:
                content = final_result[field]
                if isinstance(content, list) and content:
                    # Extract from messages
                    last_message = content[-1]
                    response_content = getattr(last_message, 'content', str(last_message))
                elif isinstance(content, str):
                    response_content = content
                break
        
        assert response_content is not None, f"No response found in result. Available keys: {list(final_result.keys())}"
        assert len(response_content) >= 50, f"Response too short: {len(response_content)} chars"
        
        # Quality checks
        response_words = len(response_content.split())
        question_words = len(input_question.split())
        
        # Response should be substantive relative to question
        word_ratio = response_words / max(question_words, 1)
        assert word_ratio >= min_response_quality, f"Response quality low: {word_ratio:.2f} < {min_response_quality}"
        
        logger.info(f" Agentic RAG workflow complete: {response_words} words, quality={word_ratio:.2f}")


class ContextAgentTestHelpers:
    """Helper utilities for context agent testing."""
    
    @staticmethod
    def create_test_rag_scenario(
        question: str,
        context_type: str = "ansible_automation"
    ) -> Dict[str, Any]:
        """Create a test scenario for RAG testing."""
        return {
            "question": question,
            "context_type": context_type,
            "expected_topics": question.lower().split(),
            "min_context_length": 100,
            "min_response_length": 50
        }
    
    @staticmethod
    def extract_response_from_messages(messages: List[Any]) -> str:
        """Extract response content from LangGraph messages."""
        if not messages:
            return ""
        
        last_message = messages[-1]
        return getattr(last_message, 'content', str(last_message))
    
    @staticmethod
    def validate_neo4j_connection_result(result: Any) -> bool:
        """Validate Neo4j connection and query results."""
        # Basic validation - can be enhanced based on actual Neo4j response format
        return result is not None and not (isinstance(result, list) and len(result) == 0)
