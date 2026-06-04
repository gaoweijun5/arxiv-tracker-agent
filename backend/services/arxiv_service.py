"""ArXiv paper fetching and processing service."""

import asyncio
import arxiv
import httpx
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

from backend.core.config import get_settings


class ArxivService:
    """Service for fetching and downloading arXiv papers."""

    _request_lock = asyncio.Lock()
    _last_request_at: float = 0.0
    _cooldown_until: float = 0.0

    def __init__(self):
        self.settings = get_settings()
        self.client = arxiv.Client(
            page_size=self.settings.arxiv_page_size,
            delay_seconds=self.settings.arxiv_request_interval_seconds,
            num_retries=0,
        )
        self._patch_arxiv_client_user_agent()

    def _patch_arxiv_client_user_agent(self) -> None:
        """Attach the app user agent to arxiv.py requests."""
        original_get = self.client._session.get

        def identified_get(url, **kwargs):
            headers = dict(kwargs.pop("headers", {}) or {})
            library_agent = headers.get("user-agent") or headers.get("User-Agent")
            app_agent = self.settings.arxiv_user_agent.strip()
            if app_agent and library_agent and app_agent not in library_agent:
                headers["user-agent"] = f"{app_agent} {library_agent}"
            elif app_agent:
                headers["user-agent"] = app_agent
            kwargs["headers"] = headers
            return original_get(url, **kwargs)

        self.client._session.get = identified_get

    async def _wait_for_request_slot(self) -> None:
        """Serialize arXiv traffic and keep at least the configured interval."""
        now = time.monotonic()
        wait_for_interval = max(
            0.0,
            self.__class__._last_request_at
            + self.settings.arxiv_request_interval_seconds
            - now,
        )
        wait_for_cooldown = max(0.0, self.__class__._cooldown_until - now)
        wait_seconds = max(wait_for_interval, wait_for_cooldown)

        if wait_seconds > 0:
            logger.info(f"Waiting {wait_seconds:.1f}s before next arXiv request")
            await asyncio.sleep(wait_seconds)

    async def _run_serial_arxiv_request(self, label: str, request_coro):
        """Run one arXiv-facing request under the global request lock."""
        async with self.__class__._request_lock:
            await self._wait_for_request_slot()
            try:
                return await request_coro()
            finally:
                self.__class__._last_request_at = time.monotonic()

    async def _backoff_after_error(self, error: Exception, attempt: int) -> None:
        """Apply a shared cooldown after 403/429 responses or timeouts."""
        wait_seconds = self.settings.arxiv_rate_limit_backoff_seconds * (2 ** attempt)
        self.__class__._cooldown_until = max(
            self.__class__._cooldown_until,
            time.monotonic() + wait_seconds,
        )
        status_code = self._status_code_from_error(error)
        if status_code:
            error_desc = f"status {status_code}"
        elif isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            error_desc = "timeout"
        else:
            error_desc = type(error).__name__
        logger.warning(
            f"arXiv request failed ({error_desc}); "
            f"backing off for {wait_seconds:.0f}s"
        )
        await asyncio.sleep(wait_seconds)

    @staticmethod
    def _status_code_from_error(error: Exception) -> Optional[int]:
        if isinstance(error, arxiv.HTTPError):
            return error.status
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code
        return None

    def _should_backoff(self, error: Exception) -> bool:
        return self._status_code_from_error(error) in {403, 429}

    async def search_papers(
        self,
        categories: Optional[list[str]] = None,
        keywords: Optional[list[str]] = None,
        max_results: Optional[int] = None,
        days_back: int = 7,
    ) -> list[arxiv.Result]:
        """Search for recent papers on arXiv.

        Args:
            categories: arXiv categories to search (e.g., ["cs.AI", "cs.CL"])
            keywords: Keywords to search for
            max_results: Maximum number of results
            days_back: How many days back to search

        Returns:
            List of arXiv paper results
        """
        categories = categories or self.settings.arxiv_categories
        max_results = max_results or self.settings.arxiv_max_results
        self.client.page_size = max(1, min(max_results, self.settings.arxiv_page_size))

        # Build search query
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])

        if keywords:
            keyword_query = " OR ".join([f'all:"{kw}"' for kw in keywords])
            query = f"({category_query}) AND ({keyword_query})"
        else:
            query = category_query

        logger.info(f"Searching arXiv with query: {query}")

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        cutoff_date = datetime.now() - timedelta(days=days_back)

        def _search_sync():
            papers = []
            for result in self.client.results(search):
                pub_date = result.published.replace(tzinfo=None)
                if pub_date < cutoff_date:
                    continue
                papers.append(result)
            return papers

        papers = []
        for attempt in range(self.settings.arxiv_max_retries + 1):
            try:
                papers = await self._run_serial_arxiv_request(
                    "search arXiv",
                    lambda: asyncio.wait_for(
                        asyncio.to_thread(_search_sync),
                        timeout=self.settings.arxiv_request_timeout_seconds,
                    ),
                )
                break
            except (asyncio.TimeoutError, TimeoutError) as e:
                logger.warning(f"arXiv search timed out (attempt {attempt + 1}/{self.settings.arxiv_max_retries + 1})")
                if attempt < self.settings.arxiv_max_retries:
                    await self._backoff_after_error(e, attempt)
                    continue
                logger.warning(f"arXiv search timed out after {attempt + 1} attempts")
                return papers
            except Exception as e:
                if self._should_backoff(e) and attempt < self.settings.arxiv_max_retries:
                    await self._backoff_after_error(e, attempt)
                    continue
                logger.warning(f"Error during arXiv search: {e}")
                return papers

        logger.info(f"Found {len(papers)} papers from last {days_back} days")
        return papers

    async def search_by_interest(
        self,
        topic: str,
        keywords: list[str],
        categories: Optional[list[str]] = None,
        max_results: int = 30,
    ) -> list[arxiv.Result]:
        """Search papers matching a user interest.

        Args:
            topic: Interest topic
            keywords: Related keywords
            categories: Preferred categories
            max_results: Maximum results

        Returns:
            List of matching papers
        """
        all_keywords = [topic] + keywords
        return await self.search_papers(
            categories=categories,
            keywords=all_keywords,
            max_results=max_results,
            days_back=7,
        )

    async def download_pdf(
        self,
        paper: arxiv.Result,
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Download paper PDF.

        Args:
            paper: arXiv paper result
            save_dir: Directory to save PDF

        Returns:
            Path to downloaded PDF or None if failed
        """
        arxiv_id = paper.entry_id.split("/")[-1]
        return await self.download_pdf_url(paper.pdf_url, arxiv_id, save_dir)

    async def download_pdf_url(
        self,
        pdf_url: str,
        arxiv_id: str,
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Download one PDF through the shared arXiv request limiter."""
        save_dir = save_dir or self.settings.papers_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{arxiv_id.replace('/', '_')}.pdf"
        pdf_path = save_dir / filename

        if pdf_path.exists():
            logger.info(f"PDF already exists: {pdf_path}")
            return pdf_path

        async def _download_once() -> Path:
            logger.info(f"Downloading PDF from {pdf_url}")
            headers = {"User-Agent": self.settings.arxiv_user_agent}
            async with httpx.AsyncClient(headers=headers) as client:
                response = await client.get(
                    pdf_url,
                    follow_redirects=True,
                    timeout=self.settings.arxiv_request_timeout_seconds,
                )
                response.raise_for_status()
                pdf_path.write_bytes(response.content)
                logger.info(f"Downloaded PDF to {pdf_path}")
                return pdf_path

        for attempt in range(self.settings.arxiv_max_retries + 1):
            try:
                return await self._run_serial_arxiv_request("download arXiv PDF", _download_once)
            except (asyncio.TimeoutError, TimeoutError) as e:
                logger.warning(f"PDF download timed out (attempt {attempt + 1}/{self.settings.arxiv_max_retries + 1})")
                if attempt < self.settings.arxiv_max_retries:
                    await self._backoff_after_error(e, attempt)
                    continue
                logger.error(f"PDF download timed out after {attempt + 1} attempts")
                return None
            except Exception as e:
                if self._should_backoff(e) and attempt < self.settings.arxiv_max_retries:
                    await self._backoff_after_error(e, attempt)
                    continue
                logger.error(f"Failed to download PDF: {e}")
                return None

        return None

    def extract_paper_info(self, paper: arxiv.Result) -> dict:
        """Extract structured information from an arXiv paper.

        Args:
            paper: arXiv paper result

        Returns:
            Dictionary with paper information
        """
        arxiv_id = paper.entry_id.split("/")[-1]
        return {
            "arxiv_id": arxiv_id,
            "title": paper.title.strip(),
            "authors": [author.name for author in paper.authors],
            "abstract": paper.summary.strip(),
            "categories": [cat for cat in paper.categories],
            "primary_category": paper.primary_category,
            "published_date": paper.published,
            "updated_date": paper.updated,
            "pdf_url": paper.pdf_url,
            "comment": paper.comment,
            "journal_ref": paper.journal_ref,
            "doi": paper.doi,
        }


# Singleton instance
_arxiv_service: Optional[ArxivService] = None


def get_arxiv_service() -> ArxivService:
    """Get or create arXiv service singleton."""
    global _arxiv_service
    if _arxiv_service is None:
        _arxiv_service = ArxivService()
    return _arxiv_service
