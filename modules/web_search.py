"""
web_search.py
--------------
Yerel "Project Knowledge" içinde yeterli veri bulunamadığında devreye
girer. Hangi sağlayıcının (Tavily / SerpAPI) kullanılacağı config.json
-> search.active_provider üzerinden seçilir. API anahtarları SADECE
st.secrets üzerinden okunur, koda asla yazılmaz.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class WebResult:
    title: str
    snippet: str
    url: str


class WebSearchClient:
    def __init__(self, provider: str, api_key: str | None, max_results: int = 5):
        self.provider = provider
        self.api_key = api_key
        self.max_results = max_results

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[WebResult]:
        if not self.is_configured():
            return []
        try:
            if self.provider == "tavily":
                return self._search_tavily(query)
            elif self.provider == "serpapi":
                return self._search_serpapi(query)
        except Exception as exc:  # Ağ hatası vb. -> sessizce boş dön, app.py kullanıcıya bildirir
            return [WebResult(title="Arama hatası", snippet=str(exc), url="")]
        return []

    # ------------------------------------------------------------------
    def _search_tavily(self, query: str) -> list[WebResult]:
        from tavily import TavilyClient
        client = TavilyClient(api_key=self.api_key)
        resp = client.search(query=query, max_results=self.max_results)
        results = []
        for item in resp.get("results", []):
            results.append(WebResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
            ))
        return results

    def _search_serpapi(self, query: str) -> list[WebResult]:
        from serpapi import GoogleSearch
        search = GoogleSearch({"q": query, "api_key": self.api_key, "num": self.max_results})
        data = search.get_dict()
        results = []
        for item in data.get("organic_results", [])[: self.max_results]:
            results.append(WebResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("link", ""),
            ))
        return results