"""Autonomous paper agent using LangGraph's create_react_agent."""

import asyncio
import json
from typing import Optional
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from backend.agents.tools import (
    search_arxiv, analyze_paper, check_relevance,
    save_paper, get_user_interests,
    get_user_feedback_summary, check_paper_exists,
    set_task_id, set_selected_interests, set_cancel_event, _send_progress, _stats_ctx,
)

AGENT_SYSTEM_PROMPT = """You are an autonomous research paper agent. Your goal is to discover, analyze, and save high-quality academic papers that match the user's research interests.

WORKFLOW:
1. Call get_user_interests() to get the user's selected interests
2. Call get_user_feedback_summary() to learn from past behavior
3. Call search_arxiv() using ONLY the keywords and categories from get_user_interests()
4. For each promising paper, call check_paper_exists() to skip duplicates
5. For new papers, call check_relevance() first as a quick filter
6. For relevant papers (score >= 0.5), call analyze_paper() for full analysis
7. Only save_paper() for papers with relevance_score >= 0.6

STRICT RULES:
- ONLY search for topics returned by get_user_interests(). Do NOT search for other topics.
- Do NOT use feedback summary to justify searching for different topics.
- If too few results, try variations of the SAME interest keywords (e.g. synonyms), NOT different topics.
- You may increase days_back to find more papers, but keep the same keywords/categories.
- Analyze at most 20 papers per run.
- Save at most 10 papers per run.
- Do not download PDFs during fetch. PDFs are downloaded only after the user clicks the download button.
- Call one tool at a time and wait for its result before calling the next tool.

When done, provide a brief summary of what you found, analyzed, and saved."""


def _create_agent():
    """Create the ReAct paper agent."""
    from backend.core.config import get_settings
    from backend.services.llm_factory import create_llm
    settings = get_settings()

    agent_model = getattr(settings, "llm_agent_model", "") or settings.llm_model
    agent_extra_body = None
    if settings.llm_provider.lower() == "openai":
        if agent_model.lower().startswith("deepseek-v4"):
            agent_extra_body = {"thinking": {"type": "disabled"}}
        elif "reasoner" in agent_model.lower():
            logger.warning(
                f"LLM agent model '{agent_model}' may not support OpenAI tool calling "
                "reliably. Set LLM_AGENT_MODEL to a tool-call-capable chat model if "
                "fetch fails."
            )

    llm = create_llm(temperature=0, model=agent_model, extra_body=agent_extra_body)

    tools = [
        get_user_interests, get_user_feedback_summary,
        search_arxiv, check_paper_exists, check_relevance,
        analyze_paper, save_paper,
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


def _loads_tool_json(raw, default):
    """Parse JSON returned by a LangChain tool."""
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        logger.warning(f"Tool returned non-JSON output: {str(raw)[:200]}...")
        return default


def _interest_list(value) -> list:
    if isinstance(value, list):
        return value
    return []


def _interest_values(interest: dict, key: str) -> list[str]:
    value = interest.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _score(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_tool_calling_compat_error(error: BaseException) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "model_dump",
            "tool_call",
            "tool calls",
            "function_call",
            "function calling",
            "parallel_tool_calls",
            "does not support tools",
            "do not support tools",
            "tools are not supported",
            "unsupported tool",
        )
    )


