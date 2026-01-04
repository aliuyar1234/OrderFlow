"""Rate limiting for authentication endpoints.

Implements sliding window rate limiting to prevent brute force attacks.
Uses Redis for distributed rate limiting across multiple API instances.

SSOT Reference: §8.4 (Security Controls)
"""

import os
import time
import hashlib
from typing import Optional
from functools import wraps

from fastapi import HTTPException, Request, status
from redis import Redis

# Rate limit configuration
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "900"))  # 15 minutes
RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("RATE_LIMIT_MAX_ATTEMPTS", "5"))  # 5 attempts per window
LOCKOUT_DURATION_SECONDS = int(os.getenv("LOCKOUT_DURATION", "1800"))  # 30 minutes lockout
LOCKOUT_THRESHOLD = int(os.getenv("LOCKOUT_THRESHOLD", "10"))  # Lock after 10 failed attempts

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_client() -> Optional[Redis]:
    """Get Redis client for rate limiting.

    Returns None if Redis is not available, allowing graceful degradation.
    """
    try:
        client = Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _get_client_identifier(request: Request) -> str:
    """Extract a unique identifier for the client.

    Uses a combination of IP address and User-Agent to create a fingerprint.
    Falls back to IP only if User-Agent is missing.
    """
    # Get IP address (handle proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = "unknown"

    # Add user agent for additional fingerprinting
    user_agent = request.headers.get("User-Agent", "")

    # Create hash for privacy
    fingerprint = f"{ip}:{user_agent}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]


def _get_rate_limit_key(identifier: str, endpoint: str) -> str:
    """Generate Redis key for rate limiting."""
    return f"rate_limit:{endpoint}:{identifier}"


def _get_lockout_key(identifier: str) -> str:
    """Generate Redis key for account lockout."""
    return f"lockout:{identifier}"


def _get_failed_attempts_key(email: str, org_slug: str) -> str:
    """Generate Redis key for failed login attempts per account."""
    account_key = f"{org_slug}:{email}"
    return f"failed_attempts:{hashlib.sha256(account_key.encode()).hexdigest()[:32]}"


class RateLimiter:
    """Rate limiter using Redis sliding window algorithm."""

    def __init__(self):
        self.redis = get_redis_client()

    def is_rate_limited(self, request: Request, endpoint: str = "auth") -> bool:
        """Check if client is rate limited.

        Args:
            request: FastAPI request object
            endpoint: Endpoint identifier for rate limiting

        Returns:
            True if client should be rate limited
        """
        if not self.redis:
            # Graceful degradation: no rate limiting if Redis unavailable
            return False

        identifier = _get_client_identifier(request)
        key = _get_rate_limit_key(identifier, endpoint)

        # Check current count in sliding window
        current_time = int(time.time())
        window_start = current_time - RATE_LIMIT_WINDOW_SECONDS

        # Remove old entries outside window
        self.redis.zremrangebyscore(key, 0, window_start)

        # Count requests in current window
        current_count = self.redis.zcard(key)

        return current_count >= RATE_LIMIT_MAX_ATTEMPTS

    def record_attempt(self, request: Request, endpoint: str = "auth") -> int:
        """Record an authentication attempt.

        Args:
            request: FastAPI request object
            endpoint: Endpoint identifier

        Returns:
            Number of attempts in current window
        """
        if not self.redis:
            return 0

        identifier = _get_client_identifier(request)
        key = _get_rate_limit_key(identifier, endpoint)

        current_time = int(time.time())

        # Add current attempt
        self.redis.zadd(key, {str(current_time): current_time})

        # Set expiry on key
        self.redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)

        # Return current count
        return self.redis.zcard(key)

    def is_locked_out(self, request: Request) -> bool:
        """Check if client IP is locked out.

        Args:
            request: FastAPI request object

        Returns:
            True if client is locked out
        """
        if not self.redis:
            return False

        identifier = _get_client_identifier(request)
        key = _get_lockout_key(identifier)

        return self.redis.exists(key) > 0

    def get_lockout_remaining(self, request: Request) -> int:
        """Get remaining lockout time in seconds.

        Args:
            request: FastAPI request object

        Returns:
            Seconds remaining in lockout, or 0 if not locked out
        """
        if not self.redis:
            return 0

        identifier = _get_client_identifier(request)
        key = _get_lockout_key(identifier)

        ttl = self.redis.ttl(key)
        return max(0, ttl)

    def record_failed_login(self, email: str, org_slug: str, request: Request) -> bool:
        """Record a failed login attempt for an account.

        Args:
            email: User email
            org_slug: Organization slug
            request: FastAPI request object

        Returns:
            True if account is now locked out
        """
        if not self.redis:
            return False

        identifier = _get_client_identifier(request)
        account_key = _get_failed_attempts_key(email, org_slug)

        # Increment failed attempts
        attempts = self.redis.incr(account_key)
        self.redis.expire(account_key, RATE_LIMIT_WINDOW_SECONDS)

        # Check if we should lock out
        if attempts >= LOCKOUT_THRESHOLD:
            lockout_key = _get_lockout_key(identifier)
            self.redis.setex(lockout_key, LOCKOUT_DURATION_SECONDS, "1")
            return True

        return False

    def clear_failed_attempts(self, email: str, org_slug: str) -> None:
        """Clear failed login attempts after successful login.

        Args:
            email: User email
            org_slug: Organization slug
        """
        if not self.redis:
            return

        account_key = _get_failed_attempts_key(email, org_slug)
        self.redis.delete(account_key)

    def get_attempts_remaining(self, request: Request, endpoint: str = "auth") -> int:
        """Get remaining attempts before rate limit.

        Args:
            request: FastAPI request object
            endpoint: Endpoint identifier

        Returns:
            Number of attempts remaining
        """
        if not self.redis:
            return RATE_LIMIT_MAX_ATTEMPTS

        identifier = _get_client_identifier(request)
        key = _get_rate_limit_key(identifier, endpoint)

        current_count = self.redis.zcard(key)
        return max(0, RATE_LIMIT_MAX_ATTEMPTS - current_count)


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit(request: Request) -> None:
    """Check rate limit and raise exception if exceeded.

    Use as a dependency in FastAPI endpoints:

        @router.post("/login")
        async def login(
            request: Request,
            _: None = Depends(check_rate_limit)
        ):
            ...
    """
    # Check lockout first
    if rate_limiter.is_locked_out(request):
        remaining = rate_limiter.get_lockout_remaining(request)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Account locked for {remaining} seconds.",
            headers={"Retry-After": str(remaining)}
        )

    # Check rate limit
    if rate_limiter.is_rate_limited(request, "auth"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait before trying again.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)}
        )

    # Record attempt
    rate_limiter.record_attempt(request, "auth")
