"""Rate limiter and retry manager for the scraper package.

Provides a token-bucket rate limiter and a configurable retry manager
with circuit-breaker support.  These are reusable building blocks that
the ``Fetcher`` and ``BrowserTransport`` can use.

Phase 14-15: Rate limiter + retry manager.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token-bucket rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Token-bucket rate limiter.

    * ``rate`` — tokens per second (sustained throughput).
    * ``burst`` — maximum burst size (bucket capacity).
    * Tokens refill at ``rate`` per second; each request consumes 1 token.
    * If the bucket is empty, ``acquire()`` blocks until a token is available.

    Thread-safety: NOT thread-safe by design.  One ``RateLimiter`` per source
    scrape (concurrency of 1 per source).
    """

    def __init__(
        self,
        rate: float = 0.4,       # 1 request every 2.5 seconds
        burst: int = 1,
        cancel_event: Any = None,
    ) -> None:
        self.rate = max(rate, 0.01)  # floor to avoid divide-by-zero
        self.burst = max(burst, 1)
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()
        self._cancel_event = cancel_event

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> None:
        """Block until ``tokens`` are available.  Raises ``OperationCancelled``
        if the cancel event is set during the wait."""
        self._refill()
        while self._tokens < tokens:
            if self._cancel_event is not None and self._cancel_event.is_set():
                from .errors import OperationCancelled
                raise OperationCancelled()
            deficit = tokens - self._tokens
            wait = deficit / self.rate
            time.sleep(min(0.25, wait))
            self._refill()
        self._tokens -= tokens

    @property
    def available(self) -> float:
        """Number of tokens currently available (non-blocking)."""
        self._refill()
        return self._tokens


# ---------------------------------------------------------------------------
# Retry manager with circuit breaker
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    CLOSED = "closed"       # normal operation
    OPEN = "open"           # failing; reject requests immediately
    HALF_OPEN = "half_open" # testing recovery


@dataclass
class RetryConfig:
    """Configuration for the retry manager."""
    max_retries: int = 3
    base_delay: float = 2.5
    max_delay: float = 30.0
    jitter: float = 0.2          # ±20% jitter
    retry_after_weight: float = 1.5  # multiply Retry-After by this
    # Circuit breaker
    circuit_threshold: int = 5   # failures to trip the breaker
    circuit_reset_seconds: float = 60.0  # time before half-open
    # Retryable status codes
    retryable_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass
class RetryState:
    """Mutable state for the retry manager."""
    consecutive_failures: int = 0
    total_retries: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_opened_at: Optional[float] = None
    last_failure_at: Optional[float] = None
    retry_history: List[float] = field(default_factory=list)


class RetryManager:
    """Manages retries with exponential backoff and circuit breaker.

    Usage::

        rm = RetryManager(config=RetryConfig(max_retries=3))
        for attempt in range(1, config.max_retries + 2):
            try:
                result = do_request()
                rm.record_success()
                break
            except SomeError as exc:
                if not rm.should_retry(attempt, exc):
                    raise
                rm.wait_before_retry(attempt, exc)

    Circuit breaker states:

    * **CLOSED** — normal.  Failures increment the counter.
    * **OPEN** — after ``circuit_threshold`` consecutive failures, the circuit
      opens.  ``should_retry()`` returns ``False`` immediately.
    * **HALF_OPEN** — after ``circuit_reset_seconds``, the circuit allows
      one test request.  Success closes it; failure reopens it.
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        cancel_event: Any = None,
    ) -> None:
        self.config = config or RetryConfig()
        self.state = RetryState()
        self._cancel_event = cancel_event

    def record_success(self) -> None:
        """Record a successful request.  Resets the failure counter and
        closes the circuit breaker."""
        self.state.consecutive_failures = 0
        self.state.circuit_state = CircuitState.CLOSED
        self.state.circuit_opened_at = None

    def record_failure(self) -> None:
        """Record a failed request.  May trip the circuit breaker."""
        self.state.consecutive_failures += 1
        self.state.last_failure_at = time.monotonic()
        if self.state.consecutive_failures >= self.config.circuit_threshold:
            if self.state.circuit_state != CircuitState.OPEN:
                self.state.circuit_state = CircuitState.OPEN
                self.state.circuit_opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN after %d consecutive failures",
                    self.state.consecutive_failures,
                )

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        """Return ``True`` if we should retry after this failure.

        Checks circuit breaker state and retry count.
        """
        # Circuit breaker
        if self.state.circuit_state == CircuitState.OPEN:
            if self.state.circuit_opened_at is not None:
                elapsed = time.monotonic() - self.state.circuit_opened_at
                if elapsed >= self.config.circuit_reset_seconds:
                    self.state.circuit_state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker HALF_OPEN after %.1fs", elapsed)
                else:
                    return False
        # Retry count
        if attempt > self.config.max_retries:
            return False
        return True

    def wait_before_retry(
        self,
        attempt: int,
        exc: Exception,
        retry_after: Optional[float] = None,
    ) -> None:
        """Sleep with exponential backoff before the next retry attempt.

        Respects the cancel event for responsive cancellation.
        """
        cfg = self.config
        base = min(cfg.base_delay * (2 ** (attempt - 1)), cfg.max_delay)
        jitter = random.uniform(1 - cfg.jitter, 1 + cfg.jitter)
        delay = base * jitter

        if retry_after is not None and retry_after > 0:
            delay = max(delay, retry_after * cfg.retry_after_weight)

        self.state.retry_history.append(delay)
        self.state.total_retries += 1

        logger.debug(
            "Retry %d/%d in %.1fs: %s",
            attempt, cfg.max_retries, delay, exc,
        )

        deadline = time.monotonic() + delay
        while True:
            if self._cancel_event is not None and self._cancel_event.is_set():
                from .errors import OperationCancelled
                raise OperationCancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.25, remaining))

    def get_retry_after_from_headers(self, headers: dict) -> Optional[float]:
        """Extract Retry-After header as a float seconds value."""
        value = headers.get("retry-after") or headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None
