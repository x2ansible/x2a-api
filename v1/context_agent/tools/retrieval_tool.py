"""
Neo4j Retrieval Tool for Context Agent

Handles search and retrieval from Neo4j knowledge base of Ansible patterns.
"""

from langchain.tools.retriever import create_retriever_tool
from langchain_core.documents import Document
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from context_agent.neo4j_utils.utils.connection import Neo4jConnection
from context_agent.neo4j_utils.utils.embeddings import EmbeddingGenerator


class Neo4jRetriever:
    """Simple Neo4j retriever that mimics LangChain's retriever interface"""
    
    def __init__(self):
        self.top_k = 5
    
    async def ainvoke(self, query, config=None):
        """Async retrieve - return documents"""
        # Handle both string and dict input (LangChain compatibility)
        if isinstance(query, dict):
            query_text = query.get("query", str(query))
        else:
            query_text = str(query)
        
        print(f"🔍 Neo4j retrieval for: {query_text}")
        
        # Generate embedding for query
        embedding_generator = await EmbeddingGenerator.create_async()
        query_embeddings = await asyncio.to_thread(embedding_generator.encode, [query_text])
        query_embedding = query_embeddings[0]
        
        # Search Neo4j
        async with Neo4jConnection() as neo4j_conn:
            results = await neo4j_conn._run_query("""
                CALL db.index.vector.queryNodes('automation_patterns_embedding', $top_k, $embedding)
                YIELD node, score
                WHERE score >= 0.4
                RETURN node.title as title, 
                       node.content as content,
                       node.category as category,
                       score
                ORDER BY score DESC
            """, {"embedding": query_embedding, "top_k": self.top_k})
        
        # Format as Document objects (LangChain compatibility)
        documents = []
        for record in results:
            doc_content = f"Title: {record['title']}\nCategory: {record['category']}\nContent: {record['content']}"
            doc = Document(
                page_content=doc_content,
                metadata={
                    "title": record['title'],
                    "category": record['category'],
                    "score": record['score']
                }
            )
            documents.append(doc)
        
        print(f" Retrieved {len(documents)} documents")
        return documents
    
    def invoke(self, query, config=None):
        """Sync version - run async in thread"""
        return asyncio.run(self.ainvoke(query, config))


from langchain_core.tools import tool

@tool
async def neo4j_vector_search_async(query: str) -> str:
    """
    Perform vector similarity search in Neo4j for Ansible automation patterns (async version).
    
    Uses embedding-based semantic search to find relevant Ansible content.
    Best for finding content based on meaning and context.
    """
    print(f"🔍 Neo4j vector search for: {query}")
    
    # Generate embedding for query
    embedding_generator = await EmbeddingGenerator.create_async()
    query_embeddings = await asyncio.to_thread(embedding_generator.encode, [query])
    query_embedding = query_embeddings[0]
    
    # Vector search in Neo4j
    async with Neo4jConnection() as neo4j_conn:
        results = await neo4j_conn._run_query("""
            CALL db.index.vector.queryNodes('automation_patterns_embedding', $top_k, $embedding)
            YIELD node, score
            WHERE score >= 0.4
            RETURN node.title as title, 
                   node.content as content,
                   node.category as category,
                   score
            ORDER BY score DESC
        """, {"embedding": query_embedding, "top_k": 5})
    
    # Format results
    formatted_results = []
    for record in results:
        formatted_results.append(
            f"**{record['title']}** (Category: {record['category']}, Score: {record['score']:.3f})\n"
            f"{record['content']}\n"
        )
    
    result_text = "\n---\n".join(formatted_results) if formatted_results else "No relevant patterns found."
    print(f" Vector search returned {len(formatted_results)} results")
    return result_text

@tool
def neo4j_vector_search(query: str) -> str:
    """
    Perform vector similarity search in Neo4j for Ansible automation patterns.
    
    Uses embedding-based semantic search to find relevant Ansible content.
    Best for finding content based on meaning and context.
    """
    print(f"🔍 Neo4j vector search for: {query}")
    
    try:
        # Use sync version of Neo4j operations
        import time
        from neo4j import GraphDatabase
        import numpy as np
        from sentence_transformers import SentenceTransformer
        
        # Load embedding model (sync)
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_embedding = model.encode([query])[0].tolist()
        
        # Neo4j connection (sync)
        uri = "neo4j://127.0.0.1:7687"  # Local Neo4j
        username = "neo4j"
        password = "password"
        
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        with driver.session() as session:
            # Vector similarity search
            result = session.run("""
                CALL db.index.vector.queryNodes('automation_patterns_embedding', $top_k, $embedding)
                YIELD node, score
                WHERE score >= 0.4
                RETURN node.title as title, 
                       node.content as content,
                       node.category as category,
                       score
                ORDER BY score DESC
            """, {"embedding": query_embedding, "top_k": 5})
            
            # Format results
            formatted_results = []
            for record in result:
                formatted_results.append(
                    f"**{record['title']}** (Category: {record['category']}, Score: {record['score']:.3f})\\n"
                    f"{record['content']}\\n"
                )
        
        driver.close()
        
        result_text = "\\n---\\n".join(formatted_results) if formatted_results else "No relevant patterns found."
        print(f" Vector search returned {len(formatted_results)} results")
        return result_text
        
    except Exception as e:
        print(f"⚠️ Neo4j vector search failed: {e}")
        return f"Neo4j search temporarily unavailable. Error: {str(e)}. Please try a different query or contact support."

