from __future__ import annotations
import time, random
from typing import Iterable
from pai.core.errors import ProviderClientError, ProviderTransientError

class ResiliencePolicy:
    def __init__(self, max_retries=3, base_delay=0.5, max_delay=8.0, total_timeout=30.0,
                 retry_exceptions=(TimeoutError,)):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.total_timeout = total_timeout
        self.retry_exceptions = tuple(retry_exceptions)

    def compute_backoff(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * (2 ** (attempt - 1)) + random.random() * 0.1)

class ResilientProvider:
    def __init__(self, inner, policy: ResiliencePolicy):
        self.inner = inner
        self.policy = policy
        self.model = getattr(inner, "model", "unknown")

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, ProviderClientError):
            return False
        if isinstance(exc, ProviderTransientError):
            return True
        # Fallback on configured transient types (e.g., TimeoutError)
        return isinstance(exc, self.policy.retry_exceptions)

    def chat(self, messages):
        start = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            try:
                return self.inner.chat(messages)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if not self._should_retry(e) or attempt > self.policy.max_retries or (time.monotonic() - start) > self.policy.total_timeout:
                    raise RuntimeError(f"Provider call failed after retries: {e}") from e
                time.sleep(self.policy.compute_backoff(attempt))

    def chat_stream(self, messages) -> Iterable[str]:
        start = time.monotonic()
        attempt = 0
        yielded_any = False
        while True:
            attempt += 1
            try:
                for chunk in self.inner.chat_stream(messages):
                    yielded_any = True
                    yield chunk
                return
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Only retry before first chunk is yielded
                if yielded_any or not self._should_retry(e) or attempt > self.policy.max_retries or (time.monotonic() - start) > self.policy.total_timeout:
                    raise RuntimeError(f"Provider stream failed after retries: {e}") from e
                time.sleep(self.policy.compute_backoff(attempt))
