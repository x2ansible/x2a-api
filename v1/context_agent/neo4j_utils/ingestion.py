#!/usr/bin/env python3
"""
Neo4j Ingestion Pipeline for Red Hat Automation Good Practices

This module handles:
1. Cloning the Red Hat CoP automation good practices repository
2. Extracting content from .adoc files
3. Creating embeddings for text chunks
4. Storing content + embeddings + relationships in Neo4j
"""

import asyncio
import os
import shutil
import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from context_agent.neo4j_utils.utils.connection import Neo4jConnection
from context_agent.neo4j_utils.utils.embeddings import EmbeddingGenerator


@dataclass
class AutomationPattern:
    """Represents an automation pattern to be stored in Neo4j"""
    id: str
    title: str
    content: str
    category: str  # e.g., "roles", "playbooks", "collections"
    platform: str  # e.g., "ansible", "general"
    source_file: str
    section: Optional[str] = None
    tags: List[str] = None
    difficulty: Optional[str] = None  # "beginner", "intermediate", "advanced"
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class RedHatPracticesIngester:
    """
    Handles the complete ingestion pipeline for Red Hat automation practices into Neo4j
    """
    
    def __init__(self):
        self.repo_url = "https://github.com/redhat-cop/automation-good-practices.git"
        self.repo_dir = Path("./tmp/automation-good-practices")
        self.embedding_generator = EmbeddingGenerator()
        
        # Key files to process
        self.target_files = [
            "README.adoc",
            "roles/README.adoc", 
            "playbooks/README.adoc",
            "collections/README.adoc",
            "inventories/README.adoc",
            "structures/README.adoc",
            "plugins/README.adoc",
            "coding_style/README.adoc"
        ]
    
    async def run_full_ingestion(self) -> bool:
        """
        Run the complete ingestion pipeline
        """
        print("🚀 Starting Red Hat Automation Practices Ingestion Pipeline")
        print("=" * 70)
        
        try:
            # Step 1: Clone repository
            if not await self.clone_repository():
                return False
            
            # Step 2: Extract patterns from .adoc files
            patterns = await self.extract_patterns()
            if not patterns:
                print(" No patterns extracted")
                return False
            
            print(f" Extracted {len(patterns)} automation patterns")
            
            # Step 3: Generate embeddings
            patterns_with_embeddings = await self.generate_embeddings(patterns)
            
            # Step 4: Store in Neo4j
            success = await self.store_in_neo4j(patterns_with_embeddings)
            
            # Step 5: Cleanup
            await self.cleanup()
            
            if success:
                print("\n🎉 Ingestion pipeline completed successfully!")
                return True
            else:
                print("\n Ingestion pipeline failed")
                return False
                
        except Exception as e:
            print(f" Ingestion pipeline error: {e}")
            await self.cleanup()
            return False
    
    async def clone_repository(self) -> bool:
        """
        Clone the Red Hat automation good practices repository
        """
        print("\n📥 Cloning Red Hat Automation Good Practices Repository")
        print("-" * 50)
        
        try:
            # Remove existing directory if it exists
            if self.repo_dir.exists():
                print(f"🗑️  Removing existing directory: {self.repo_dir}")
                shutil.rmtree(self.repo_dir)
            
            # Create parent directory
            self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Clone repository
            print(f"📦 Cloning {self.repo_url}...")
            process = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", self.repo_url, str(self.repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for clone with longer timeout (120 seconds)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            except asyncio.TimeoutError:
                process.kill()
                print(" Git clone timed out after 120 seconds")
                return False
            
            if process.returncode == 0:
                print(" Repository cloned successfully")
                return True
            else:
                print(f" Git clone failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f" Clone error: {e}")
            return False
    
    async def extract_patterns(self) -> List[AutomationPattern]:
        """
        Extract automation patterns from .adoc files
        """
        print("\n📄 Extracting Patterns from .adoc Files")
        print("-" * 50)
        
        patterns = []
        
        for file_path in self.target_files:
            full_path = self.repo_dir / file_path
            
            if not full_path.exists():
                print(f"⚠️  File not found: {file_path}")
                continue
            
            print(f"📖 Processing: {file_path}")
            
            try:
                file_patterns = await self.extract_from_adoc_file(full_path, file_path)
                patterns.extend(file_patterns)
                print(f"    Extracted {len(file_patterns)} patterns")
                
            except Exception as e:
                print(f"    Error processing {file_path}: {e}")
        
        return patterns
    
    async def extract_from_adoc_file(self, file_path: Path, relative_path: str) -> List[AutomationPattern]:
        """
        Extract patterns from a single .adoc file
        """
        patterns = []
        
        # Read file content
        content = await asyncio.to_thread(file_path.read_text, encoding='utf-8')
        
        # Determine category from file path
        category = self.get_category_from_path(relative_path)
        
        # Split content into sections
        sections = self.parse_adoc_sections(content)
        
        for section_title, section_content in sections.items():
            if len(section_content.strip()) < 50:  # Skip very short sections
                continue
            
            pattern_id = self.generate_pattern_id(relative_path, section_title)
            
            pattern = AutomationPattern(
                id=pattern_id,
                title=section_title,
                content=section_content.strip(),
                category=category,
                platform="ansible",
                source_file=relative_path,
                section=section_title if section_title != "main" else None,
                tags=self.extract_tags_from_content(section_content),
                difficulty=self.infer_difficulty(section_content)
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def parse_adoc_sections(self, content: str) -> Dict[str, str]:
        """
        Parse AsciiDoc content into sections
        """
        sections = {}
        
        # Split by headers (=, ==, ===, etc.)
        header_pattern = r'^(={1,6})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = "main"
        current_content = []
        
        for line in lines:
            match = re.match(header_pattern, line, re.MULTILINE)
            
            if match:
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                level = len(match.group(1))
                title = match.group(2).strip()
                current_section = title
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def get_category_from_path(self, file_path: str) -> str:
        """
        Determine category from file path
        """
        if "roles/" in file_path:
            return "roles"
        elif "playbooks/" in file_path:
            return "playbooks"
        elif "collections/" in file_path:
            return "collections"
        elif "inventories/" in file_path:
            return "inventories"
        elif "structures/" in file_path:
            return "structures"
        elif "plugins/" in file_path:
            return "plugins"
        elif "coding_style/" in file_path:
            return "coding_style"
        else:
            return "general"
    
    def generate_pattern_id(self, file_path: str, section_title: str) -> str:
        """
        Generate a unique ID for a pattern
        """
        content = f"{file_path}#{section_title}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def extract_tags_from_content(self, content: str) -> List[str]:
        """
        Extract relevant tags from content
        """
        tags = []
        
        # Common Ansible concepts
        ansible_terms = [
            "playbook", "role", "task", "handler", "variable", "template", 
            "inventory", "collection", "module", "plugin", "vault", "galaxy",
            "become", "delegate", "loop", "conditional", "block", "rescue"
        ]
        
        content_lower = content.lower()
        for term in ansible_terms:
            if term in content_lower:
                tags.append(term)
        
        # Infrastructure tools
        if any(tool in content_lower for tool in ["chef", "puppet", "salt"]):
            tags.append("migration")
        
        return list(set(tags))  # Remove duplicates
    
    def infer_difficulty(self, content: str) -> str:
        """
        Infer difficulty level from content
        """
        content_lower = content.lower()
        
        # Advanced indicators
        if any(term in content_lower for term in [
            "advanced", "complex", "enterprise", "production", "scalability", 
            "performance", "security", "vault", "delegate", "strategy"
        ]):
            return "advanced"
        
        # Beginner indicators
        if any(term in content_lower for term in [
            "basic", "simple", "introduction", "getting started", "beginner", 
            "first", "easy", "quick start"
        ]):
            return "beginner"
        
        return "intermediate"
    
    async def generate_embeddings(self, patterns: List[AutomationPattern]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for all patterns
        """
        print("\n🧮 Generating Embeddings")
        print("-" * 50)
        
        # Prepare text for embedding
        texts = []
        for pattern in patterns:
            # Combine title and content for better semantic representation
            text = f"{pattern.title}\n\n{pattern.content}"
            texts.append(text)
        
        print(f"🔄 Generating embeddings for {len(texts)} patterns...")
        
        # Generate embeddings (run in thread since it's CPU intensive)
        embeddings = await asyncio.to_thread(self.embedding_generator.encode, texts)
        
        print(f" Generated {len(embeddings)} embeddings")
        
        # Combine patterns with embeddings
        patterns_with_embeddings = []
        for pattern, embedding in zip(patterns, embeddings):
            pattern_dict = {
                "id": pattern.id,
                "title": pattern.title,
                "content": pattern.content,
                "category": pattern.category,
                "platform": pattern.platform,
                "source_file": pattern.source_file,
                "section": pattern.section,
                "tags": pattern.tags,
                "difficulty": pattern.difficulty,
                "embedding": embedding,
                "created_at": datetime.utcnow().isoformat()
            }
            patterns_with_embeddings.append(pattern_dict)
        
        return patterns_with_embeddings
    
    async def store_in_neo4j(self, patterns: List[Dict[str, Any]]) -> bool:
        """
        Store patterns in Neo4j with embeddings and relationships
        """
        print("\n🗄️  Storing Patterns in Neo4j")
        print("-" * 50)
        
        try:
            async with Neo4jConnection() as neo4j_conn:
                # Clear existing automation patterns
                print("🗑️  Clearing existing automation patterns...")
                await neo4j_conn._run_query("""
                    MATCH (p:AutomationPattern)
                    DETACH DELETE p
                """)
                
                # Insert patterns
                print(f"📝 Inserting {len(patterns)} patterns...")
                
                for pattern in patterns:
                    await neo4j_conn._run_query("""
                        CREATE (p:AutomationPattern {
                            id: $id,
                            title: $title,
                            content: $content,
                            category: $category,
                            platform: $platform,
                            source_file: $source_file,
                            section: $section,
                            tags: $tags,
                            difficulty: $difficulty,
                            embedding: $embedding,
                            created_at: datetime($created_at)
                        })
                    """, pattern)
                
                # Create category relationships
                print("🔗 Creating category relationships...")
                await self.create_category_relationships(neo4j_conn)
                
                # Create similarity relationships
                print("🔗 Creating similarity relationships...")
                await self.create_similarity_relationships(neo4j_conn)
                
                print(" Successfully stored all patterns in Neo4j")
                return True
                
        except Exception as e:
            print(f" Neo4j storage error: {e}")
            return False
    
    async def create_category_relationships(self, neo4j_conn: Neo4jConnection):
        """
        Create relationships between patterns in the same category
        """
        await neo4j_conn._run_query("""
            MATCH (p1:AutomationPattern), (p2:AutomationPattern)
            WHERE p1.category = p2.category 
            AND p1.id <> p2.id
            CREATE (p1)-[:SAME_CATEGORY]->(p2)
        """)
    
    async def create_similarity_relationships(self, neo4j_conn: Neo4jConnection):
        """
        Create relationships between highly similar patterns
        """
        # This could be enhanced with vector similarity computation
        # For now, create relationships based on shared tags
        await neo4j_conn._run_query("""
            MATCH (p1:AutomationPattern), (p2:AutomationPattern)
            WHERE p1.id <> p2.id
            AND size([tag IN p1.tags WHERE tag IN p2.tags]) >= 2
            CREATE (p1)-[:SIMILAR_TO {shared_tags: size([tag IN p1.tags WHERE tag IN p2.tags])}]->(p2)
        """)
    
    async def cleanup(self):
        """
        Clean up temporary files
        """
        if self.repo_dir.exists():
            print(f"🧹 Cleaning up: {self.repo_dir}")
            shutil.rmtree(self.repo_dir)


# CLI interface for testing
async def main():
    """
    Run the ingestion pipeline
    """
    ingester = RedHatPracticesIngester()
    success = await ingester.run_full_ingestion()
    
    if success:
        print("\n🎯 Ingestion Summary:")
        print(" Repository cloned")
        print(" .adoc files processed") 
        print(" Embeddings generated")
        print(" Data stored in Neo4j")
        print(" Relationships created")
        print("\n🚀 Ready for agentic RAG queries!")
    else:
        print("\n Ingestion failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())
