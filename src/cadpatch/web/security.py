"""
Security enforcement, AST sanitization, and rate limiting for the Web API.
"""

from typing import Dict, Tuple
import time
from fastapi import Request, HTTPException, status
from ..sandbox.executor import static_security_check


class RateLimiter:
    """
    Sliding window rate limiter by client IP.
    """
    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # client_ip -> list of timestamps
        self.history: Dict[str, list] = {}

    def check(self, client_ip: str) -> Tuple[bool, int]:
        now = time.time()
        timestamps = self.history.get(client_ip, [])
        cutoff = now - self.window_seconds
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= self.max_requests:
            remaining = 0
            self.history[client_ip] = timestamps
            return False, remaining

        timestamps.append(now)
        self.history[client_ip] = timestamps
        remaining = self.max_requests - len(timestamps)
        return True, remaining


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def validate_script_security(code_str: str, max_bytes: int = 20480) -> None:
    if len(code_str.encode("utf-8")) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Script exceeds maximum allowed size of {max_bytes} bytes."
        )

    violation = static_security_check(code_str)
    if violation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Policy Violation: {violation}"
        )
