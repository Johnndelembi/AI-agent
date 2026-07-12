"""Internal TanzLII retrieval, parsing, and caching services for the legal agent."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import LEGAL_CACHE_TTL_HOURS, LEGAL_SEARCH_RESULTS_LIMIT, TANZLII_BASE_URL, logger
from app.models.legal import LegalDocument
from app.services.browser_fetch_service import BrowserFetchService


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

COLLECTION_SEARCH_PATHS = {
    "judgments": "/en/search/?q={query}&nature=Judgment",
    "legislation": "/en/search/?q={query}",
    "gazettes": "/en/search/?q={query}&nature=Gazette",
    "secondary_sources": "/en/search/?q={query}",
    "practice_essentials": "/en/search/?q={query}",
    "regional_law": "/en/search/?q={query}",
}


class TanzLIIService:
    """Fetches and caches TanzLII legal materials."""

    def __init__(self, base_url: str = TANZLII_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.cache_ttl_hours = LEGAL_CACHE_TTL_HOURS
        self.default_limit = LEGAL_SEARCH_RESULTS_LIMIT
        self.browser_fetcher = BrowserFetchService()

    def search(
        self,
        query: str,
        collection: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search TanzLII by collection and cache result metadata."""
        if collection not in COLLECTION_SEARCH_PATHS:
            raise ValueError(f"Unsupported TanzLII collection: {collection}")

        limit = max(1, min(limit or self.default_limit, 10))
        search_path = COLLECTION_SEARCH_PATHS[collection].format(query=quote_plus(query.strip()))
        url = f"{self.base_url}{search_path}"

        try:
            response_text = self._get_text(url)
            results = self._parse_search_results(response_text, collection=collection, limit=limit)
        except Exception as exc:
            logger.warning("Live TanzLII search failed for %s: %s", collection, exc)
            results = [doc.to_source_dict() for doc in LegalDocument.find_cached(query, collection=collection, limit=limit)]
            for item in results:
                item["cached_only"] = True
            return results

        cached_results = []
        for item in results:
            cached = LegalDocument.upsert_source(
                normalized_url=item["normalized_url"],
                defaults={
                    "source_url": item["url"],
                    "normalized_url": item["normalized_url"],
                    "source_type": "tanzlii",
                    "collection": item["collection"],
                    "title": item["title"],
                    "citation": item.get("citation"),
                    "court": item.get("court"),
                    "nature": item.get("nature"),
                    "year": item.get("year"),
                    "document_date": item.get("document_date"),
                    "expression_date": item.get("expression_date"),
                    "summary": item.get("summary"),
                    "metadata": {
                        "query": query,
                        "search_collection": collection,
                    },
                },
            )
            cached_results.append(cached.to_source_dict())
        return cached_results

    def research(self, question: str, limit_per_collection: int = 3) -> Dict[str, Any]:
        """Run a multi-collection TanzLII-first research pass for a legal question."""
        collections = self._infer_collections(question)
        sources: List[Dict[str, Any]] = []

        for collection in collections:
            for result in self.search(question, collection=collection, limit=limit_per_collection):
                result["requested_collection"] = collection
                sources.append(result)

        deduped = self._dedupe_sources(sources)[: max(limit_per_collection * len(collections), 6)]
        enriched_sources = []
        for result in deduped[:4]:
            doc = self.fetch_document(result["url"], prefer_cache=True)
            if doc:
                result["document_excerpt"] = doc.get("excerpt")
                result["document_fetch_status"] = doc.get("fetch_status")
            enriched_sources.append(result)

        return {
            "question": question,
            "collections": collections,
            "sources": enriched_sources or deduped,
        }

    def fetch_document(self, url: str, prefer_cache: bool = True) -> Dict[str, Any]:
        """Fetch a TanzLII document page and cache the text when available."""
        absolute_url = self._absolute_url(url)
        normalized_url = self._normalize_url(absolute_url)

        cached = LegalDocument.objects(normalized_url=normalized_url).first()
        if prefer_cache and cached and self._is_cache_fresh(cached):
            return self._document_payload(cached, fetch_status="cached")

        try:
            response_text = self._get_text(absolute_url)
            title, text_content, summary, source_links = self._parse_document(response_text, absolute_url)
            collection = self._infer_collection_from_url(absolute_url)
            document_date, expression_date, year, court, nature = self._extract_metadata_from_url(absolute_url)

            cached = LegalDocument.upsert_source(
                normalized_url=normalized_url,
                defaults={
                    "source_url": absolute_url,
                    "normalized_url": normalized_url,
                    "source_type": "tanzlii",
                    "collection": collection,
                    "title": title,
                    "court": court,
                    "nature": nature,
                    "year": year,
                    "document_date": document_date,
                    "expression_date": expression_date,
                    "text_content": text_content,
                    "summary": summary,
                    "source_links": source_links,
                    "section_chunks": self._chunk_text(text_content),
                    "fetch_error": None,
                    "metadata": {
                        "retrieved_from_live_source": True,
                    },
                },
            )
            return self._document_payload(cached, fetch_status="live")
        except Exception as exc:
            logger.warning("TanzLII document fetch failed for %s: %s", absolute_url, exc)
            if cached:
                cached.fetch_error = str(exc)
                cached.save()
                return self._document_payload(cached, fetch_status="cached_after_error", warning=str(exc))
            return {
                "url": absolute_url,
                "fetch_status": "unavailable",
                "warning": str(exc),
            }

    def sync_collection(self, collection: str, seed_query: str, limit: int = 5) -> Dict[str, Any]:
        """Prime the local cache for a collection through the existing TanzLII search UI."""
        results = self.search(seed_query, collection=collection, limit=limit)
        fetched = 0
        failures = 0
        for result in results:
            payload = self.fetch_document(result["url"], prefer_cache=False)
            if payload.get("fetch_status") in {"live", "cached", "cached_after_error"}:
                fetched += 1
            else:
                failures += 1
        return {
            "collection": collection,
            "seed_query": seed_query,
            "discovered": len(results),
            "fetched": fetched,
            "failures": failures,
        }

    def warm_cache_recent(self, per_collection: int = 3) -> Dict[str, Any]:
        """Warm the cache with recent judgments, legislation, and gazettes from TanzLII."""
        per_collection = max(1, min(per_collection, 10))
        targets = {
            "judgments": [],
            "legislation": [],
            "gazettes": [],
        }
        seen = {key: set() for key in targets}
        discovery_pages = [
            f"{self.base_url}/en/",
            f"{self.base_url}/en/legislation/",
            f"{self.base_url}/en/gazettes/",
        ]

        for page_url in discovery_pages:
            try:
                html = self._get_text(page_url)
            except Exception as exc:
                logger.warning("Warm-cache discovery fetch failed for %s: %s", page_url, exc)
                continue

            for collection in targets:
                if len(targets[collection]) >= per_collection:
                    continue
                discovered = self._parse_search_results(
                    html,
                    collection=collection,
                    limit=per_collection * 3,
                )
                for item in discovered:
                    url = item["url"]
                    if url in seen[collection]:
                        continue
                    seen[collection].add(url)
                    targets[collection].append(item)
                    if len(targets[collection]) >= per_collection:
                        break

        stats = {
            "collections": {},
            "total_discovered": sum(len(items) for items in targets.values()),
            "total_fetched": 0,
            "total_failures": 0,
        }
        for collection, items in targets.items():
            fetched = 0
            failures = 0
            for item in items[:per_collection]:
                payload = self.fetch_document(item["url"], prefer_cache=False)
                if payload.get("fetch_status") in {"live", "cached", "cached_after_error"}:
                    fetched += 1
                else:
                    failures += 1

            stats["collections"][collection] = {
                "discovered": len(items[:per_collection]),
                "fetched": fetched,
                "failures": failures,
            }
            stats["total_fetched"] += fetched
            stats["total_failures"] += failures

        return stats

    def _get_text(self, url: str) -> str:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True) as client:
            try:
                response = client.get(url)
                response.raise_for_status()
                if self._is_cloudflare_challenge(response.text):
                    raise RuntimeError("TanzLII returned a Cloudflare challenge instead of legal content")
                return response.text
            except Exception as exc:
                logger.info("Plain HTTP TanzLII fetch failed for %s, trying browser fallback: %s", url, exc)

        browser_result = self.browser_fetcher.fetch_html(url)
        if self._is_cloudflare_challenge(browser_result.html):
            raise RuntimeError(
                f"Browser fetch still received a challenge page via {browser_result.mode}"
            )
        return browser_result.html

    def _parse_search_results(
        self,
        html: str,
        collection: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select('main a[href^="/en/akn/"], main a[href^="/en/doc/"], main a[href^="/en/articles/"], main a[href^="/en/journals/"], main a[href^="/en/law-reports/"]')

        results: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for anchor in anchors:
            href = anchor.get("href")
            title = self._clean_text(anchor.get_text(" ", strip=True))
            if not href or not title:
                continue

            absolute_url = self._absolute_url(href)
            normalized_url = self._normalize_url(absolute_url)
            inferred_collection = self._infer_collection_from_url(absolute_url)
            if collection != inferred_collection and not self._collection_filter_match(collection, inferred_collection, absolute_url):
                continue
            if normalized_url in seen:
                continue

            summary = self._extract_result_snippet(anchor)
            document_date, expression_date, year, court, nature = self._extract_metadata_from_url(absolute_url)
            results.append(
                {
                    "title": title,
                    "url": absolute_url,
                    "normalized_url": normalized_url,
                    "collection": inferred_collection,
                    "summary": summary,
                    "court": court,
                    "nature": nature,
                    "year": year,
                    "document_date": document_date,
                    "expression_date": expression_date,
                    "citation": self._build_citation(title, court, year, nature),
                }
            )
            seen.add(normalized_url)
            if len(results) >= limit:
                break

        return results

    def _parse_document(self, html: str, url: str) -> tuple[str, str, str, List[str]]:
        soup = BeautifulSoup(html, "html.parser")
        title = self._clean_text(
            (soup.select_one("main h1") or soup.select_one("title")).get_text(" ", strip=True)
        )

        main = soup.select_one("main") or soup.body or soup
        for node in main.select("script, style, nav, footer, form"):
            node.decompose()

        text_content = self._clean_text(main.get_text("\n", strip=True))
        if len(text_content) > 50000:
            text_content = text_content[:50000]

        paragraphs = [self._clean_text(p) for p in text_content.split("\n") if self._clean_text(p)]
        summary = " ".join(paragraphs[:3])[:1200]
        source_links = [
            self._absolute_url(a.get("href"))
            for a in soup.select('main a[href]')
            if a.get("href")
        ][:20]

        if not title:
            title = url.rsplit("/", 1)[-1]
        return title, text_content, summary, source_links

    def _chunk_text(self, text: str, chunk_size: int = 1500) -> List[Dict[str, Any]]:
        if not text:
            return []

        chunks = []
        start = 0
        index = 1
        while start < len(text):
            chunk = text[start : start + chunk_size].strip()
            if chunk:
                chunks.append({"index": index, "text": chunk})
                index += 1
            start += chunk_size
        return chunks[:25]

    def _infer_collections(self, question: str) -> List[str]:
        text = question.lower()
        collections: List[str] = []

        if any(token in text for token in ["section", "act", "regulation", "rules", "subsidiary", "law", "statute"]):
            collections.append("legislation")
        if any(token in text for token in ["case", "judgment", "court", "appeal", "holding", "decision", "vs", " v "]):
            collections.append("judgments")
        if any(token in text for token in ["gazette", "government notice", "gn ", "notice"]):
            collections.append("gazettes")
        if any(token in text for token in ["journal", "article", "digest", "law report", "commentary"]):
            collections.append("secondary_sources")

        if not collections:
            collections = ["legislation", "judgments", "gazettes"]

        ordered = []
        for item in collections:
            if item not in ordered:
                ordered.append(item)
        return ordered

    def _extract_metadata_from_url(
        self,
        url: str,
    ) -> tuple[Optional[datetime], Optional[datetime], Optional[int], Optional[str], Optional[str]]:
        expression_match = re.search(r"@(\d{4}-\d{2}-\d{2})", url)
        expression_date = self._parse_date(expression_match.group(1)) if expression_match else None

        date_match = re.search(r"/(\d{4}-\d{2}-\d{2})/", url)
        document_date = self._parse_date(date_match.group(1)) if date_match else expression_date

        year_match = re.search(r"/(19|20)\d{2}/", url)
        year = int(year_match.group(0).strip("/")) if year_match else None

        court = None
        judgment_match = re.search(r"/judgment/([^/]+)/", url)
        if judgment_match:
            court = judgment_match.group(1).upper()

        nature = None
        if "/officialGazette/" in url:
            nature = "Gazette"
        elif "/judgment/" in url:
            nature = "Judgment"
        elif "/act/" in url:
            nature = "Legislation"

        return document_date, expression_date, year, court, nature

    def _collection_filter_match(self, requested: str, inferred: str, url: str) -> bool:
        if requested == inferred:
            return True
        if requested == "legislation" and "/en/akn/tz/act/" in url and "/officialGazette/" not in url:
            return True
        if requested == "secondary_sources" and any(
            token in url
            for token in ["/journals/", "/articles/", "/law-reports/", "/taxonomy/case-indexes/", "/authors/TZLRC/"]
        ):
            return True
        if requested == "practice_essentials" and any(
            token in url
            for token in ["/doc/jot-documents-and-guidelines", "/authors/TZNPS/", "/authors/TLS/"]
        ):
            return True
        if requested == "regional_law" and any(
            token in url
            for token in ["/place/aa-eac", "/judgments/EACJ/", "/judgments/EACA/", "/judgments/AfCHPR/", "/judgments/ACHPR/"]
        ):
            return True
        return False

    def _infer_collection_from_url(self, url: str) -> str:
        if "/officialGazette/" in url or "/gazettes/" in url:
            return "gazettes"
        if "/judgment/" in url or "/judgments/" in url:
            return "judgments"
        if "/act/" in url or "/legislation/" in url:
            return "legislation"
        if any(token in url for token in ["/journals/", "/articles/", "/law-reports/", "/taxonomy/case-indexes/", "/authors/TZLRC/"]):
            return "secondary_sources"
        if any(token in url for token in ["/doc/jot-documents-and-guidelines", "/authors/TZNPS/", "/authors/TLS/"]):
            return "practice_essentials"
        if any(token in url for token in ["/place/aa-eac", "/judgments/EACJ/", "/judgments/EACA/", "/judgments/AfCHPR/", "/judgments/ACHPR/"]):
            return "regional_law"
        return "other"

    def _build_citation(
        self,
        title: str,
        court: Optional[str],
        year: Optional[int],
        nature: Optional[str],
    ) -> Optional[str]:
        if nature == "Judgment" and court and year:
            return f"{title} ({court}, {year})"
        if nature == "Legislation" and year:
            return f"{title} ({year})"
        return None

    def _extract_result_snippet(self, anchor) -> str:
        container = anchor.find_parent(["article", "li", "div"]) or anchor.parent
        snippet = self._clean_text(container.get_text(" ", strip=True))
        title = self._clean_text(anchor.get_text(" ", strip=True))
        if snippet.startswith(title):
            snippet = snippet[len(title) :].strip(" :-")
        return snippet[:500]

    def _document_payload(
        self,
        cached: LegalDocument,
        fetch_status: str,
        warning: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = cached.to_source_dict()
        payload.update(
            {
                "fetch_status": fetch_status,
                "text": cached.text_content,
                "excerpt": (cached.summary or cached.text_content or "")[:1500],
                "source_links": cached.source_links,
                "section_chunks": cached.section_chunks[:5],
            }
        )
        if warning:
            payload["warning"] = warning
        return payload

    def _is_cache_fresh(self, document: LegalDocument) -> bool:
        if not document.last_synced_at:
            return False
        age = datetime.utcnow() - document.last_synced_at
        return age.total_seconds() < (self.cache_ttl_hours * 3600)

    def _dedupe_sources(self, sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped = []
        seen = set()
        for item in sources:
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(item)
        return deduped

    def _absolute_url(self, url: str) -> str:
        return urljoin(f"{self.base_url}/", url)

    def _normalize_url(self, url: str) -> str:
        return url.split("?", 1)[0].rstrip("/")

    def _parse_date(self, value: str) -> Optional[datetime]:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    def _is_cloudflare_challenge(self, text: str) -> bool:
        lowered = text.lower()
        return "just a moment" in lowered and "cloudflare" in lowered
