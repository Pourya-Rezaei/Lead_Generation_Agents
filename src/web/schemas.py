from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignForm:
    campaign_id: str
    name: str
    description: str | None = None

    @classmethod
    def from_form(cls, campaign_id: str, name: str, description: str = "") -> "CampaignForm":
        campaign_id = campaign_id.strip()
        name = " ".join(name.split())
        description = " ".join(description.split()) or None
        if not campaign_id:
            raise ValueError("Campaign ID is required.")
        if not name:
            raise ValueError("Campaign name is required.")
        return cls(campaign_id=campaign_id, name=name, description=description)
