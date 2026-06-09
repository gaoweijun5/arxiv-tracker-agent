"""Topic explorer workflow for natural language paper search."""

import asyncio
from typing import Optional
from loguru import logger

from backend.agents.tools import _send_progress, set_task_id, set_cancel_event, check_cancelled


async def explore_topic_workflow(
    query: str,
    max_results: int = 10,
    task_id: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> dict:
    """
    Topic exploration workflow:
    1. Understand the topic using LLM
    2. Search arXiv with extracted keywords
    3. Analyze and score papers
    4. Return recommended papers

    Args:
        query: User's natural language query about a research topic
        max_results: Maximum number of papers to return
        task_id: Optional task ID for WebSocket progress
        cancel_event: Optional event for cancellation

    Returns:
        Dictionary with topic understanding and recommended papers
    """
    set_task_id(task_id)
    set_cancel_event(cancel_event)

    try:
        # Step 1: Understand the topic
        await _send_progress("understand", 10, "Understanding your topic...")
        logger.info(f"Understanding topic: {query}")

        from backend.services.llm_service import get_llm_service
        llm_service = get_llm_service()

        topic_understanding = await llm_service.understand_topic(query)
        logger.info(f"Topic understood: {topic_understanding.understanding[:100]}...")
        logger.info(f"Keywords: {topic_understanding.keywords}")
        logger.info(f"Categories: {topic_understanding.categories}")

        await _send_progress("understand", 25, f"Found {len(topic_understanding.keywords)} keywords")

        # Step 2: Search arXiv with multiple strategies
        await _send_progress("search", 30, "Searching arXiv papers...")
        logger.info(f"Searching arXiv with {len(topic_understanding.search_queries)} strategies")

        from backend.services.arxiv_service import get_arxiv_service
        arxiv_service = get_arxiv_service()

        all_papers = []
        seen_arxiv_ids = set()

        for i, search_query in enumerate(topic_understanding.search_queries):
            check_cancelled()

            keywords = search_query.get("keywords", [])
            categories = search_query.get("categories", [])
            description = search_query.get("description", f"Search {i+1}")

            if not keywords and not categories:
                continue

            logger.info(f"Executing search: {description} - Keywords: {keywords}, Categories: {categories}")

            try:
                papers = await arxiv_service.search_papers(
                    categories=categories if categories else None,
                    keywords=keywords if keywords else None,
                    max_results=max_results * 2,  # Get more for deduplication
                    days_back=90,  # Search last 90 days for exploration
                )

                for paper in papers:
                    info = arxiv_service.extract_paper_info(paper)
                    arxiv_id = info["arxiv_id"]

                    if arxiv_id not in seen_arxiv_ids:
                        seen_arxiv_ids.add(arxiv_id)
                        all_papers.append({
                            "arxiv_id": arxiv_id,
                            "title": info["title"],
                            "abstract": info["abstract"],
                            "authors": info["authors"],
                            "categories": info["categories"],
                            "published_date": str(info["published_date"]),
                            "pdf_url": info["pdf_url"],
                            "search_query": description,
                        })

            except Exception as e:
                logger.warning(f"Search failed for {description}: {e}")
                continue

        logger.info(f"Found {len(all_papers)} unique papers from arXiv")
        await _send_progress("search", 50, f"Found {len(all_papers)} papers")

        if not all_papers:
            return {
                "status": "success",
                "query": query,
                "topic_understanding": topic_understanding.understanding,
                "keywords": topic_understanding.keywords,
                "categories": topic_understanding.categories,
                "papers": [],
                "message": "No papers found for this topic. Try different keywords or a broader query.",
            }

        # Step 3: Local scoring (fast filtering)
        await _send_progress("analyze", 55, "Scoring papers for relevance...")
        logger.info("Performing local scoring...")

        scored_papers = []
        for paper in all_papers:
            check_cancelled()

            # Calculate local relevance score
            score = _calculate_local_score(paper, topic_understanding)
            paper["local_score"] = score

            # Only keep papers with minimum relevance
            if score >= 0.2:
                scored_papers.append(paper)

        # Sort by local score
        scored_papers.sort(key=lambda x: x["local_score"], reverse=True)

        # Take top papers for LLM analysis
        papers_to_analyze = scored_papers[:min(10, len(scored_papers))]
        logger.info(f"Selected {len(papers_to_analyze)} papers for LLM analysis")

        await _send_progress("analyze", 65, f"Analyzing top {len(papers_to_analyze)} papers...")

        # Step 4: LLM analysis on top papers
        analyzed_papers = []
        for i, paper in enumerate(papers_to_analyze):
            check_cancelled()

            try:
                # Generate summary and check relevance
                analysis = await _analyze_paper_for_topic(
                    paper, query, topic_understanding
                )

                paper["analysis"] = analysis
                paper["relevance_score"] = analysis.get("relevance_score", 0)
                paper["relevance_reason"] = analysis.get("relevance_reason", "")
                paper["summary"] = analysis.get("summary", "")

                analyzed_papers.append(paper)

                progress = 65 + int((i + 1) / len(papers_to_analyze) * 25)
                await _send_progress("analyze", progress, f"Analyzed: {paper['title'][:40]}...")

            except Exception as e:
                logger.warning(f"Failed to analyze paper {paper['arxiv_id']}: {e}")
                # Use local score as fallback
                paper["relevance_score"] = paper["local_score"]
                paper["relevance_reason"] = "Local scoring only (LLM analysis failed)"
                paper["summary"] = paper["abstract"][:200] + "..."
                analyzed_papers.append(paper)

        # Step 5: Sort by relevance and take top results
        analyzed_papers.sort(key=lambda x: x["relevance_score"], reverse=True)
        recommended_papers = analyzed_papers[:max_results]

        await _send_progress("complete", 95, f"Found {len(recommended_papers)} relevant papers")

        # Prepare response
        papers_response = []
        for paper in recommended_papers:
            papers_response.append({
                "arxiv_id": paper["arxiv_id"],
                "title": paper["title"],
                "authors": paper["authors"],
                "abstract": paper["abstract"],
                "categories": paper["categories"],
                "published_date": paper["published_date"],
                "pdf_url": paper["pdf_url"],
                "relevance_score": paper.get("relevance_score", 0),
                "relevance_reason": paper.get("relevance_reason", ""),
                "summary": paper.get("summary", ""),
            })

        logger.info(f"Topic exploration completed: {len(papers_response)} papers recommended")

        return {
            "status": "success",
            "query": query,
            "topic_understanding": topic_understanding.understanding,
            "keywords": topic_understanding.keywords,
            "expanded_keywords": topic_understanding.expanded_keywords,
            "categories": topic_understanding.categories,
            "papers": papers_response,
            "total_found": len(all_papers),
            "total_analyzed": len(analyzed_papers),
        }

    except asyncio.CancelledError:
        logger.info("Topic exploration cancelled")
        return {
            "status": "cancelled",
            "query": query,
            "error": "Exploration was cancelled",
        }
    except Exception as e:
        logger.exception(f"Topic exploration failed: {e}")
        return {
            "status": "failed",
            "query": query,
            "error": str(e),
        }
    finally:
        set_task_id(None)
        set_cancel_event(None)


def _calculate_local_score(paper: dict, topic_understanding) -> float:
    """Calculate local relevance score based on keyword matching.

    Args:
        paper: Paper dictionary with title, abstract, categories
        topic_understanding: TopicUnderstanding object

    Returns:
        Score between 0 and 1
    """
    import re

    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    text = f"{title} {abstract}"
    paper_categories = {cat.lower() for cat in paper.get("categories", [])}

    # Keyword matching score
    keywords = topic_understanding.keywords
    expanded_keywords = topic_understanding.expanded_keywords

    keyword_matches = sum(1 for kw in keywords if kw.lower() in text)
    expanded_matches = sum(1 for kw in expanded_keywords if kw.lower() in text)

    # Normalize scores
    keyword_score = min(keyword_matches / max(len(keywords), 1), 1.0)
    expanded_score = min(expanded_matches / max(len(expanded_keywords), 1), 1.0)

    # Category matching score
    target_categories = {cat.lower() for cat in topic_understanding.categories}
    category_matches = len(paper_categories & target_categories)
    category_score = min(category_matches / max(len(target_categories), 1), 1.0)

    # Title keyword bonus (keywords in title are more important)
    title_keyword_matches = sum(1 for kw in keywords if kw.lower() in title)
    title_bonus = min(title_keyword_matches / max(len(keywords), 1), 0.3)

    # Weighted combination
    final_score = (
        0.35 * keyword_score +
        0.25 * expanded_score +
        0.25 * category_score +
        0.15 * title_bonus
    )

    return round(min(final_score, 1.0), 4)


async def _analyze_paper_for_topic(
    paper: dict,
    query: str,
    topic_understanding,
) -> dict:
    """Analyze a paper for relevance to the explored topic.

    Args:
        paper: Paper dictionary
        query: Original user query
        topic_understanding: TopicUnderstanding object

    Returns:
        Analysis dictionary with summary and relevance info
    """
    from backend.services.llm_service import get_llm_service

    llm_service = get_llm_service()

    # Create interests-like structure for relevance checking
    interests = [{
        "topic": query,
        "description": topic_understanding.understanding,
        "keywords": topic_understanding.keywords,
        "categories": topic_understanding.categories,
        "weight": 1.0,
    }]

    # Run summary and relevance check in parallel
    summary_result, relevance_result = await asyncio.gather(
        llm_service.generate_summary(
            title=paper["title"],
            abstract=paper["abstract"],
            authors=paper.get("authors", []),
            categories=paper.get("categories", []),
        ),
        llm_service.check_relevance(
            title=paper["title"],
            abstract=paper["abstract"],
            categories=paper.get("categories", []),
            interests=interests,
        ),
    )

    return {
        "summary": summary_result.summary,
        "summary_zh": summary_result.summary_zh,
        "key_findings": summary_result.key_findings,
        "methodology": summary_result.methodology,
        "relevance_score": relevance_result.score,
        "relevance_reason": relevance_result.reason,
        "is_relevant": relevance_result.is_relevant,
    }
