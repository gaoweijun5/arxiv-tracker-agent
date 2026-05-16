"""Autonomous paper agent using LangGraph's create_react_agent."""

import json
from typing import Optional
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from loguru import logger

from backend.agents.tools import (
    search_arxiv, analyze_paper, check_relevance,
    download_and_save_paper, get_user_interests,
    get_user_feedback_summary, check_paper_exists,
    set_task_id, get_stats, _send_progress, _stats_ctx,
)

AGENT_SYSTEM_PROMPT = """You are an autonomous research paper agent. Your goal is to discover, analyze, and save high-quality academic papers that match the user's research interests.

WORKFLOW:
1. Call get_user_interests() to understand what the user cares about
2. Call get_user_feedback_summary() to learn from past behavior (what was bookmarked, what was skipped)
3. Call search_arxiv() with appropriate keywords and categories from the interests
4. For each promising paper, call check_paper_exists() to skip duplicates
5. For new papers, call check_relevance() first as a quick filter
6. For relevant papers (score >= 0.5), call analyze_paper() for full analysis
7. Only download_and_save_paper() for papers with relevance_score >= 0.6
8. If too few relevant papers found (< 3), try broader searches with modified keywords or more days_back

CONSTRAINTS:
- Analyze at most 20 papers per run to control costs
- Download at most 10 papers per run
- Always check if papers exist before analyzing to avoid redundant work
- If search results seem poor quality, adjust your search strategy (broader keywords, different categories, more days_back)
- Use the feedback summary to guide your search: prioritize categories and topics the user has bookmarked before

REFLECTION:
After analyzing papers, evaluate the results:
- Are there enough relevant papers? If not, search with different terms.
- Are the relevance scores generally high or low? Adjust your threshold or search accordingly.
- Do the results align with what the user has bookmarked in the past?

When done, provide a brief summary of what you found, analyzed, and saved. Include counts of papers found, analyzed, relevant, and saved."""


def _create_agent():
    """Create the ReAct paper agent."""
    from backend.core.config import get_settings
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
    )

    tools = [
        get_user_interests, get_user_feedback_summary,
        search_arxiv, check_paper_exists, check_relevance,
        analyze_paper, download_and_save_paper,
    ]

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=AGENT_SYSTEM_PROMPT),
    )


# Singleton
_agent = None


def get_paper_agent():
    """Get or create the paper agent singleton."""
    global _agent
    if _agent is None:
        _agent = _create_agent()
    return _agent


async def run_paper_agent(
    interests_data: list[dict],
    days_back: int = 7,
    max_results: int = 30,
    task_id: Optional[str] = None,
) -> dict:
    """Run the autonomous paper agent.

    Args:
        interests_data: List of user interest dicts
        days_back: How many days back to search
        max_results: Max results per search
        task_id: WebSocket task ID for progress updates

    Returns:
        Dict with status, stats, and final message
    """
    set_task_id(task_id)

    # Initialize stats in context
    stats = {"papers_found": 0, "papers_analyzed": 0, "papers_relevant": 0, "papers_saved": 0}
    _stats_ctx.set(stats)

    agent = get_paper_agent()

    interests_summary = json.dumps([{
        "topic": i.get("topic", ""),
        "keywords": i.get("keywords", []),
        "categories": i.get("categories", []),
    } for i in interests_data])

    user_message = f"""Find and process papers for the user.

User interests: {interests_summary}
Search parameters: days_back={days_back}, max_results={max_results}

Start by getting the user's interests and feedback summary, then search for papers,
analyze the most promising ones, and download/save the best results."""

    await _send_progress("start", 5, "Starting paper agent...")

    try:
        result = await agent.ainvoke({
            "messages": [("user", user_message)]
        })

        # Extract final AI message
        final_message = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                final_message = msg.content
                break

        logger.info(f"Agent completed. Stats: {stats}")

        return {
            "status": "success",
            "papers_found": stats["papers_found"],
            "papers_analyzed": stats["papers_analyzed"],
            "papers_relevant": stats["papers_relevant"],
            "papers_saved": stats["papers_saved"],
            "final_message": final_message,
        }

    except Exception as e:
        logger.error(f"Paper agent failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "papers_found": stats["papers_found"],
            "papers_analyzed": stats["papers_analyzed"],
            "papers_relevant": stats["papers_relevant"],
            "papers_saved": stats["papers_saved"],
        }


# Backward compatibility alias
def get_paper_workflow():
    """Deprecated: use get_paper_agent() instead."""
    return get_paper_agent()
