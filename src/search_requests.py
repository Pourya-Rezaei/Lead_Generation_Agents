"""Source-specific requests, validated before provider execution."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlacesSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["places"] = "places"
    query: str = Field(min_length=1)
    location: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("query", "location")
    @classmethod
    def clean(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("query and location must not be empty")
        return value


class InstagramSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["instagram"] = "instagram"
    search: str = Field(min_length=1)
    searchLimit: int = Field(default=10, ge=1, le=250, strict=True)

    @field_validator("search")
    @classmethod
    def clean(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or any(separator in value for separator in (",", "،", "，")):
            raise ValueError("Instagram requires one non-empty search phrase; comma-separated terms are not supported")
        return value

    def actor_input(self) -> dict:
        return {"search": self.search, "searchLimit": self.searchLimit, "searchType": "user", "liveSearch": False, "enhanceUserSearchWithFacebookPage": False}


def validate_job_request(request: dict) -> dict:
    if request.get("operation") not in (None, "search") or request.get("sources") is not None:
        raise ValueError("unsupported_source: only single-source search jobs are supported")
    source = request.get("source", "places")
    operational = {"campaign_id", "idempotency_key", "force_refresh", "estimated_cost", "max_cost", "currency", "provider_run_id", "operation", "provider_run_ids", "pricing_version"}
    payload = {key: value for key, value in request.items() if key not in operational and not key.startswith("_")}
    if source == "instagram":
        validated = InstagramSearchRequest.model_validate(payload)
    elif source == "places":
        validated = PlacesSearchRequest.model_validate(payload)
    else:
        raise ValueError("unsupported_source: selected source is historical and cannot execute")
    return {**request, **validated.model_dump()}
