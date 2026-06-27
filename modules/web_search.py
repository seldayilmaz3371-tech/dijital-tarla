"""
web_search.py
--------------
Yerel "Project Knowledge" içinde yeterli veri bulunamadığında devreye
girer. Hangi sağlayıcının (Tavily / SerpAPI) kullanılacağı config.json
-> search.active_provider üzerinden seçilir. API anahtarları SADECE
st.secrets üzerinden okunur, koda asla yazılmaz.

GÜNCELLEME: trusted_domains + İKİ KADEMELİ FALLBACK eklendi.
1) Önce config.json'daki güvenilir/resmi domainlerle SINIRLI arama yapılır.
2) Sonuç çıkmazsa (örn. o domain'de o konuda sayfa yoksa), filtre kaldırılıp
   sınırsız aramaya otomatik düşülür. Böylece hem öncelik güvenilir kaynakta
   olur hem de "hiç sonuç yok" durumu minimize edilir.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class WebResult:
    title: str
    snippet: str
    url: str


class WebSearchClient:
    def __init__(self, provider: str, api_key: str | None, max_results: int = 5,
                 trusted_domains: list[str] | None = None):
        self.provider = provider
        self.api_key = api_key
        self.max_results = max_results
        self.trusted_domains = trusted_domains or []

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[WebResult]:
        if not self.is_configured():
            return []
        try:
            if self.provider == "tavily":
                results = self._search_tavily(query, use_trusted_domains=True)
                # İKİ KADEMELİ FALLBACK: güvenilir domainlerde hiç sonuç
                # çıkmazsa, filtreyi kaldırıp sınırsız aramaya düşüyoruz.
                if not results and self.trusted_domains:
                    results = self._search_tavily(query, use_trusted_domains=False)
                return results
            elif self.provider == "serpapi":
                results = self._search_serpapi(query, use_trusted_domains=True)
                if not results and self.trusted_domains:
                    results = self._search_serpapi(query, use_trusted_domains=False)
                return results
        except Exception as exc:  # Ağ hatası vb. -> sessizce boş dön, app.py kullanıcıya bildirir
            return [WebResult(title="Arama hatası", snippet=str(exc), url="")]
        return []

    # ------------------------------------------------------------------
    def _search_tavily(self, query: str, use_trusted_domains: bool = True) -> list[WebResult]:
        from tavily import TavilyClient
        client = TavilyClient(api_key=self.api_key)
        search_kwargs = {"query": query, "max_results": self.max_results}
        if use_trusted_domains and self.trusted_domains:
            search_kwargs["include_domains"] = self.trusted_domains
        resp = client.search(**search_kwargs)
        results = []
        for item in resp.get("results", []):
            results.append(WebResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
            ))
        return results

    def _search_serpapi(self, query: str, use_trusted_domains: bool = True) -> list[WebResult]:
        from serpapi import GoogleSearch
        search_query = query
        if use_trusted_domains and self.trusted_domains:
            # SerpAPI'de (Google) doğrudan include_domains parametresi yok;
            # "site:" operatörlerini sorguya ekleyerek aynı etkiyi sağlıyoruz.
            site_filter = " OR ".join(f"site:{d}" for d in self.trusted_domains)
            search_query = f"({site_filter}) {query}"
        search = GoogleSearch({"q": search_query, "api_key": self.api_key, "num": self.max_results})
        data = search.get_dict()
        results = []
        for item in data.get("organic_results", [])[: self.max_results]:
            results.append(WebResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("link", ""),
            ))
        return results