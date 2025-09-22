"""
Embedding Utilities for Neo4j Vector Search

Handles local embedding generation using sentence-transformers.
All configuration comes from config.yaml.
"""

import asyncio
import sys
import yaml
from pathlib import Path
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))


def _load_config_sync():
    """Load configuration synchronously (for thread execution)"""
    config_path = Path(__file__).parent.parent.parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def load_config():
    """Load configuration asynchronously to avoid blocking"""
    return await asyncio.to_thread(_load_config_sync)


class EmbeddingGenerator:
    """
    Local embedding generation using sentence-transformers.
    Configured via config.yaml, no hardcoded values.
    """
    
    def __init__(self):
        # Use sync version for initialization
        self.config = _load_config_sync()
        self.embedding_config = self.config.get("embedding", {})
        
        self.model_name = self.embedding_config.get("model", "all-MiniLM-L6-v2")
        self.dimension = self.embedding_config.get("dimension", 384)
        self.device = self.embedding_config.get("device", "cpu")
        
        self._model = None
        print(f"🤖 Embedding Generator configured: {self.model_name} ({self.dimension}d)")
    
    @classmethod
    async def create_async(cls):
        """Create EmbeddingGenerator with async config loading"""
        config = await load_config()
        instance = cls.__new__(cls)
        instance.config = config
        instance.embedding_config = config.get("embedding", {})
        
        instance.model_name = instance.embedding_config.get("model", "all-MiniLM-L6-v2")
        instance.dimension = instance.embedding_config.get("dimension", 384)
        instance.device = instance.embedding_config.get("device", "cpu")
        
        instance._model = None
        print(f"🤖 Embedding Generator configured: {instance.model_name} ({instance.dimension}d)")
        return instance
    
    @property
    def model(self):
        """Lazy loading of the embedding model"""
        if self._model is None:
            print(f"📥 Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            print(f" Model loaded on device: {self.device}")
        
        return self._model
    
    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text(s).
        
        Args:
            texts: Single text string or list of texts
            
        Returns:
            Embedding vector(s) as list of floats
        """
        if isinstance(texts, str):
            # Single text
            embedding = self.model.encode(texts, convert_to_numpy=True)
            return embedding.tolist()
        else:
            # Multiple texts
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
    
    def encode_automation_pattern(self, pattern_data: dict) -> List[float]:
        """
        Generate embedding for an automation pattern.
        Combines multiple fields for richer semantic representation.
        
        Args:
            pattern_data: Dict with pattern information
            
        Returns:
            Embedding vector as list of floats
        """
        # Combine relevant fields for embedding
        text_parts = []
        
        # Add name/title
        if pattern_data.get("name"):
            text_parts.append(f"Name: {pattern_data['name']}")
        
        # Add description
        if pattern_data.get("description"):
            text_parts.append(f"Description: {pattern_data['description']}")
        
        # Add category context
        if pattern_data.get("category"):
            text_parts.append(f"Category: {pattern_data['category']}")
        
        # Add platform context
        if pattern_data.get("platform"):
            text_parts.append(f"Platform: {pattern_data['platform']}")
        
        # Add code examples
        if pattern_data.get("code_example"):
            text_parts.append(f"Code: {pattern_data['code_example']}")
        
        # Add converted code if available
        if pattern_data.get("converted_code"):
            text_parts.append(f"Converted: {pattern_data['converted_code']}")
        
        # Add keywords/tags
        if pattern_data.get("tags"):
            tags = pattern_data["tags"]
            if isinstance(tags, list):
                text_parts.append(f"Tags: {', '.join(tags)}")
            else:
                text_parts.append(f"Tags: {tags}")
        
        # Combine all parts
        combined_text = "\n".join(text_parts)
        
        # Generate embedding
        return self.encode(combined_text)
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, (similarity + 1) / 2))


# Global embedding generator instance
_embedding_generator = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator (sync version)"""
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    
    return _embedding_generator


async def get_embedding_generator_async() -> EmbeddingGenerator:
    """Get the global embedding generator (async version)"""
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = await EmbeddingGenerator.create_async()
    
    return _embedding_generator


def test_embeddings():
    """Test embedding generation"""
    print("🧪 Testing Embedding Generation")
    print("-" * 40)
    
    try:
        generator = get_embedding_generator()
        
        # Test single text
        test_text = "Install nginx package using package manager"
        embedding = generator.encode(test_text)
        
        print(f" Generated embedding for: '{test_text}'")
        print(f"📊 Embedding dimension: {len(embedding)}")
        print(f"📋 First 5 values: {embedding[:5]}")
        
        # Test automation pattern
        test_pattern = {
            "name": "Chef Package Resource",
            "description": "Install packages using Chef package resource",
            "category": "package_management",
            "platform": "chef",
            "code_example": "package 'nginx' do\n  action :install\nend",
            "tags": ["chef", "package", "installation"]
        }
        
        pattern_embedding = generator.encode_automation_pattern(test_pattern)
        print(f" Generated pattern embedding")
        print(f"📊 Pattern embedding dimension: {len(pattern_embedding)}")
        
        # Test similarity
        similarity_score = generator.similarity(embedding, pattern_embedding)
        print(f"📏 Similarity between texts: {similarity_score:.3f}")
        
        return True
        
    except Exception as e:
        print(f" Embedding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_embeddings()