@tool
async def neo4j_graph_query_async(query: str) -> str:
    """
    Perform graph-based query in Neo4j for Ansible automation patterns (async version).
    
    Uses graph relationships and structure to find connected information.
    Best for finding relationships between concepts and hierarchical content.
    """
    print(f"🔗 Neo4j graph query for: {query}")
    
    # Simple graph queries based on keywords
    graph_queries = []
    
    # Determine query type and build appropriate Cypher
    if any(keyword in query.lower() for keyword in ["role", "roles"]):
        graph_queries.append("""
            MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
            WHERE c.name CONTAINS 'roles' OR p.title CONTAINS 'role'
            RETURN p.title as title, p.content as content, c.name as category
            LIMIT 5
        """)
    elif any(keyword in query.lower() for keyword in ["playbook", "playbooks"]):
        graph_queries.append("""
            MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
            WHERE c.name CONTAINS 'playbooks' OR p.title CONTAINS 'playbook'
            RETURN p.title as title, p.content as content, c.name as category
            LIMIT 5
        """)
    elif any(keyword in query.lower() for keyword in ["best practice", "practices"]):
        graph_queries.append("""
            MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
            WHERE c.name CONTAINS 'best' OR p.title CONTAINS 'practice'
            RETURN p.title as title, p.content as content, c.name as category
            LIMIT 5
        """)
    else:
        # General query - find related patterns
        graph_queries.append("""
            MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
            RETURN p.title as title, p.content as content, c.name as category
            LIMIT 5
        """)
    
    # Execute graph queries
    all_results = []
    async with Neo4jConnection() as neo4j_conn:
        for graph_query in graph_queries:
            try:
                results = await neo4j_conn._run_query(graph_query, {})
                all_results.extend(results)
            except Exception as e:
                print(f"⚠️ Graph query failed: {e}")
    
    # Format results
    formatted_results = []
    for record in all_results[:5]:  # Limit to top 5
        formatted_results.append(
            f"**{record['title']}** (Category: {record['category']})\n"
            f"{record['content']}\n"
        )
    
    result_text = "\n---\n".join(formatted_results) if formatted_results else "No related patterns found."
    print(f" Graph query returned {len(formatted_results)} results")
    return result_text

@tool
def neo4j_graph_query(query: str) -> str:
    """
    Perform graph-based query in Neo4j for Ansible automation patterns.
    
    Uses graph relationships and structure to find connected information.
    Best for finding relationships between concepts and hierarchical content.
    """
    print(f"🔗 Neo4j graph query for: {query}")
    
    try:
        from neo4j import GraphDatabase
        
        # Neo4j connection (sync)
        uri = "neo4j://127.0.0.1:7687"  # Local Neo4j
        username = "neo4j"
        password = "password"
        
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        # Determine query type and build appropriate Cypher
        graph_queries = []
        
        if any(keyword in query.lower() for keyword in ["role", "roles"]):
            graph_queries.append("""
                MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
                WHERE c.name CONTAINS 'roles' OR p.title CONTAINS 'role'
                RETURN p.title as title, p.content as content, c.name as category
                LIMIT 5
            """)
        elif any(keyword in query.lower() for keyword in ["playbook", "playbooks"]):
            graph_queries.append("""
                MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
                WHERE c.name CONTAINS 'playbooks' OR p.title CONTAINS 'playbook'
                RETURN p.title as title, p.content as content, c.name as category
                LIMIT 5
            """)
        elif any(keyword in query.lower() for keyword in ["best practice", "practices"]):
            graph_queries.append("""
                MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
                WHERE c.name CONTAINS 'best' OR p.title CONTAINS 'practice'
                RETURN p.title as title, p.content as content, c.name as category
                LIMIT 5
            """)
        else:
            # General query - find related patterns
            graph_queries.append("""
                MATCH (p:Pattern)-[:BELONGS_TO_CATEGORY]->(c:Category)
                RETURN p.title as title, p.content as content, c.name as category
                LIMIT 5
            """)
        
        # Execute graph queries
        all_results = []
        with driver.session() as session:
            for graph_query in graph_queries:
                try:
                    result = session.run(graph_query, {})
                    all_results.extend(list(result))
                except Exception as e:
                    print(f"⚠️ Graph query failed: {e}")
        
        driver.close()
        
        # Format results
        formatted_results = []
        for record in all_results[:5]:  # Limit to top 5
            formatted_results.append(
                f"**{record['title']}** (Category: {record['category']})\\n"
                f"{record['content']}\\n"
            )
        
        result_text = "\\n---\\n".join(formatted_results) if formatted_results else "No related patterns found."
        print(f" Graph query returned {len(formatted_results)} results")
        return result_text
        
    except Exception as e:
        print(f"⚠️ Neo4j graph query failed: {e}")
        return f"Neo4j graph search temporarily unavailable. Error: {str(e)}. Please try a different query or contact support."


def get_retriever_tool():
    """Create and return the Neo4j retriever tool"""
    neo4j_retriever = Neo4jRetriever()
    
    return create_retriever_tool(
        neo4j_retriever,
        "retrieve_ansible_patterns", 
        "Search and return Ansible automation patterns, best practices, roles, and playbooks from the Neo4j database."
    )