async def _run_compatibility_fetch(days_back: int, max_results: int) -> dict:
    """Run the fetch workflow without LLM tool calling.

    Some OpenAI-compatible providers can answer normal chat prompts but fail when
    LangGraph uses OpenAI tool calls. This keeps fetch usable for those models.
    """
    await _send_progress(
        "fallback",
        10,
        "Agent tool calling failed; running compatibility fetch workflow...",
    )

    interests_raw = await get_user_interests.ainvoke({})
    interests = _interest_list(_loads_tool_json(interests_raw, []))
    if not interests:
        return {
            "status": "success",
            "papers_found": 0,
            "papers_analyzed": 0,
            "papers_relevant": 0,
            "papers_saved": 0,
            "saved_paper_ids": [],
            "final_message": "No active or selected interests were available.",
        }

    await get_user_feedback_summary.ainvoke({})

    candidates = []
    seen_arxiv_ids = set()
    for interest in interests:
        topic = str(interest.get("topic") or "").strip()
        keywords = _dedupe(([topic] if topic else []) + _interest_values(interest, "keywords"))
        categories = _dedupe(_interest_values(interest, "categories"))

        search_raw = await search_arxiv.ainvoke({
            "keywords": keywords,
            "categories": categories,
            "days_back": days_back,
            "max_results": max_results,
        })
        search_result = _loads_tool_json(search_raw, [])
        if isinstance(search_result, dict):
            logger.warning(f"Compatibility search skipped: {search_result.get('error')}")
            continue

        for paper in search_result:
            arxiv_id = paper.get("arxiv_id")
            if not arxiv_id or arxiv_id in seen_arxiv_ids:
                continue
            seen_arxiv_ids.add(arxiv_id)
            candidates.append(paper)

    analyzed = 0
    for paper in candidates:
        stats = _stats_ctx.get() or {}
        if analyzed >= 20 or stats.get("papers_saved", 0) >= 10:
            break

        exists_raw = await check_paper_exists.ainvoke({"arxiv_id": paper["arxiv_id"]})
        exists = _loads_tool_json(exists_raw, {})
        if isinstance(exists, dict) and exists.get("exists"):
            continue

        relevance_raw = await check_relevance.ainvoke({
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "categories": paper.get("categories", []),
        })
        relevance = _loads_tool_json(relevance_raw, {})
        if _score(relevance.get("score")) < 0.5:
            continue

        analysis_raw = await analyze_paper.ainvoke({
            "arxiv_id": paper.get("arxiv_id", ""),
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": paper.get("authors", []),
            "categories": paper.get("categories", []),
        })
        analysis = _loads_tool_json(analysis_raw, {})
        if not isinstance(analysis, dict) or analysis.get("error"):
            continue

        analyzed += 1
        relevance_score = _score(analysis.get("relevance_score"))
        if relevance_score < 0.6:
            continue

        await save_paper.ainvoke({
            "arxiv_id": paper.get("arxiv_id", ""),
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": paper.get("authors", []),
            "categories": paper.get("categories", []),
            "published_date": paper.get("published_date", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "ai_summary": analysis.get("summary", ""),
            "ai_summary_zh": analysis.get("summary_zh", ""),
            "key_findings": analysis.get("key_findings", []),
            "relevance_score": relevance_score,
            "relevance_reason": analysis.get("relevance_reason", ""),
        })

    stats = _stats_ctx.get() or {}
    await _send_progress(
        "complete",
        95,
        f"Fetch completed: saved {stats.get('papers_saved', 0)} papers",
    )
    return {
        "status": "success",
        "papers_found": stats.get("papers_found", 0),
        "papers_analyzed": stats.get("papers_analyzed", 0),
        "papers_relevant": stats.get("papers_relevant", 0),
        "papers_saved": stats.get("papers_saved", 0),
        "saved_paper_ids": stats.get("saved_paper_ids", []),
        "final_message": (
            "Compatibility fetch completed after the LLM provider rejected "
            "agent tool calling."
        ),
    }


async def run_paper_agent(
    interests_data: list[dict],
    days_back: int = 7,
    max_results: int = 30,
    task_id: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> dict:
    """Run the autonomous paper agent.

    Args:
        interests_data: List of user interest dicts
        days_back: How many days back to search
        max_results: Max results per search
        task_id: WebSocket task ID for progress updates
        cancel_event: Event to signal cancellation

    Returns:
        Dict with status, stats, and final message
    """
    set_task_id(task_id)
    set_selected_interests(interests_data)
    if cancel_event:
        set_cancel_event(cancel_event)

    # Initialize stats in context
    stats = {
        "papers_found": 0,
        "papers_analyzed": 0,
        "papers_relevant": 0,
        "papers_saved": 0,
        "saved_paper_ids": [],
    }
    _stats_ctx.set(stats)

    agent = get_paper_agent()

    user_message = f"""Find and process papers for the user.

Search parameters: days_back={days_back}, max_results={max_results}

Start by getting the user's interests and feedback summary, then search for papers,
analyze the most promising ones, and save the best matching paper metadata."""

    await _send_progress("start", 5, "Starting paper agent...")

    try:
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [HumanMessage(content=user_message)]}),
            timeout=300,  # 5 minute timeout
        )

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
            "saved_paper_ids": stats["saved_paper_ids"],
            "final_message": final_message,
        }

    except asyncio.CancelledError as e:
        error_msg = str(e) or "Agent was cancelled"
        logger.error(f"Paper agent cancelled: {error_msg}")
        return {
            "status": "failed",
            "error": error_msg,
            "papers_found": stats["papers_found"],
            "papers_analyzed": stats["papers_analyzed"],
            "papers_relevant": stats["papers_relevant"],
            "papers_saved": stats["papers_saved"],
            "saved_paper_ids": stats["saved_paper_ids"],
        }
    except Exception as e:
        error_msg = str(e) or type(e).__name__
        if not error_msg or error_msg == "CancelledError":
            error_msg = "Agent timed out or was cancelled"
        logger.exception(f"Paper agent failed: {error_msg}")

        if _is_tool_calling_compat_error(e):
            try:
                logger.warning("Falling back to compatibility fetch workflow")
                fallback_result = await _run_compatibility_fetch(days_back, max_results)
                fallback_result["agent_error"] = error_msg
                return fallback_result
            except asyncio.CancelledError as fallback_cancelled:
                fallback_error = str(fallback_cancelled) or "Compatibility fetch was cancelled"
                logger.error(f"Compatibility fetch cancelled: {fallback_error}")
                return {
                    "status": "failed",
                    "error": fallback_error,
                    "papers_found": stats["papers_found"],
                    "papers_analyzed": stats["papers_analyzed"],
                    "papers_relevant": stats["papers_relevant"],
                    "papers_saved": stats["papers_saved"],
                    "saved_paper_ids": stats["saved_paper_ids"],
                }
            except Exception as fallback_error:
                logger.exception(f"Compatibility fetch failed: {fallback_error}")
                error_msg = f"{error_msg}; compatibility fallback failed: {fallback_error}"

        return {
            "status": "failed",
            "error": error_msg,
            "papers_found": stats["papers_found"],
            "papers_analyzed": stats["papers_analyzed"],
            "papers_relevant": stats["papers_relevant"],
            "papers_saved": stats["papers_saved"],
            "saved_paper_ids": stats["saved_paper_ids"],
        }


# Backward compatibility alias
def get_paper_workflow():
    """Deprecated: use get_paper_agent() instead."""
    return get_paper_agent()
