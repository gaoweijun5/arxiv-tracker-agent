"""Research report generation service."""

from datetime import datetime
from typing import Optional
from loguru import logger
from sqlalchemy import select

from backend.models.database import get_session_factory, Paper, ResearchReport


class ReportService:
    """Service for generating persistent research reports after fetch runs."""

    async def generate_fetch_report(
        self,
        fetch_log_id: Optional[int],
        agent_result: dict,
        source: str,
        interests_data: list[dict],
    ) -> ResearchReport:
        """Generate and save a report for one fetch run."""
        saved_paper_ids = list(dict.fromkeys(agent_result.get("saved_paper_ids") or []))
        status = agent_result.get("status", "success")
        stats = {
            "papers_found": agent_result.get("papers_found", 0),
            "papers_analyzed": agent_result.get("papers_analyzed", 0),
            "papers_relevant": agent_result.get("papers_relevant", 0),
            "papers_saved": agent_result.get("papers_saved", len(saved_paper_ids)),
        }

        papers = await self._load_papers(saved_paper_ids)
        title = self._build_title(source)

        if status == "failed" and not papers:
            report_status = "failed"
            summary = "Fetch failed before any reportable papers were saved."
            content_md = self._build_failed_report(title, agent_result, stats)
            error_message = agent_result.get("error") or "Fetch failed"
        elif not papers:
            report_status = "empty"
            summary = "No new papers were saved in this fetch."
            content_md = self._build_empty_report(title, agent_result, stats, interests_data)
            error_message = agent_result.get("error")
        else:
            report_status = "generated"
            error_message = agent_result.get("error")
            try:
                from backend.services.llm_service import get_llm_service

                content_md = await get_llm_service().generate_research_report(
                    papers=[paper.to_dict() for paper in papers],
                    stats=stats,
                    interests=interests_data,
                    source=source,
                )
                summary = self._extract_summary(content_md)
            except Exception as e:
                logger.warning(f"Falling back to deterministic research report: {e}")
                content_md = self._build_fallback_report(title, papers, stats, interests_data)
                summary = f"Saved {len(papers)} papers from this fetch."

        factory = get_session_factory()
        async with factory() as session:
            report = ResearchReport(
                fetch_log_id=fetch_log_id,
                source=source,
                title=title,
                summary=summary,
                content_md=content_md,
                paper_ids=saved_paper_ids,
                stats=stats,
                status=report_status,
                error_message=error_message,
            )
            session.add(report)
            await session.commit()
            await session.refresh(report)
            logger.info(f"Generated research report {report.id} for fetch log {fetch_log_id}")
            return report

    async def _load_papers(self, paper_ids: list[int]) -> list[Paper]:
        if not paper_ids:
            return []

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Paper).where(Paper.id.in_(paper_ids)))
            papers = result.scalars().all()

        by_id = {paper.id: paper for paper in papers}
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]

    def _build_title(self, source: str) -> str:
        label = "Daily Research Report" if source == "auto" else "Research Report"
        return f"{label} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    def _build_failed_report(self, title: str, agent_result: dict, stats: dict) -> str:
        error = agent_result.get("error") or "Unknown error"
        return f"""# {title}

## Executive Summary
This fetch failed before a research report could be generated from saved papers.

## Fetch Stats
- Papers found: {stats["papers_found"]}
- Papers analyzed: {stats["papers_analyzed"]}
- Papers relevant: {stats["papers_relevant"]}
- Papers saved: {stats["papers_saved"]}

## Error
{error}

## Suggested Next Steps
- Check whether arXiv is rate limiting the current network.
- Try a smaller search window or fewer selected interests.
- Run the fetch again later if the error was temporary.
"""

    def _build_empty_report(
        self,
        title: str,
        agent_result: dict,
        stats: dict,
        interests_data: list[dict],
    ) -> str:
        topics = ", ".join([i.get("topic", "") for i in interests_data if i.get("topic")]) or "No topics"
        error = agent_result.get("error")
        error_section = f"\n## Error\n{error}\n" if error else ""
        return f"""# {title}

## Executive Summary
No new papers were saved in this fetch.

## Search Scope
{topics}

## Fetch Stats
- Papers found: {stats["papers_found"]}
- Papers analyzed: {stats["papers_analyzed"]}
- Papers relevant: {stats["papers_relevant"]}
- Papers saved: {stats["papers_saved"]}
{error_section}
## Suggested Next Steps
- Expand the search period if the topic is quiet.
- Add more specific keywords to active interests.
- Check arXiv rate-limit status if papers found is zero.
"""

    def _build_fallback_report(
        self,
        title: str,
        papers: list[Paper],
        stats: dict,
        interests_data: list[dict],
    ) -> str:
        topics = ", ".join([i.get("topic", "") for i in interests_data if i.get("topic")]) or "No topics"
        paper_sections = "\n\n".join([
            f"""### {index}. {paper.title}
- Authors: {", ".join((paper.authors or [])[:4])}
- Categories: {", ".join(paper.categories or [])}
- Relevance score: {paper.relevance_score if paper.relevance_score is not None else "n/a"}
- Summary: {paper.ai_summary or paper.abstract[:400]}"""
            for index, paper in enumerate(papers, start=1)
        ])
        return f"""# {title}

## Executive Summary
This fetch saved {len(papers)} papers matching the selected interests.

## Search Scope
{topics}

## Fetch Stats
- Papers found: {stats["papers_found"]}
- Papers analyzed: {stats["papers_analyzed"]}
- Papers relevant: {stats["papers_relevant"]}
- Papers saved: {stats["papers_saved"]}

## Top Papers
{paper_sections}

## Suggested Next Steps
- Open the most relevant papers and download PDFs for full-text Q&A.
- Bookmark papers that match your long-term research direction.
- Dismiss weak matches so future ranking can learn from the signal.
"""

    def _extract_summary(self, content_md: str) -> str:
        lines = [
            line.strip()
            for line in content_md.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return lines[0][:300] if lines else "Research report generated."


_report_service: Optional[ReportService] = None


def get_report_service() -> ReportService:
    """Get or create report service singleton."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
