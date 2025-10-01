"""
Semantic caching service to reduce LLM costs and latency.
Uses embeddings to match similar queries and return cached responses.
"""
from typing import Optional, Tuple
import logging
import json
import hashlib
from datetime import datetime
import redis.asyncio as redis
from redis.asyncio import Redis
from openai import OpenAI

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    Semantic cache using embeddings for similarity matching.
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        openai_client: Optional[OpenAI] = None
    ):
        self.settings = get_settings()
        self.redis_client = redis_client
        self.openai_client = openai_client or OpenAI(api_key=self.settings.openai_api_key)

    async def _get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.settings.cache_redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis_client

    def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",  # Cost-effective embedding model
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _create_cache_key(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """
        Create cache key from messages and parameters.
        For exact matching, we hash the entire input.
        """
        key_data = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ) -> Optional[Tuple[str, dict]]:
        """
        Get cached response if available.

        Returns:
            Tuple of (response_content, metadata) if cache hit, None otherwise
        """
        if not self.settings.cache_enabled:
            return None

        try:
            redis_client = await self._get_redis()

            # Strategy 1: Exact match using hash
            cache_key = self._create_cache_key(messages, temperature, max_tokens)
            exact_match = await redis_client.get(f"cache:exact:{cache_key}")

            if exact_match:
                logger.info(f"Cache hit (exact): {cache_key[:16]}")
                data = json.loads(exact_match)
                return data["response"], data["metadata"]

            # Strategy 2: Semantic similarity search
            # For semantic search, we'll use the last user message
            last_user_msg = next(
                (msg["content"] for msg in reversed(messages) if msg["role"] == "user"),
                None
            )

            if not last_user_msg:
                return None

            # Get embedding for current query
            query_embedding = self._get_embedding(last_user_msg)
            if not query_embedding:
                return None

            # Search for similar cached queries
            # In production, use a vector database (Pinecone, Weaviate, etc.)
            # For this implementation, we'll use a simplified approach with Redis

            # Get all cached queries (limited scan)
            cursor = 0
            best_match = None
            best_similarity = 0.0

            # Scan cached embeddings
            while True:
                cursor, keys = await redis_client.scan(
                    cursor,
                    match="cache:semantic:*",
                    count=100
                )

                for key in keys:
                    cached_data = await redis_client.get(key)
                    if not cached_data:
                        continue

                    try:
                        cache_entry = json.loads(cached_data)
                        cached_embedding = cache_entry.get("embedding")

                        if not cached_embedding:
                            continue

                        # Calculate similarity
                        similarity = self._cosine_similarity(query_embedding, cached_embedding)

                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = cache_entry

                    except Exception as e:
                        logger.debug(f"Error processing cache entry: {e}")
                        continue

                if cursor == 0:
                    break

            # Check if best match exceeds threshold
            if best_match and best_similarity >= self.settings.cache_similarity_threshold:
                logger.info(
                    f"Cache hit (semantic): similarity={best_similarity:.3f}, "
                    f"threshold={self.settings.cache_similarity_threshold}"
                )
                return best_match["response"], best_match["metadata"]

            logger.debug(f"Cache miss: best_similarity={best_similarity:.3f}")
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response: str,
        metadata: dict
    ):
        """
        Store response in cache.

        Args:
            messages: Input messages
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            response: LLM response
            metadata: Response metadata (tokens, cost, etc.)
        """
        if not self.settings.cache_enabled:
            return

        try:
            redis_client = await self._get_redis()

            # Store exact match
            cache_key = self._create_cache_key(messages, temperature, max_tokens)
            cache_data = {
                "response": response,
                "metadata": metadata,
                "timestamp": datetime.utcnow().isoformat()
            }

            await redis_client.set(
                f"cache:exact:{cache_key}",
                json.dumps(cache_data),
                ex=self.settings.cache_ttl_seconds
            )

            # Store for semantic search
            last_user_msg = next(
                (msg["content"] for msg in reversed(messages) if msg["role"] == "user"),
                None
            )

            if last_user_msg:
                query_embedding = self._get_embedding(last_user_msg)

                if query_embedding:
                    semantic_data = {
                        **cache_data,
                        "embedding": query_embedding,
                        "query": last_user_msg
                    }

                    await redis_client.set(
                        f"cache:semantic:{cache_key}",
                        json.dumps(semantic_data),
                        ex=self.settings.cache_ttl_seconds
                    )

            logger.info(f"Cached response: {cache_key[:16]}")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def clear(self):
        """
        Clear all cache entries.
        """
        try:
            redis_client = await self._get_redis()

            # Delete all cache keys
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match="cache:*", count=1000)
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break

            logger.info("Cache cleared")

        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    async def get_stats(self) -> dict:
        """
        Get cache statistics.
        """
        try:
            redis_client = await self._get_redis()

            # Count cache entries
            exact_count = 0
            semantic_count = 0

            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match="cache:*", count=1000)
                for key in keys:
                    if key.startswith("cache:exact:"):
                        exact_count += 1
                    elif key.startswith("cache:semantic:"):
                        semantic_count += 1
                if cursor == 0:
                    break

            return {
                "exact_entries": exact_count,
                "semantic_entries": semantic_count,
                "total_entries": exact_count + semantic_count,
                "ttl_seconds": self.settings.cache_ttl_seconds,
                "similarity_threshold": self.settings.cache_similarity_threshold
            }

        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
_semantic_cache: Optional[SemanticCache] = None


async def get_semantic_cache() -> SemanticCache:
    """Get global SemanticCache instance."""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
