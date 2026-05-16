"""ArXiv paper fetching and processing service."""

import asyncio
import arxiv
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

from backend.core.config import get_settings


class ArxivService:
    """Service for fetching and downloading arXiv papers."""

    def __init__(self):
        self.settings = get_settings()
        self.client = arxiv.Client()

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
            try:
                for result in self.client.results(search):
                    pub_date = result.published.replace(tzinfo=None)
                    if pub_date < cutoff_date:
                        continue
                    papers.append(result)
            except Exception as e:
                logger.warning(f"Error during arXiv search: {e}")
            return papers

        papers = await asyncio.to_thread(_search_sync)

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
        save_dir = save_dir or self.settings.papers_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        arxiv_id = paper.entry_id.split("/")[-1]
        filename = f"{arxiv_id.replace('.', '_')}.pdf"
        pdf_path = save_dir / filename

        if pdf_path.exists():
            logger.info(f"PDF already exists: {pdf_path}")
            return pdf_path

        try:
            pdf_url = paper.pdf_url
            logger.info(f"Downloading PDF from {pdf_url}")

            async with httpx.AsyncClient() as client:
                response = await client.get(pdf_url, follow_redirects=True, timeout=60.0)
                response.raise_for_status()

                pdf_path.write_bytes(response.content)
                logger.info(f"Downloaded PDF to {pdf_path}")
                return pdf_path

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
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
