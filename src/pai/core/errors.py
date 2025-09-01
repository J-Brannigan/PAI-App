class ProviderError(Exception):
    """Base class for provider-level failures."""

class ProviderClientError(ProviderError):
    """
    Non-retryable: caller/config issue (4xx invalid request, auth, unknown model,
    unsupported parameter, etc.). The fix is change input/config, not retry.
    """

class ProviderTransientError(ProviderError):
    """
    Retryable: rate limits, timeouts, network hiccups, 5xx, etc.
    Retrying with backoff is appropriate.
    """
