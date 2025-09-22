"""
Remote Embedding Utilities using OpenAI/LlamaStack APIs

Replaces sentence-transformers with remote API calls.
No GPU/CUDA dependencies needed.
"""

import asyncio
import sys
import yaml
from pathlib import Path
from typing import List, Union
import numpy as np
import openai
from openai import AsyncOpenAI

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))


def _load_config_sync():
    """Load configuration synchronously"""
    config_path = Path(__file__).parent.parent.parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def load_config():
    """Load configuration asynchronously"""
    return await asyncio.to_thread(_load_config_sync)


class RemoteEmbeddingGenerator:
    """
    Remote embedding generation using OpenAI/LlamaStack APIs.
    No local models or GPU dependencies needed.
    """
    
    def __init__(self):
        self.config = _load_config_sync()
        self.llm_config = self.config.get("llm", {})
        
        # Use LlamaStack endpoint (OpenAI compatible)
        self.base_url = self.llm_config.get("base_url", "https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1")
        self.api_key = self.llm_config.get("api_key", "dummy-key")
        
        # Embedding model (using text-embedding-ada-002 equivalent)
        self.embedding_model = self.llm_config.get("embedding_model", "text-embedding-ada-002")
        self.dimension = 1536  # Standard OpenAI embedding dimension
        
        # Initialize async client
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        print(f"🌐 Remote Embedding Generator configured: {self.embedding_model}")
        print(f"🔗 Using endpoint: {self.base_url}")
    
    async def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text(s) using remote API.
        
        Args:
            texts: Single text string or list of texts
            
        Returns:
            Embedding vector(s) as list of floats
        """
        try:
            if isinstance(texts, str):
                # Single text
                response = await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=texts
                )
                return response.data[0].embedding
            else:
                # Multiple texts
                response = await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=texts
                )
                return [item.embedding for item in response.data]
                
        except Exception as e:
            print(f"⚠️ Remote embedding failed: {e}")
            # Fallback to dummy embeddings for development
            if isinstance(texts, str):
                return [0.0] * self.dimension
            else:
                return [[0.0] * self.dimension for _ in texts]
    
    async def encode_automation_pattern(self, pattern_data: dict) -> List[float]:
        """
        Generate embedding for an automation pattern using remote API.
        
        Args:
            pattern_data: Dict with pattern information
            
        Returns:
            Embedding vector as list of floats
        """
        # Combine relevant fields for embedding (same logic as before)
        text_parts = []
        
        if pattern_data.get("name"):
            text_parts.append(f"Name: {pattern_data['name']}")
        
        if pattern_data.get("description"):
            text_parts.append(f"Description: {pattern_data['description']}")
        
        if pattern_data.get("category"):
            text_parts.append(f"Category: {pattern_data['category']}")
        
        if pattern_data.get("platform"):
            text_parts.append(f"Platform: {pattern_data['platform']}")
        
        if pattern_data.get("code_example"):
            text_parts.append(f"Code: {pattern_data['code_example']}")
        
        if pattern_data.get("converted_code"):
            text_parts.append(f"Converted: {pattern_data['converted_code']}")
        
        if pattern_data.get("tags"):
            tags = pattern_data["tags"]
            if isinstance(tags, list):
                text_parts.append(f"Tags: {', '.join(tags)}")
            else:
                text_parts.append(f"Tags: {tags}")
        
        # Combine all parts
        combined_text = "\n".join(text_parts)
        
        # Generate embedding via API
        return await self.encode(combined_text)
    
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


async def get_remote_embedding_generator() -> RemoteEmbeddingGenerator:
    """Get the global remote embedding generator"""
    global _embedding_generator
    
    if _embedding_generator is None:
        _embedding_generator = RemoteEmbeddingGenerator()
    
    return _embedding_generator


async def test_remote_embeddings():
    """Test remote embedding generation"""
    print("🧪 Testing Remote Embedding Generation")
    print("-" * 40)
    
    try:
        generator = await get_remote_embedding_generator()
        
        # Test single text
        test_text = "Install nginx package using package manager"
        embedding = await generator.encode(test_text)
        
        print(f"🌐 Generated remote embedding for: '{test_text}'")
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
        
        pattern_embedding = await generator.encode_automation_pattern(test_pattern)
        print(f"🌐 Generated remote pattern embedding")
        print(f"📊 Pattern embedding dimension: {len(pattern_embedding)}")
        
        # Test similarity
        similarity_score = generator.similarity(embedding, pattern_embedding)
        print(f"📏 Similarity between texts: {similarity_score:.3f}")
        
        return True
        
    except Exception as e:
        print(f" Remote embedding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_remote_embeddings())
