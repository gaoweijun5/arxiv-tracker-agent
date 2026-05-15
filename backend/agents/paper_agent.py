"""LangGraph agent for paper tracking and recommendation workflow."""

from typing import TypedDict, Annotated, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from loguru import logger


class PaperState(TypedDict):
    """State for the paper tracking agent."""

    # Input
    categories: list[str]
    keywords: list[str]
    user_interests: list[dict]
    days_back: int
    max_results: int

    # Processing state
    fetched_papers: list[dict]
    analyzed_papers: list[dict]
    relevant_papers: list[dict]
    recommendations: list[dict]

    # Messages for conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Output
    daily_digest: str
    error: Optional[str]

    # Task tracking
    task_id: Optional[str]


async def send_ws_progress(task_id: str, step: str, progress: int, message: str):
    """Send progress via WebSocket if available."""
    if task_id:
        try:
            from backend.api.websocket import send_progress
            await send_progress(task_id, step, progress, message)
        except Exception:
            pass


def create_paper_workflow() -> StateGraph:
    """Create the paper tracking and recommendation workflow.

    Returns:
        Compiled StateGraph workflow
    """

    async def fetch_papers(state: PaperState) -> PaperState:
        """Node: Fetch papers from arXiv."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "fetch", 10, "Searching arXiv for papers...")

        logger.info("Fetching papers from arXiv...")
        from backend.services.arxiv_service import get_arxiv_service

        arxiv_service = get_arxiv_service()
        days_back = state.get("days_back", 7)
        max_results = state.get("max_results", 30)

        try:
            # Fetch papers for each interest
            all_papers = []
            interests = state.get("user_interests", [])

            if interests:
                for i, interest in enumerate(interests):
                    progress = 10 + int(15 * (i / len(interests)))
                    await send_ws_progress(
                        task_id, "fetch", progress,
                        f"Searching: {interest['topic']}..."
                    )

                    papers = await arxiv_service.search_by_interest(
                        topic=interest["topic"],
                        keywords=interest.get("keywords", []),
                        categories=interest.get("categories"),
                        max_results=max_results,
                    )
                    for paper in papers:
                        info = arxiv_service.extract_paper_info(paper)
                        info["matched_interest"] = interest["topic"]
                        all_papers.append(info)
            else:
                papers = await arxiv_service.search_papers(
                    categories=state.get("categories"),
                    keywords=state.get("keywords"),
                    days_back=days_back,
                    max_results=max_results,
                )
                all_papers = [arxiv_service.extract_paper_info(p) for p in papers]

            # Deduplicate by arxiv_id
            seen = set()
            unique_papers = []
            for p in all_papers:
                if p["arxiv_id"] not in seen:
                    seen.add(p["arxiv_id"])
                    unique_papers.append(p)

            logger.info(f"Fetched {len(unique_papers)} unique papers")
            await send_ws_progress(
                task_id, "fetch", 25,
                f"Found {len(unique_papers)} papers from arXiv"
            )
            return {**state, "fetched_papers": unique_papers}

        except Exception as e:
            logger.error(f"Failed to fetch papers: {e}")
            return {**state, "fetched_papers": [], "error": str(e)}

    async def analyze_papers(state: PaperState) -> PaperState:
        """Node: Analyze papers with AI summarization."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "analyze", 30, "Generating AI summaries...")

        logger.info("Analyzing papers with AI...")
        from backend.services.llm_service import get_llm_service

        llm_service = get_llm_service()
        fetched = state.get("fetched_papers", [])
        analyzed = []
        total = min(len(fetched), 20)

        for i, paper in enumerate(fetched[:20]):
            progress = 30 + int(30 * (i / total))
            await send_ws_progress(
                task_id, "analyze", progress,
                f"Analyzing paper {i+1}/{total}: {paper['title'][:40]}..."
            )

            try:
                summary = await llm_service.generate_summary(
                    title=paper["title"],
                    abstract=paper["abstract"],
                    authors=paper["authors"],
                    categories=paper["categories"],
                )
                paper["ai_summary"] = summary.summary
                paper["ai_summary_zh"] = summary.summary_zh
                paper["key_findings"] = summary.key_findings
                paper["methodology"] = summary.methodology
                paper["relevance_score"] = summary.relevance_score
                paper["relevance_reason"] = summary.relevance_reason
                analyzed.append(paper)
            except Exception as e:
                logger.warning(f"Failed to analyze paper '{paper['title'][:50]}...': {e}")
                paper["ai_summary"] = paper["abstract"][:200]
                paper["relevance_score"] = 0.5
                analyzed.append(paper)

        logger.info(f"Analyzed {len(analyzed)} papers")
        await send_ws_progress(task_id, "analyze", 60, f"Analyzed {len(analyzed)} papers")
        return {**state, "analyzed_papers": analyzed}

    async def filter_relevant(state: PaperState) -> PaperState:
        """Node: Filter papers based on relevance to user interests."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "filter", 65, "Filtering relevant papers...")

        logger.info("Filtering relevant papers...")
        analyzed = state.get("analyzed_papers", [])
        relevant = []

        for paper in analyzed:
            if paper.get("relevance_score", 0) >= 0.6:
                relevant.append(paper)

        # Sort by relevance score
        relevant.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        logger.info(f"Filtered {len(relevant)} relevant papers from {len(analyzed)}")
        await send_ws_progress(
            task_id, "filter", 75,
            f"Found {len(relevant)} relevant papers"
        )
        return {**state, "relevant_papers": relevant}

    async def generate_recommendations(state: PaperState) -> PaperState:
        """Node: Generate paper recommendations with reasons."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "recommend", 80, "Generating recommendations...")

        logger.info("Generating recommendations...")
        relevant = state.get("relevant_papers", [])

        recommendations = []
        for paper in relevant[:10]:  # Top 10 recommendations
            rec = {
                "paper": paper,
                "score": paper.get("relevance_score", 0.5),
                "reason": paper.get("relevance_reason", "Matches your research interests"),
                "matched_interest": paper.get("matched_interest", "General"),
            }
            recommendations.append(rec)

        logger.info(f"Generated {len(recommendations)} recommendations")
        await send_ws_progress(
            task_id, "recommend", 85,
            f"Generated {len(recommendations)} recommendations"
        )
        return {**state, "recommendations": recommendations}

    async def create_digest(state: PaperState) -> PaperState:
        """Node: Create daily research digest."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "digest", 90, "Creating research digest...")

        logger.info("Creating daily digest...")
        recommendations = state.get("recommendations", [])

        if not recommendations:
            return {**state, "daily_digest": "No new relevant papers found today."}

        # Simple digest without LLM call (faster)
        digest_parts = []
        for i, rec in enumerate(recommendations[:5]):
            paper = rec["paper"]
            digest_parts.append(
                f"**{i+1}. {paper['title']}**\n"
                f"{paper.get('ai_summary', paper['abstract'][:150])}...\n"
                f"Relevance: {rec['score']*100:.0f}%"
            )

        digest = "📰 **Today's Research Highlights**\n\n" + "\n\n".join(digest_parts)

        logger.info("Created digest")
        await send_ws_progress(task_id, "digest", 95, "Digest created")
        return {**state, "daily_digest": digest}

    async def save_to_database(state: PaperState) -> PaperState:
        """Node: Save relevant papers to database with PDF processing."""
        task_id = state.get("task_id")
        await send_ws_progress(task_id, "save", 96, "Saving papers to database...")

        logger.info("Saving papers to database...")
        from backend.models.database import get_session_factory, Paper, PaperRecommendation
        from backend.services.vector_store import get_vector_store
        from backend.services.pdf_service import get_pdf_service
        from backend.services.arxiv_service import get_arxiv_service

        vector_store = get_vector_store()
        pdf_service = get_pdf_service()
        arxiv_service = get_arxiv_service()
        factory = get_session_factory()

        recommendations = state.get("recommendations", [])
        saved_count = 0
        total = len(recommendations)

        async with factory() as session:
            for i, rec in enumerate(recommendations):
                paper_data = rec["paper"]
                try:
                    # Check if paper already exists
                    from sqlalchemy import select
                    result = await session.execute(
                        select(Paper).where(Paper.arxiv_id == paper_data["arxiv_id"])
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        logger.info(f"Paper {paper_data['arxiv_id']} already exists")
                        continue

                    # Update progress
                    await send_ws_progress(
                        task_id, "save", 96 + int(3 * (i / total)),
                        f"Processing: {paper_data['title'][:40]}..."
                    )

                    # Download PDF and extract text
                    pdf_path = None
                    full_text = None
                    is_downloaded = False

                    if paper_data.get("pdf_url"):
                        try:
                            # Search for the paper to get arxiv.Result object
                            papers = await arxiv_service.search_papers(
                                keywords=[paper_data["arxiv_id"]],
                                max_results=1,
                            )
                            if papers:
                                pdf_path = await arxiv_service.download_pdf(papers[0])
                                if pdf_path:
                                    is_downloaded = True
                                    full_text = pdf_service.extract_text(pdf_path)
                                    logger.info(f"Extracted {len(full_text)} chars from PDF")
                        except Exception as e:
                            logger.warning(f"Failed to download/process PDF: {e}")

                    # Save to database
                    paper = Paper(
                        arxiv_id=paper_data["arxiv_id"],
                        title=paper_data["title"],
                        authors=paper_data["authors"],
                        abstract=paper_data["abstract"],
                        categories=paper_data["categories"],
                        published_date=paper_data["published_date"],
                        pdf_url=paper_data.get("pdf_url"),
                        local_pdf_path=str(pdf_path) if pdf_path else None,
                        ai_summary=paper_data.get("ai_summary"),
                        ai_summary_zh=paper_data.get("ai_summary_zh"),
                        key_findings=paper_data.get("key_findings"),
                        relevance_score=rec["score"],
                        is_downloaded=is_downloaded,
                    )
                    session.add(paper)
                    await session.flush()

                    # Add abstract to vector store
                    await vector_store.add_paper(
                        arxiv_id=paper_data["arxiv_id"],
                        title=paper_data["title"],
                        abstract=paper_data["abstract"],
                    )

                    # Add full text chunks to vector store for RAG
                    if full_text:
                        chunks = pdf_service.chunk_text(full_text)
                        if chunks:
                            await vector_store.add_paper_chunks(
                                arxiv_id=paper_data["arxiv_id"],
                                title=paper_data["title"],
                                chunks=chunks,
                            )
                            logger.info(f"Added {len(chunks)} chunks to vector store")

                    # Save recommendation
                    recommendation = PaperRecommendation(
                        paper_id=paper.id,
                        score=rec["score"],
                        reason=rec["reason"],
                    )
                    session.add(recommendation)
                    saved_count += 1

                    logger.info(f"Saved paper: {paper_data['title'][:50]}...")

                except Exception as e:
                    logger.error(f"Failed to save paper: {e}")
                    continue

            await session.commit()

        await send_ws_progress(
            task_id, "save", 99,
            f"Saved {saved_count} new papers to database"
        )
        return state

    # Build the workflow graph
    workflow = StateGraph(PaperState)

    # Add nodes
    workflow.add_node("fetch_papers", fetch_papers)
    workflow.add_node("analyze_papers", analyze_papers)
    workflow.add_node("filter_relevant", filter_relevant)
    workflow.add_node("generate_recommendations", generate_recommendations)
    workflow.add_node("create_digest", create_digest)
    workflow.add_node("save_to_database", save_to_database)

    # Define edges
    workflow.set_entry_point("fetch_papers")
    workflow.add_edge("fetch_papers", "analyze_papers")
    workflow.add_edge("analyze_papers", "filter_relevant")
    workflow.add_edge("filter_relevant", "generate_recommendations")
    workflow.add_edge("generate_recommendations", "create_digest")
    workflow.add_edge("create_digest", "save_to_database")
    workflow.add_edge("save_to_database", END)

    # Compile the workflow
    return workflow.compile()


# Singleton instance
_workflow = None


def get_paper_workflow() -> StateGraph:
    """Get or create paper workflow singleton."""
    global _workflow
    if _workflow is None:
        _workflow = create_paper_workflow()
    return _workflow
