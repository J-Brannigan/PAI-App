from __future__ import annotations
import logging, time, random
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Optional, Tuple, Type

try:
    from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError
    OPENAI_ERRORS = (APIError, APIConnectionError, RateLimitError, APITimeoutError)
except Exception:
    OPENAI_ERRORS = tuple()

logger = logging.getLogger("pai.resilience")


@dataclass(frozen=True)
class ResiliencePolicy:
    max_retries: int = 3
    base_delay: float = 0.5      # seconds
    max_delay: float = 8.0       # cap per-sleep
    total_timeout: float = 30.0  # overall budget for all retries (seconds)
    retry_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
    # Extra exception classes to retry on (in addition to OpenAI ones above)
    retry_exceptions: Tuple[Type[BaseException], ...] = (TimeoutError,)

    # If True, log retry decisions at DEBUG
    debug_logging: bool = False


def _retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Best-effort extraction of Retry-After seconds from known SDK errors."""
    # OpenAI 1.x APIError has .response with headers, sometimes .status_code
    val = None
    headers = getattr(exc, "response", None)
    if headers and hasattr(headers, "headers"):
        ra = headers.headers.get("retry-after") or headers.headers.get("Retry-After")
        if ra:
            try:
                val = float(ra)
            except Exception:
                pass
    return val


class ResilientProvider:
    """
    Decorator that wraps any Provider-like object with retries, backoff, and neat errors.
    The wrapped object must implement:
        chat(messages: List[Dict[str, Any]]) -> Dict[str, str]
        chat_stream(messages: List[Dict[str, Any]]) -> Iterable[str]
    """
    def __init__(self, inner, policy: Optional[ResiliencePolicy] = None):
        self.inner = inner
        self.policy = policy or ResiliencePolicy()
        self.model = getattr(inner, "model", None)  # surface for logging

        # Build the retryable exception tuple once
        self._retryable_excs: Tuple[Type[BaseException], ...] = tuple(set(
            (self.policy.retry_exceptions or tuple()) + OPENAI_ERRORS  # type: ignore[operator]
        ))

    def _should_retry(self, exc: BaseException) -> bool:
        if isinstance(exc, self._retryable_excs):
            return True
        # Some SDK errors expose .status_code
        code = getattr(exc, "status_code", None)
        if isinstance(code, int) and code in self.policy.retry_status_codes:
            return True
        return False

    def _sleep_backoff(self, attempt: int, exc: Optional[BaseException]) -> None:
        retry_after = _retry_after_seconds(exc) if exc else None
        if retry_after is not None:
            delay = min(max(retry_after, 0.0), self.policy.max_delay)
        else:
            delay = min(self.policy.base_delay * (2 ** attempt) + random.uniform(0, 0.25),
                        self.policy.max_delay)
        if self.policy.debug_logging:
            logger.debug("retrying in %.2fs (attempt %d)", delay, attempt + 1)
        time.sleep(delay)

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        start = time.monotonic()
        attempt = 0
        while True:
            try:
                if self.policy.debug_logging:
                    logger.debug("chat call model=%s attempt=%d", self.model, attempt)
                return self.inner.chat(messages)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                elapsed = time.monotonic() - start
                if not self._should_retry(exc) or attempt >= self.policy.max_retries or elapsed >= self.policy.total_timeout:
                    # Final failure
                    msg = getattr(exc, "message", None) or str(exc)
                    raise RuntimeError(f"Provider failed after retries: {msg}") from exc
                if self.policy.debug_logging:
                    logger.debug("chat error: %r (elapsed=%.2fs) -> will retry", exc, elapsed)
                self._sleep_backoff(attempt, exc)
                attempt += 1

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        """
        Retry only if the stream fails before yielding any chunk. If it fails mid-stream,
        bubble up so the caller can persist the partial text and show a clear message.
        """
        policy = self.policy

        def gen():
            start = time.monotonic()
            attempt = 0
            yielded_any = False
            while True:
                try:
                    if policy.debug_logging:
                        logger.debug("chat_stream start model=%s attempt=%d", self.model, attempt)
                    for piece in self.inner.chat_stream(messages):
                        yielded_any = True
                        yield piece
                    return  # normal completion
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    elapsed = time.monotonic() - start
                    if yielded_any:
                        # mid-stream failure: do not restart the stream
                        msg = getattr(exc, "message", None) or str(exc)
                        raise RuntimeError(f"Provider stream failed mid-reply: {msg}") from exc
                    if (not self._should_retry(exc) or
                        attempt >= policy.max_retries or
                        elapsed >= policy.total_timeout):
                        msg = getattr(exc, "message", None) or str(exc)
                        raise RuntimeError(f"Provider stream failed after retries: {msg}") from exc
                    if policy.debug_logging:
                        logger.debug("chat_stream error before first chunk: %r -> retrying", exc)
                    self._sleep_backoff(attempt, exc)
                    attempt += 1

        return gen()
