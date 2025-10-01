"""
Multi-level rate limiting middleware with Redis backend.
Implements sliding window rate limiting for:
- Per IP address
- Per user ID
- Global (all requests)
"""
from typing import Optional, Tuple
import time
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from redis.asyncio import Redis

from app.config.settings import get_settings
from app.models.schemas import ErrorResponse

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """
    Custom exception for rate limit exceeded.
    """
    def __init__(self, retry_after: int, limit_type: str):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit_type}. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )
        self.retry_after = retry_after
        self.limit_type = limit_type


class RateLimiter:
    """
    Redis-based sliding window rate limiter.
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        self.settings = get_settings()
        self.redis_client = redis_client

    async def _get_redis(self) -> Redis:
        """
        Get or create Redis connection.
        """
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.settings.rate_limit_redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if rate limit is exceeded using sliding window algorithm.

        Args:
            key: Redis key (e.g., "rate_limit:ip:192.168.1.1")
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        try:
            redis_client = await self._get_redis()
            current_time = time.time()
            window_start = current_time - window_seconds

            # Use Redis sorted set with timestamps as scores
            pipe = redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request with timestamp
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration on the key
            pipe.expire(key, window_seconds)

            results = await pipe.execute()
            count = results[1]  # zcard result

            if count >= limit:
                # Rate limit exceeded
                # Calculate retry_after based on oldest entry in window
                oldest_timestamps = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_timestamps:
                    oldest_time = oldest_timestamps[0][1]
                    retry_after = int(oldest_time + window_seconds - current_time) + 1
                else:
                    retry_after = window_seconds

                logger.warning(
                    f"Rate limit exceeded for {key}: {count}/{limit} in {window_seconds}s"
                )
                return False, retry_after

            return True, 0

        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open: allow request if rate limiter fails
            return True, 0

    async def check_ip_rate_limit(self, ip: str) -> Tuple[bool, int]:
        """
        Check per-IP rate limit.
        """
        key = f"rate_limit:ip:{ip}"
        limit = self.settings.rate_limit_requests_per_minute_per_ip
        window = 60  # 1 minute
        return await self.check_rate_limit(key, limit, window)

    async def check_user_rate_limit(self, user_id: str) -> Tuple[bool, int]:
        """
        Check per-user rate limit.
        """
        key = f"rate_limit:user:{user_id}"
        limit = self.settings.rate_limit_requests_per_minute_per_user
        window = 60  # 1 minute
        return await self.check_rate_limit(key, limit, window)

    async def check_global_rate_limit(self) -> Tuple[bool, int]:
        """
        Check global rate limit (all requests).
        """
        key = "rate_limit:global"
        limit = self.settings.rate_limit_requests_per_hour_global
        window = 3600  # 1 hour
        return await self.check_rate_limit(key, limit, window)

    async def close(self):
        """
        Close Redis connection.
        """
        if self.redis_client:
            await self.redis_client.close()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for multi-level rate limiting.
    """

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.rate_limiter = RateLimiter()

    async def dispatch(self, request: Request, call_next):
        """
        Apply rate limiting checks before processing request.
        """
        # Skip rate limiting if disabled
        if not self.settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        try:
            # 1. Check global rate limit
            is_allowed, retry_after = await self.rate_limiter.check_global_rate_limit()
            if not is_allowed:
                raise RateLimitExceeded(retry_after, "global")

            # 2. Check IP rate limit
            client_ip = self._get_client_ip(request)
            is_allowed, retry_after = await self.rate_limiter.check_ip_rate_limit(client_ip)
            if not is_allowed:
                raise RateLimitExceeded(retry_after, f"IP {client_ip}")

            # 3. Check user rate limit (if user_id provided)
            user_id = self._get_user_id(request)
            if user_id:
                is_allowed, retry_after = await self.rate_limiter.check_user_rate_limit(user_id)
                if not is_allowed:
                    raise RateLimitExceeded(retry_after, f"user {user_id}")

            # All checks passed, process request
            response = await call_next(request)
            return response

        except RateLimitExceeded as e:
            error = ErrorResponse(
                error="rate_limit_exceeded",
                message=e.detail,
                request_id=str(request.state.request_id) if hasattr(request.state, "request_id") else None
            )

            return JSONResponse(
                status_code=e.status_code,
                content=error.dict(),
                headers=e.headers
            )

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        Handles X-Forwarded-For header for reverse proxies.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP if multiple (client IP)
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client
        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request.
        Can be from:
        - Authorization header (JWT token)
        - Request body (for POST requests)
        - Query parameter
        """
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Try to get from query parameter
        user_id = request.query_params.get("user_id")
        if user_id:
            return user_id

        # In production, extract from JWT token
        # auth_header = request.headers.get("Authorization")
        # if auth_header and auth_header.startswith("Bearer "):
        #     token = auth_header.split(" ")[1]
        #     user_id = decode_jwt_token(token)
        #     return user_id

        return None


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """
    Get global RateLimiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
