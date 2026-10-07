import httpx
from .base import Connector
from ..domain import Lead, normalize, score

class GoogleSearchConnector(Connector):
    endpoint = "https://www.google.com/search"
    def __init__(self, timeout: float = 20): self.timeout = timeout
    def search(self, query: str, location: str, limit: int = 20) -> list[Lead]:
        response = httpx.get(self.endpoint, params={"q": f"{query} {location}"}, headers={"User-Agent": "leadgen/0.1"}, timeout=self.timeout, trust_env=False)
        response.raise_for_status()
        import re, html
        leads = []
        for match in re.finditer(r'<a href="([^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>', response.text, re.S):
            if len(leads) >= limit: break
            title = re.sub(r"<[^>]+>", "", match.group(2))
            lead = normalize(Lead(name=html.unescape(title).strip(), website=match.group(1), category=query, source="google_search"))
            leads.append(lead.model_copy(update={"score": score(lead)}))
        return leads
