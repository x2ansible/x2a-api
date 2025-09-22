"""
Neo4j Connection Utilities

Handles connection to Neo4j database with configuration from config.yaml.
Can create database if it doesn't exist and set up vector indices.
"""

import asyncio
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from neo4j import AsyncGraphDatabase, GraphDatabase, Driver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, ClientError

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))


def _load_config_sync() -> Dict[str, Any]:
    """Load configuration from config.yaml synchronously"""
    config_path = Path(__file__).parent.parent.parent.parent.parent / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml asynchronously"""
    return await asyncio.to_thread(_load_config_sync)


class Neo4jConnectionManager:
    """
    Manages Neo4j connections with automatic database creation and setup.
    All configuration comes from config.yaml - no hardcoded values.
    """
    
    def __init__(self):
        self.config = _load_config_sync()
        self.neo4j_config = self.config.get("neo4j", {})
        self.driver: Optional[Driver] = None
        self.database_name = self.neo4j_config.get("database", "neo4j")
        
        # Validate required config
        required_fields = ["uri", "username", "password"]
        for field in required_fields:
            if not self.neo4j_config.get(field):
                raise ValueError(f"Missing required Neo4j config field: {field}")
    
    def connect(self) -> Driver:
        """
        Connect to Neo4j and return driver.
        Creates database if it doesn't exist.
        """
        if self.driver:
            return self.driver
        
        try:
            print(f"🔗 Connecting to Neo4j at {self.neo4j_config['uri']}")
            
            # Create driver
            self.driver = GraphDatabase.driver(
                self.neo4j_config["uri"],
                auth=(self.neo4j_config["username"], self.neo4j_config["password"]),
                max_connection_lifetime=self.neo4j_config.get("max_connection_lifetime", 3600),
                max_connection_pool_size=self.neo4j_config.get("max_connection_pool_size", 50),
                connection_timeout=self.neo4j_config.get("connection_timeout", 30)
            )
            
            # Test connection
            self.driver.verify_connectivity()
            print(" Neo4j connection successful")
            
            # Create database if needed
            self._ensure_database_exists()
            
            # Set up schema and indices
            self._setup_schema()
            
            return self.driver
            
        except ServiceUnavailable as e:
            print(f" Neo4j service unavailable: {e}")
            print("💡 Make sure Neo4j Desktop is running and accessible")
            raise
        except Exception as e:
            print(f" Neo4j connection failed: {e}")
            raise
    
    def _ensure_database_exists(self):
        """Create database if it doesn't exist"""
        
        # Note: Database creation requires Enterprise edition or Neo4j 4.0+
        # For Community edition, we'll just use the default database
        try:
            # Try to create database (works in Enterprise/Aura)
            with self.driver.session(database="system") as session:
                # Check if database exists
                result = session.run(
                    "SHOW DATABASES YIELD name WHERE name = $db_name",
                    db_name=self.database_name
                )
                
                if not result.single():
                    print(f"🔄 Creating database: {self.database_name}")
                    session.run(f"CREATE DATABASE {self.database_name}")
                    print(f" Database '{self.database_name}' created")
                else:
                    print(f" Database '{self.database_name}' already exists")
                    
        except ClientError as e:
            if "Unsupported administration command" in str(e):
                print(f"ℹ️  Using default database (Community Edition)")
                self.database_name = "neo4j"  # Use default for Community Edition
            else:
                print(f"⚠️  Database creation warning: {e}")
    
    def _setup_schema(self):
        """Set up schema, constraints, and vector indices"""
        
        print("🔧 Setting up Neo4j schema and indices...")
        
        with self.driver.session(database=self.database_name) as session:
            try:
                # Create constraints for uniqueness
                constraints = [
                    "CREATE CONSTRAINT automation_pattern_id IF NOT EXISTS FOR (p:AutomationPattern) REQUIRE p.id IS UNIQUE",
                    "CREATE CONSTRAINT platform_name IF NOT EXISTS FOR (p:Platform) REQUIRE p.name IS UNIQUE",
                    "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE"
                ]
                
                for constraint in constraints:
                    try:
                        session.run(constraint)
                        print(f" Constraint created: {constraint.split()[-7]}")  # Extract constraint name
                    except ClientError as e:
                        if "already exists" not in str(e):
                            print(f"⚠️  Constraint warning: {e}")
                
                # Create regular indices for performance
                indices = [
                    "CREATE INDEX pattern_name IF NOT EXISTS FOR (p:AutomationPattern) ON (p.name)",
                    "CREATE INDEX pattern_platform IF NOT EXISTS FOR (p:AutomationPattern) ON (p.platform)",
                    "CREATE INDEX pattern_category IF NOT EXISTS FOR (p:AutomationPattern) ON (p.category)"
                ]
                
                for index in indices:
                    try:
                        session.run(index)
                        print(f" Index created: {index.split()[-4]}")  # Extract index field
                    except ClientError as e:
                        if "already exists" not in str(e):
                            print(f"⚠️  Index warning: {e}")
                
                # Create vector index (Neo4j 5.0+)
                self._create_vector_index(session)
                
                print(" Schema setup completed")
                
            except Exception as e:
                print(f"⚠️  Schema setup warning: {e}")
    
    def _create_vector_index(self, session):
        """Create vector index for semantic search"""
        
        vector_config = self.neo4j_config
        index_name = vector_config.get("vector_index_name", "automation_patterns_embedding")
        dimension = vector_config.get("embedding_dimension", 384)
        similarity_function = vector_config.get("similarity_function", "cosine")
        
        try:
            # Check if vector index already exists
            result = session.run("SHOW INDEXES YIELD name WHERE name = $index_name", index_name=index_name)
            
            if not result.single():
                print(f"🔄 Creating vector index: {index_name}")
                
                # Create vector index for embeddings
                vector_index_query = f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (p:AutomationPattern) ON (p.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {dimension},
                        `vector.similarity_function`: '{similarity_function}'
                    }}
                }}
                """
                
                session.run(vector_index_query)
                print(f" Vector index '{index_name}' created")
            else:
                print(f" Vector index '{index_name}' already exists")
                
        except ClientError as e:
            if "Unsupported" in str(e) or "vector" in str(e).lower():
                print(f"⚠️  Vector indices not supported in this Neo4j version")
                print(f"    Consider upgrading to Neo4j 5.0+ for vector search capabilities")
            else:
                print(f"⚠️  Vector index creation warning: {e}")
    
    def get_session(self):
        """Get a Neo4j session for the configured database"""
        if not self.driver:
            self.connect()
        
        return self.driver.session(database=self.database_name)
    
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.driver = None
            print(" Neo4j connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class Neo4jConnection:
    """
    Async-compatible Neo4j connection manager for use with async/await patterns.
    This is the class expected by the ingestion pipeline.
    """
    def __init__(self):
        # Don't load config here - do it in __aenter__ to avoid blocking I/O
        self.neo4j_config = None
        self.uri = None
        self.username = None
        self.password = None
        self.database = None
        self.vector_index_name = None
        self.embedding_dimension = None
        self.similarity_function = None
        self.driver: Optional[Driver] = None

    async def __aenter__(self):
        """Async context manager entry: connect to Neo4j and ensure DB/schema."""
        # Load config asynchronously to avoid blocking I/O
        await self._load_config()
        await self.connect()
        await self.ensure_database_and_schema()
        return self
    
    async def _load_config(self):
        """Load configuration asynchronously"""
        config = await load_config()
        self.neo4j_config = config.get("neo4j", {})
        
        self.uri = self.neo4j_config.get("uri", "neo4j://127.0.0.1:7687")
        self.username = self.neo4j_config.get("username", "neo4j")
        self.password = self.neo4j_config.get("password", "password")
        self.database = self.neo4j_config.get("database", "neo4j")
        
        self.vector_index_name = self.neo4j_config.get("vector_index_name", "automation_patterns_embedding")
        self.embedding_dimension = self.neo4j_config.get("embedding_dimension", 384)
        self.similarity_function = self.neo4j_config.get("similarity_function", "cosine")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit: close Neo4j driver."""
        await self.close()

    async def connect(self):
        """Establish connection to Neo4j."""
        print(f"Attempting to connect to Neo4j at {self.uri} as {self.username}...")
        self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.username, self.password))
        try:
            await self.driver.verify_connectivity()
            print(" Neo4j connection verified.")
        except Exception as e:
            print(f" Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            print("Closing Neo4j connection.")
            await self.driver.close()
            self.driver = None

    async def _run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None, db_name: Optional[str] = None):
        """Helper to run a Cypher query."""
        if not self.driver:
            raise RuntimeError("Neo4j driver is not initialized.")
        
        target_db = db_name if db_name else self.database
        async with self.driver.session(database=target_db) as session:
            result = await session.run(query, parameters)
            return [record async for record in result]

    async def ensure_database_and_schema(self):
        """
        Ensures the target database exists and sets up necessary schema (constraints, indices, vector index).
        """
        print(f"Ensuring Neo4j database '{self.database}' and schema...")
        
        # 1. Ensure the database exists (requires system admin context)
        try:
            # Attempt to create the database if it's not the default 'neo4j'
            if self.database != "neo4j":
                await self._run_query(f"CREATE DATABASE {self.database} IF NOT EXISTS", db_name="system")
                print(f"ℹ️  Database '{self.database}' ensured (or already exists).")
            else:
                print(f"ℹ️  Using default database '{self.database}'.")
        except Exception as e:
            print(f"⚠️  Could not create database '{self.database}' (might lack permissions or it exists): {e}")
            print(f"    Proceeding with database '{self.database}', assuming it's accessible.")

        # 2. Create constraints and indices on the target database
        try:
            # Create constraints one by one
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:AutomationPattern) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE", 
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE"
            ]
            
            for constraint in constraints:
                await self._run_query(constraint)
            print(" Constraints ensured.")

            # Create indices one by one
            indices = [
                "CREATE INDEX IF NOT EXISTS FOR (p:AutomationPattern) ON (p.platform)",
                "CREATE INDEX IF NOT EXISTS FOR (p:AutomationPattern) ON (p.category)",
                "CREATE INDEX IF NOT EXISTS FOR (p:AutomationPattern) ON (p.tags)"
            ]
            
            for index in indices:
                await self._run_query(index)
            print(" Node property indices ensured.")

            # 3. Create vector index
            vector_index_query = f"""
                CREATE VECTOR INDEX {self.vector_index_name} IF NOT EXISTS
                FOR (p:AutomationPattern) ON p.embedding
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {self.embedding_dimension},
                    `vector.similarity_function`: '{self.similarity_function}'
                }}}}
            """
            await self._run_query(vector_index_query)
            print(f" Vector index '{self.vector_index_name}' ensured (dimensions: {self.embedding_dimension}, similarity: {self.similarity_function}).")

        except Exception as e:
            print(f" Failed to ensure schema for database '{self.database}': {e}")
            raise

    async def get_session(self) -> AsyncSession:
        """Get an async session for the configured database."""
        if not self.driver:
            await self.connect() # Ensure connected if not already
        return self.driver.session(database=self.database)


# Global connection manager instance
_connection_manager = None


def get_neo4j_connection() -> Neo4jConnectionManager:
    """Get the global Neo4j connection manager"""
    global _connection_manager
    
    if _connection_manager is None:
        _connection_manager = Neo4jConnectionManager()
    
    return _connection_manager


def test_connection():
    """Test Neo4j connection with current config"""
    print("🧪 Testing Neo4j Connection")
    print("-" * 40)
    
    try:
        with get_neo4j_connection() as neo4j:
            with neo4j.get_session() as session:
                # Test basic query
                result = session.run("RETURN 'Connection successful' AS message")
                message = result.single()["message"]
                print(f" {message}")
                
                # Test database info
                result = session.run("CALL dbms.components() YIELD name, versions")
                for record in result:
                    print(f"📊 {record['name']}: {record['versions'][0]}")
                
                return True
                
    except Exception as e:
        print(f" Connection test failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
