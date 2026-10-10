"""Safe, user-facing errors for external lead providers."""


class CampaignError(ValueError):
    """Base error for invalid or unavailable campaign operations."""


class CampaignNotFoundError(CampaignError):
    """A requested campaign does not exist."""


class DuplicateCampaignNameError(CampaignError):
    """A campaign name is already in use."""


class DuplicateCampaignIdError(CampaignError):
    """A campaign ID is already in use."""


class ApifyError(RuntimeError):
    """Base error for Apify API failures."""


class ApifyCredentialError(ApifyError):
    """Authentication or authorization failed."""


class ApifyNotFoundError(ApifyError):
    """An Actor, dataset, or endpoint was not found."""


class ApifyTransientError(ApifyError):
    """A retryable Apify or network failure exhausted its retries."""


class ApifyStartOutcomeUnknown(ApifyError):
    """An Actor start may have been accepted, but no usable run ID was received."""


class ProviderAbortOutcomeUnknown(ApifyError):
    """A provider run abort may have been accepted, but completion is unknown."""


class ApifyMalformedResponseError(ApifyError):
    """Apify returned JSON with an unexpected shape."""


class SearchAttemptPersistenceError(RuntimeError):
    """A failed search could not be recorded in the local database."""
