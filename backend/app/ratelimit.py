"""In-memory sliding-window rate limiter.

Each attempt is counted when it is allowed. A blocked attempt is not recorded,
so waiting out the window is enough to get through again. State lives in this
process only, which matches the single-process deployment; move it to a shared
store before running several workers.
"""
import threading
import time

from fastapi import Request

from app.config import get_settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str, max_events: int, window_seconds: int) -> int:
        """Record one attempt for `key`. Returns 0 if allowed, otherwise seconds to wait."""
        now = time.monotonic()
        with self._lock:
            recent = [t for t in self._events.get(key, []) if now - t < window_seconds]
            if len(recent) >= max_events:
                self._events[key] = recent
                return int(recent[0] + window_seconds - now) + 1
            recent.append(now)
            self._events[key] = recent
            return 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """The client's IP. X-Forwarded-For is trusted only when TRUST_PROXY_HEADERS is set.
    Then the last entry is used: the first one is whatever the client sent."""
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
