"""Safe, user-facing errors for external lead providers."""


class ApifyError(RuntimeError):
    """Base error for Apify API failures."""


class ApifyCredentialError(ApifyError):
    """Authentication or authorization failed."""


class ApifyNotFoundError(ApifyError):
    """An Actor, dataset, or endpoint was not found."""


class ApifyTransientError(ApifyError):
    """A retryable Apify or network failure exhausted its retries."""


class ApifyMalformedResponseError(ApifyError):
    """Apify returned JSON with an unexpected shape."""
