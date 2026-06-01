"""Explicit paper discovery workflow built with LangGraph StateGraph."""

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger
from sqlalchemy import select

from backend.agents.tools import (
    _send_progress,
    _stats_ctx,
    check_cancelled,
    get_user_feedback_summary,
    set_cancel_event,
    set_selected_interests,
    set_task_id,
)


ANALYZE_LIMIT = 20
SAVE_LIMIT = 10
QUICK_RELEVANCE_THRESHOLD = 0.5
SAVE_RELEVANCE_THRESHOLD = 0.6
LOCAL_ANALYZE_THRESHOLD = 0.2
LOCAL_LLM_FALLBACK_SAVE_THRESHOLD = 0.82
WORKFLOW_RECURSION_LIMIT = 2000


class PaperAgentState(TypedDict, total=False):
    """State carried through the explicit paper workflow."""

    interests_data: list[dict]
    interests: list[dict]
    feedback: dict
    query_plans: list[dict]
    candidates: list[dict]
    new_candidates: list[dict]
    ranked_candidates: list[dict]
    relevant_candidates: list[dict]
    decisions: list[dict]
    errors: list[dict]
    fallbacks_used: list[str]
    stats: dict
    days_back: int
    max_results: int
    source: str
    generate_report: bool
    current_plan_index: int
    current_attempt_index: int
    current_attempt_found: bool
    scored_candidates: list[dict]
    current_candidate_index: int
    current_analyze_index: int
    current_save_index: int
    fetch_log_id: int | None
    report_id: int | None
    report_status: str | None
    report_error: str | None
    status: str
    final_message: str


_workflow = None


def get_paper_agent():
    """Get or create the explicit paper workflow singleton."""
    global _workflow
    if _workflow is None:
        _workflow = _create_workflow()
    return _workflow


def _create_workflow():
    workflow = StateGraph(PaperAgentState)
    workflow.add_node("load_context", _load_context)
    workflow.add_node("build_query_plan", _build_query_plan)
    workflow.add_node("init_search_loop", _init_search_loop)
    workflow.add_node("search_attempt", _search_attempt)
    workflow.add_node("next_search_attempt", _next_search_attempt)
    workflow.add_node("next_query_plan", _next_query_plan)
    workflow.add_node("exhaust_query_plan", _exhaust_query_plan)
    workflow.add_node("search_candidates", _search_candidates)
    workflow.add_node("dedupe_and_check_existing", _dedupe_and_check_existing)
    workflow.add_node("init_rank_loop", _init_rank_loop)
    workflow.add_node("score_one_candidate", _score_one_candidate)
    workflow.add_node("finalize_ranking", _finalize_ranking)
    workflow.add_node("init_analysis_loop", _init_analysis_loop)
    workflow.add_node("analyze_one_candidate", _analyze_one_candidate)
    workflow.add_node("finalize_analysis", _finalize_analysis)
    workflow.add_node("init_save_loop", _init_save_loop)
    workflow.add_node("save_one_paper", _save_one_paper)
    workflow.add_node("mark_save_limit", _mark_save_limit)
    workflow.add_node("finalize_discovery", _finalize_discovery)
    workflow.add_node("persist_fetch_log", _persist_fetch_log)
    workflow.add_node("generate_report", _generate_report)
    workflow.add_node("complete_run", _complete_run)

    workflow.set_entry_point("load_context")
    workflow.add_conditional_edges(
        "load_context",
        _route_after_load_context,
        {
            "has_interests": "build_query_plan",
            "finalize": "finalize_discovery",
        },
    )
    workflow.add_conditional_edges(
        "build_query_plan",
        _route_after_build_query_plan,
        {
            "has_query_plans": "init_search_loop",
            "finalize": "finalize_discovery",
        },
    )
    workflow.add_edge("init_search_loop", "search_attempt")
    workflow.add_conditional_edges(
        "search_attempt",
        _route_after_search_attempt,
        {
            "next_plan": "next_query_plan",
            "next_attempt": "next_search_attempt",
            "exhaust_plan": "exhaust_query_plan",
        },
    )
    workflow.add_edge("next_search_attempt", "search_attempt")
    workflow.add_conditional_edges(
        "next_query_plan",
        _route_query_plan_loop,
        {
            "search_attempt": "search_attempt",
            "finish_search": "search_candidates",
        },
    )
    workflow.add_conditional_edges(
        "exhaust_query_plan",
        _route_query_plan_loop,
        {
            "search_attempt": "search_attempt",
            "finish_search": "search_candidates",
        },
    )
    workflow.add_edge("search_candidates", "dedupe_and_check_existing")
    workflow.add_edge("dedupe_and_check_existing", "init_rank_loop")
    workflow.add_conditional_edges(
        "init_rank_loop",
        _route_rank_loop,
        {
            "score_candidate": "score_one_candidate",
            "finalize_ranking": "finalize_ranking",
        },
    )
    workflow.add_conditional_edges(
        "score_one_candidate",
        _route_rank_loop,
        {
            "score_candidate": "score_one_candidate",
            "finalize_ranking": "finalize_ranking",
        },
    )
    workflow.add_edge("finalize_ranking", "init_analysis_loop")
    workflow.add_conditional_edges(
        "init_analysis_loop",
        _route_analysis_loop,
        {
            "analyze_candidate": "analyze_one_candidate",
            "finalize_analysis": "finalize_analysis",
        },
    )
    workflow.add_conditional_edges(
        "analyze_one_candidate",
        _route_analysis_loop,
        {
            "analyze_candidate": "analyze_one_candidate",
            "finalize_analysis": "finalize_analysis",
        },
    )
    workflow.add_edge("finalize_analysis", "init_save_loop")
    workflow.add_conditional_edges(
        "init_save_loop",
        _route_save_loop,
        {
            "save_paper": "save_one_paper",
            "mark_save_limit": "mark_save_limit",
            "finalize": "finalize_discovery",
        },
    )
    workflow.add_conditional_edges(
        "save_one_paper",
        _route_save_loop,
        {
            "save_paper": "save_one_paper",
            "mark_save_limit": "mark_save_limit",
            "finalize": "finalize_discovery",
        },
    )
    workflow.add_edge("mark_save_limit", "finalize_discovery")
    workflow.add_edge("finalize_discovery", "persist_fetch_log")
    workflow.add_conditional_edges(
        "persist_fetch_log",
        _route_after_persist_fetch_log,
        {
            "generate_report": "generate_report",
            "complete_run": "complete_run",
        },
    )
    workflow.add_edge("generate_report", "complete_run")
    workflow.add_edge("complete_run", END)
    return workflow.compile()


def _empty_stats() -> dict:
    return {
        "papers_found": 0,
        "papers_analyzed": 0,
        "papers_relevant": 0,
        "papers_saved": 0,
        "saved_paper_ids": [],
    }


def _ensure_state_defaults(state: PaperAgentState) -> PaperAgentState:
    state.setdefault("interests", [])
    state.setdefault("feedback", {})
    state.setdefault("query_plans", [])
    state.setdefault("candidates", [])
    state.setdefault("new_candidates", [])
    state.setdefault("scored_candidates", [])
    state.setdefault("ranked_candidates", [])
    state.setdefault("relevant_candidates", [])
    state.setdefault("decisions", [])
    state.setdefault("errors", [])
    state.setdefault("fallbacks_used", [])
    state.setdefault("stats", _empty_stats())
    state.setdefault("source", "manual")
    state.setdefault("generate_report", True)
    state.setdefault("fetch_log_id", None)
    state.setdefault("report_id", None)
    state.setdefault("report_status", None)
    state.setdefault("report_error", None)
    return state


def _record_decision(
    state: PaperAgentState,
    *,
    stage: str,
    action: str,
    reason: str,
    arxiv_id: str | None = None,
    score: float | None = None,
    extra: Optional[dict] = None,
) -> None:
    decision = {
        "stage": stage,
        "action": action,
        "reason": reason,
    }
    if arxiv_id:
        decision["arxiv_id"] = arxiv_id
    if score is not None:
        decision["score"] = round(float(score), 4)
    if extra:
        decision.update(extra)
    state.setdefault("decisions", []).append(decision)


def _record_error(
    state: PaperAgentState,
    *,
    stage: str,
    message: str,
    arxiv_id: str | None = None,
    recoverable: bool = True,
) -> None:
    error = {
        "stage": stage,
        "message": message,
        "recoverable": recoverable,
    }
    if arxiv_id:
        error["arxiv_id"] = arxiv_id
    state.setdefault("errors", []).append(error)


def _record_fallback(state: PaperAgentState, fallback: str) -> None:
    fallbacks = state.setdefault("fallbacks_used", [])
    if fallback not in fallbacks:
        fallbacks.append(fallback)


def _loads_tool_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        logger.warning(f"Tool returned non-JSON output: {str(raw)[:200]}...")
        return default


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen = set()
    result = []
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _interest_keywords(interest: dict) -> list[str]:
    topic = str(interest.get("topic") or "").strip()
    keywords = ([topic] if topic else []) + _as_list(interest.get("keywords"))
    return _dedupe_strings(keywords)


def _interest_categories(interest: dict) -> list[str]:
    return _dedupe_strings(_as_list(interest.get("categories")))


def _interest_payload_for_llm(interests: list[dict]) -> list[dict]:
    return [
        {
            "id": interest.get("id"),
            "topic": interest.get("topic") or "",
            "description": interest.get("description") or "",
            "keywords": _as_list(interest.get("keywords")),
            "categories": _as_list(interest.get("categories")),
            "weight": interest.get("weight", 1.0),
        }
        for interest in interests
    ]


async def _load_context(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    interests = state.get("interests_data") or []
    state["interests"] = interests

    if not interests:
        _record_decision(
            state,
            stage="load_context",
            action="skipped",
            reason="No active or selected interests were provided.",
        )
        return state

    try:
        feedback_raw = await get_user_feedback_summary.ainvoke({})
        feedback = _loads_tool_json(feedback_raw, {})
        state["feedback"] = feedback if isinstance(feedback, dict) else {}
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(state, stage="load_context", message=f"Feedback summary failed: {e}")
        state["feedback"] = {}

    await _send_progress("plan", 10, f"Loaded {len(interests)} research interests")
    return state


async def _build_query_plan(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    query_plans = []
    days_back = int(state.get("days_back") or 7)

    for index, interest in enumerate(state.get("interests", [])):
        topic = str(interest.get("topic") or "").strip()
        keywords = _interest_keywords(interest)
        categories = _interest_categories(interest)

        if not keywords and not categories:
            _record_decision(
                state,
                stage="build_query_plan",
                action="skipped_interest",
                reason="Interest has neither keywords nor arXiv categories.",
                extra={"interest_id": interest.get("id"), "interest_topic": topic},
            )
            continue

        attempts = []
        _append_search_attempt(
            attempts,
            mode="primary",
            keywords=keywords,
            categories=categories,
            days_back=days_back,
        )
        if categories and keywords:
            _append_search_attempt(
                attempts,
                mode="category_only",
                keywords=[],
                categories=categories,
                days_back=days_back,
            )
            _append_search_attempt(
                attempts,
                mode="keyword_only",
                keywords=keywords,
                categories=[],
                days_back=days_back,
            )

        expanded_days = min(max(days_back * 3, days_back + 14), 90)
        if expanded_days > days_back:
            _append_search_attempt(
                attempts,
                mode="expanded_days",
                keywords=keywords,
                categories=categories,
                days_back=expanded_days,
            )
            if categories and not keywords:
                _append_search_attempt(
                    attempts,
                    mode="expanded_category_only",
                    keywords=[],
                    categories=categories,
                    days_back=expanded_days,
                )
            if keywords and not categories:
                _append_search_attempt(
                    attempts,
                    mode="expanded_keyword_only",
                    keywords=keywords,
                    categories=[],
                    days_back=expanded_days,
                )

        query_plans.append(
            {
                "interest_index": index,
                "interest_id": interest.get("id"),
                "topic": topic,
                "keywords": keywords,
                "categories": categories,
                "attempts": attempts,
            }
        )

    state["query_plans"] = query_plans
    await _send_progress("plan", 12, f"Built {len(query_plans)} scoped arXiv query plans")
    return state


def _append_search_attempt(
    attempts: list[dict],
    *,
    mode: str,
    keywords: list[str],
    categories: list[str],
    days_back: int,
) -> None:
    key = (
        tuple(kw.casefold() for kw in keywords),
        tuple(cat.casefold() for cat in categories),
        days_back,
    )
    for attempt in attempts:
        existing_key = (
            tuple(kw.casefold() for kw in attempt["keywords"]),
            tuple(cat.casefold() for cat in attempt["categories"]),
            attempt["days_back"],
        )
        if existing_key == key:
            return
    attempts.append(
        {
            "mode": mode,
            "keywords": keywords,
            "categories": categories,
            "days_back": days_back,
        }
    )


def _route_after_load_context(state: PaperAgentState) -> str:
    return "has_interests" if state.get("interests") else "finalize"


def _route_after_build_query_plan(state: PaperAgentState) -> str:
    return "has_query_plans" if state.get("query_plans") else "finalize"


async def _init_search_loop(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    state["current_plan_index"] = 0
    state["current_attempt_index"] = 0
    state["current_attempt_found"] = False
    state["candidates"] = []
    await _send_progress("fetch", 15, "Searching arXiv with scoped query plans...")
    return state


async def _search_attempt(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    plan = _current_query_plan(state)
    attempt = _current_search_attempt(state)
    state["current_attempt_found"] = False

    if not plan or not attempt:
        return state

    attempt_index = int(state.get("current_attempt_index") or 0)
    if attempt_index > 0:
        _record_fallback(state, attempt["mode"])

    try:
        papers = await _search_arxiv_attempt(
            attempt=attempt,
            max_results=int(state.get("max_results") or 30),
            plan=plan,
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(
            state,
            stage="search_attempt",
            message=f"Search failed for {plan.get('topic') or plan.get('interest_id')}: {e}",
        )
        state["current_attempt_index"] = len(plan.get("attempts", []))
        return state

    if not papers:
        _record_decision(
            state,
            stage="search_attempt",
            action="no_results",
            reason=f"No papers returned for {attempt['mode']} search.",
            extra={
                "interest_id": plan.get("interest_id"),
                "interest_topic": plan.get("topic"),
                "query_mode": attempt["mode"],
            },
        )
        return state

    state["current_attempt_found"] = True
    _merge_search_results(state, papers, plan, attempt)
    if attempt_index > 0:
        _record_decision(
            state,
            stage="search_attempt",
            action="fallback_succeeded",
            reason=f"Search fallback {attempt['mode']} returned papers.",
            extra={
                "interest_id": plan.get("interest_id"),
                "interest_topic": plan.get("topic"),
                "query_mode": attempt["mode"],
                "count": len(papers),
            },
        )
    return state


def _route_after_search_attempt(state: PaperAgentState) -> str:
    if state.get("current_attempt_found"):
        return "next_plan"

    plan = _current_query_plan(state)
    if not plan:
        return "exhaust_plan"

    next_attempt_index = int(state.get("current_attempt_index") or 0) + 1
    if next_attempt_index < len(plan.get("attempts", [])):
        return "next_attempt"
    return "exhaust_plan"


async def _next_search_attempt(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state["current_attempt_index"] = int(state.get("current_attempt_index") or 0) + 1
    state["current_attempt_found"] = False
    return state


async def _next_query_plan(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state["current_plan_index"] = int(state.get("current_plan_index") or 0) + 1
    state["current_attempt_index"] = 0
    state["current_attempt_found"] = False
    return state


async def _exhaust_query_plan(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    plan = _current_query_plan(state)
    if plan:
        _record_decision(
            state,
            stage="search_attempt",
            action="exhausted",
            reason="All scoped search attempts returned no papers.",
            extra={"interest_id": plan.get("interest_id"), "interest_topic": plan.get("topic")},
        )
    state["current_plan_index"] = int(state.get("current_plan_index") or 0) + 1
    state["current_attempt_index"] = 0
    state["current_attempt_found"] = False
    return state


def _route_query_plan_loop(state: PaperAgentState) -> str:
    if int(state.get("current_plan_index") or 0) >= len(state.get("query_plans", [])):
        return "finish_search"
    return "search_attempt"


def _current_query_plan(state: PaperAgentState) -> Optional[dict]:
    plans = state.get("query_plans", [])
    index = int(state.get("current_plan_index") or 0)
    if index < 0 or index >= len(plans):
        return None
    return plans[index]


def _current_search_attempt(state: PaperAgentState) -> Optional[dict]:
    plan = _current_query_plan(state)
    if not plan:
        return None
    attempts = plan.get("attempts", [])
    index = int(state.get("current_attempt_index") or 0)
    if index < 0 or index >= len(attempts):
        return None
    return attempts[index]


def _merge_search_results(
    state: PaperAgentState,
    papers: list[dict],
    plan: dict,
    attempt: dict,
) -> None:
    candidate_map = {
        candidate["arxiv_id"]: candidate
        for candidate in state.setdefault("candidates", [])
        if candidate.get("arxiv_id")
    }

    for paper in papers:
        arxiv_id = paper.get("arxiv_id")
        if not arxiv_id:
            continue

        if arxiv_id not in candidate_map:
            paper["source_interest_ids"] = []
            paper["source_interest_topics"] = []
            paper["query_modes"] = []
            candidate_map[arxiv_id] = paper
            state["candidates"].append(paper)

        candidate = candidate_map[arxiv_id]
        if plan.get("interest_id") not in candidate["source_interest_ids"]:
            candidate["source_interest_ids"].append(plan.get("interest_id"))
        if plan.get("topic") not in candidate["source_interest_topics"]:
            candidate["source_interest_topics"].append(plan.get("topic"))
        if attempt["mode"] not in candidate["query_modes"]:
            candidate["query_modes"].append(attempt["mode"])


async def _search_candidates(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    candidates = state.get("candidates", [])
    state["stats"]["papers_found"] = len(candidates)
    await _send_progress("fetch", 30, f"Found {len(candidates)} unique candidate papers")
    return state


async def _search_arxiv_attempt(
    *,
    attempt: dict,
    max_results: int,
    plan: dict,
) -> list[dict]:
    keywords = attempt.get("keywords") or []
    categories = attempt.get("categories") or []
    if not keywords and not categories:
        return []

    progress_terms = keywords[:3] or categories[:3] or [plan.get("topic") or "selected interest"]
    await _send_progress("fetch", 18, f"Searching arXiv: {', '.join(progress_terms)}...")

    from backend.services.arxiv_service import get_arxiv_service

    arxiv_service = get_arxiv_service()
    papers = await arxiv_service.search_papers(
        categories=categories if categories else None,
        keywords=keywords if keywords else None,
        days_back=int(attempt.get("days_back") or 7),
        max_results=max_results,
    )

    results = []
    seen = set()
    for paper in papers:
        info = arxiv_service.extract_paper_info(paper)
        arxiv_id = info["arxiv_id"]
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        results.append(
            {
                "arxiv_id": arxiv_id,
                "title": info["title"],
                "abstract": info["abstract"],
                "authors": info["authors"],
                "categories": info["categories"],
                "primary_category": info.get("primary_category"),
                "pdf_url": info["pdf_url"],
                "published_date": str(info["published_date"]),
                "updated_date": str(info.get("updated_date") or ""),
                "query_mode": attempt["mode"],
                "query_keywords": keywords,
                "query_categories": categories,
                "query_days_back": attempt.get("days_back"),
            }
        )
    return results


async def _dedupe_and_check_existing(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    candidates = state.get("candidates", [])
    if not candidates:
        state["new_candidates"] = []
        return state

    ids = [candidate["arxiv_id"] for candidate in candidates if candidate.get("arxiv_id")]
    existing_ids: set[str] = set()

    try:
        from backend.models.database import Paper, get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(Paper.arxiv_id).where(Paper.arxiv_id.in_(ids)))
            existing_ids = set(result.scalars().all())
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(state, stage="dedupe", message=f"Duplicate lookup failed: {e}")

    new_candidates = []
    for candidate in candidates:
        arxiv_id = candidate.get("arxiv_id")
        if arxiv_id in existing_ids:
            _record_decision(
                state,
                stage="dedupe",
                action="duplicate",
                arxiv_id=arxiv_id,
                reason="Paper already exists in the database.",
            )
            continue
        new_candidates.append(candidate)

    state["new_candidates"] = new_candidates
    await _send_progress("filter", 35, f"{len(new_candidates)} new papers after duplicate check")
    return state


async def _init_rank_loop(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    state["current_candidate_index"] = 0
    state["scored_candidates"] = []
    return state


def _route_rank_loop(state: PaperAgentState) -> str:
    index = int(state.get("current_candidate_index") or 0)
    if index >= len(state.get("new_candidates", [])):
        return "finalize_ranking"
    return "score_candidate"


async def _score_one_candidate(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    index = int(state.get("current_candidate_index") or 0)
    candidates = state.get("new_candidates", [])
    if index >= len(candidates):
        return state

    candidate = candidates[index]
    score_info = _score_candidate(candidate, state.get("interests", []))
    candidate.update(score_info)

    if score_info["local_score"] < LOCAL_ANALYZE_THRESHOLD:
        _record_decision(
            state,
            stage="rank",
            action="skipped",
            arxiv_id=candidate.get("arxiv_id"),
            score=score_info["local_score"],
            reason=score_info["local_reason"],
        )
    else:
        state.setdefault("scored_candidates", []).append(candidate)

    state["current_candidate_index"] = index + 1
    return state


async def _finalize_ranking(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    scored = state.get("scored_candidates", [])
    scored.sort(
        key=lambda item: (
            item.get("local_score", 0.0),
            _published_sort_key(item.get("published_date")),
        ),
        reverse=True,
    )

    overflow = scored[ANALYZE_LIMIT:]
    for candidate in overflow:
        _record_decision(
            state,
            stage="rank",
            action="skipped",
            arxiv_id=candidate.get("arxiv_id"),
            score=candidate.get("local_score"),
            reason=f"Skipped because analyze limit is {ANALYZE_LIMIT} papers per run.",
        )

    state["ranked_candidates"] = scored[:ANALYZE_LIMIT]
    await _send_progress("filter", 38, f"Ranked {len(state['ranked_candidates'])} papers for LLM analysis")
    return state


def _published_sort_key(value: Any) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.timestamp()
    except Exception:
        return 0.0


def _score_candidate(candidate: dict, interests: list[dict]) -> dict:
    title = candidate.get("title") or ""
    abstract = candidate.get("abstract") or ""
    text = _normalize_text(f"{title}\n{abstract}")
    title_text = _normalize_text(title)
    text_tokens = set(_tokens(text))
    paper_categories = {str(cat).casefold() for cat in candidate.get("categories") or []}

    best_score = 0.0
    best_reason = "No local interest signals matched."
    best_interest_ids = []
    best_keywords = []
    best_categories = []

    for interest in interests:
        keywords = _interest_keywords(interest)
        categories = _interest_categories(interest)
        matched_keywords = [kw for kw in keywords if _normalize_text(kw) in text]
        matched_title_keywords = [kw for kw in keywords if _normalize_text(kw) in title_text]
        matched_categories = [
            cat for cat in categories if str(cat).casefold() in paper_categories
        ]

        topic = str(interest.get("topic") or "")
        topic_signal = 0.0
        topic_norm = _normalize_text(topic)
        if topic_norm and topic_norm in text:
            topic_signal = 1.0
        elif topic_norm:
            topic_tokens = set(_tokens(topic_norm))
            if topic_tokens:
                topic_signal = len(topic_tokens & text_tokens) / len(topic_tokens)

        keyword_denominator = max(1, min(len(keywords), 3))
        keyword_signal = min(len(matched_keywords) / keyword_denominator, 1.0)
        category_signal = 1.0 if matched_categories else 0.0
        title_signal = 1.0 if matched_title_keywords else 0.0

        base_score = (
            0.45 * keyword_signal
            + 0.25 * topic_signal
            + 0.25 * category_signal
            + 0.05 * title_signal
        )
        if category_signal and (keyword_signal or topic_signal):
            base_score = max(base_score, 0.65)
        elif keyword_signal or topic_signal:
            base_score = max(base_score, 0.45)
        elif category_signal:
            base_score = max(base_score, 0.55)

        weight = min(max(_safe_float(interest.get("weight"), 1.0), 0.5), 1.25)
        score = min(base_score * weight, 1.0)
        if score > best_score:
            interest_label = interest.get("topic") or interest.get("id") or "selected interest"
            reason_parts = []
            if matched_keywords:
                reason_parts.append(f"keywords: {', '.join(matched_keywords[:5])}")
            if matched_categories:
                reason_parts.append(f"categories: {', '.join(matched_categories[:5])}")
            if topic_signal and not matched_keywords:
                reason_parts.append("topic overlap")
            if not reason_parts:
                reason_parts.append("weak local overlap")

            best_score = score
            best_reason = f"Matched {interest_label} via {'; '.join(reason_parts)}."
            best_interest_ids = [interest.get("id")] if interest.get("id") is not None else []
            best_keywords = matched_keywords
            best_categories = matched_categories

    return {
        "local_score": round(best_score, 4),
        "local_reason": best_reason,
        "matched_interest_ids": best_interest_ids,
        "matched_keywords": best_keywords,
        "matched_categories": best_categories,
    }


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9.+_-]*", value.casefold())


async def _init_analysis_loop(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    state["current_analyze_index"] = 0
    state["relevant_candidates"] = []
    return state


def _route_analysis_loop(state: PaperAgentState) -> str:
    index = int(state.get("current_analyze_index") or 0)
    if index >= len(state.get("ranked_candidates", [])):
        return "finalize_analysis"
    return "analyze_candidate"


async def _analyze_one_candidate(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    index = int(state.get("current_analyze_index") or 0)
    ranked = state.get("ranked_candidates", [])
    if index >= len(ranked):
        return state

    candidate = ranked[index]
    progress = 40 + int(((index + 1) / max(len(ranked), 1)) * 25)
    await _send_progress("analyze", progress, f"Analyzing: {candidate.get('title', '')[:40]}...")

    try:
        analysis = await _analyze_candidate(candidate, state.get("interests", []))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(
            state,
            stage="analyze",
            arxiv_id=candidate.get("arxiv_id"),
            message=f"Analysis failed: {e}",
        )
        _record_decision(
            state,
            stage="analyze",
            action="failed",
            arxiv_id=candidate.get("arxiv_id"),
            reason="Analysis failed and the paper was skipped.",
        )
        state["current_analyze_index"] = index + 1
        return state

    candidate["analysis"] = analysis
    state["stats"]["papers_analyzed"] += 1
    score = _safe_float(analysis.get("relevance_score"))

    if score >= SAVE_RELEVANCE_THRESHOLD:
        state["stats"]["papers_relevant"] += 1
        state.setdefault("relevant_candidates", []).append(candidate)
        _record_decision(
            state,
            stage="analyze",
            action="relevant",
            arxiv_id=candidate.get("arxiv_id"),
            score=score,
            reason=analysis.get("relevance_reason") or "Passed relevance threshold.",
        )
    elif score >= QUICK_RELEVANCE_THRESHOLD:
        _record_decision(
            state,
            stage="analyze",
            action="not_saved",
            arxiv_id=candidate.get("arxiv_id"),
            score=score,
            reason="Paper was somewhat relevant but below the save threshold.",
        )
    else:
        _record_decision(
            state,
            stage="analyze",
            action="skipped",
            arxiv_id=candidate.get("arxiv_id"),
            score=score,
            reason=analysis.get("relevance_reason") or "Below relevance threshold.",
        )

    state["current_analyze_index"] = index + 1
    return state


async def _finalize_analysis(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    state["relevant_candidates"].sort(
        key=lambda item: item.get("analysis", {}).get("relevance_score", 0.0),
        reverse=True,
    )
    return state


async def _analyze_candidate(candidate: dict, interests: list[dict]) -> dict:
    from backend.services.llm_service import get_llm_service

    llm_service = get_llm_service()
    interest_payload = _interest_payload_for_llm(interests)
    summary, relevance = await asyncio.gather(
        llm_service.generate_summary(
            title=candidate.get("title", ""),
            abstract=candidate.get("abstract", ""),
            authors=candidate.get("authors", []),
            categories=candidate.get("categories", []),
        ),
        llm_service.check_relevance(
            title=candidate.get("title", ""),
            abstract=candidate.get("abstract", ""),
            categories=candidate.get("categories", []),
            interests=interest_payload,
        ),
    )

    relevance_failed = _relevance_failed(relevance)
    summary_failed = _summary_failed(summary)
    local_score = _safe_float(candidate.get("local_score"))

    if relevance_failed and local_score >= LOCAL_LLM_FALLBACK_SAVE_THRESHOLD:
        relevance_score = min(max(local_score, SAVE_RELEVANCE_THRESHOLD), 0.7)
        relevance_reason = (
            "LLM relevance check failed; strong scoped local signals were used as a "
            f"conservative fallback. {candidate.get('local_reason', '')}"
        )
        is_relevant = True
        fallback_used = "local_relevance_after_llm_failure"
    elif relevance_failed:
        relevance_score = 0.0
        relevance_reason = (
            "LLM relevance check failed and local signals were not strong enough "
            "for conservative fallback saving."
        )
        is_relevant = False
        fallback_used = "skip_after_llm_failure"
    else:
        relevance_score = _safe_float(relevance.score)
        relevance_reason = relevance.reason
        is_relevant = bool(relevance.is_relevant)
        fallback_used = None

    summary_text = summary.summary
    summary_zh = summary.summary_zh
    key_findings = summary.key_findings
    methodology = summary.methodology
    if summary_failed:
        summary_text = _fallback_summary(candidate)
        summary_zh = ""
        key_findings = []
        methodology = "Unknown"

    return {
        "summary": summary_text,
        "summary_zh": summary_zh,
        "key_findings": key_findings,
        "methodology": methodology,
        "relevance_score": relevance_score,
        "relevance_reason": relevance_reason,
        "is_relevant": is_relevant,
        "fallback_used": fallback_used,
        "summary_fallback_used": summary_failed,
        "local_score": local_score,
        "local_reason": candidate.get("local_reason"),
        "matched_interest_ids": candidate.get("matched_interest_ids", []),
    }


def _relevance_failed(relevance: Any) -> bool:
    reason = str(getattr(relevance, "reason", "") or "").casefold()
    score = _safe_float(getattr(relevance, "score", 0.0))
    return (
        reason.startswith("error:")
        or "unable to determine relevance" in reason
        or ("failed" in reason and score <= 0.0)
    )


def _summary_failed(summary: Any) -> bool:
    findings = getattr(summary, "key_findings", None) or []
    return any(str(item).casefold() == "summary generation failed" for item in findings)


def _fallback_summary(candidate: dict) -> str:
    abstract = str(candidate.get("abstract") or "").strip()
    if len(abstract) <= 350:
        return abstract
    return abstract[:350].rstrip() + "..."


async def _init_save_loop(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    state["current_save_index"] = 0
    await _send_progress("save", 70, "Saving relevant papers...")
    return state


def _route_save_loop(state: PaperAgentState) -> str:
    index = int(state.get("current_save_index") or 0)
    relevant = state.get("relevant_candidates", [])
    if index >= len(relevant):
        return "finalize"
    if state.get("stats", {}).get("papers_saved", 0) >= SAVE_LIMIT:
        return "mark_save_limit"
    return "save_paper"


async def _mark_save_limit(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    index = int(state.get("current_save_index") or 0)
    relevant = state.get("relevant_candidates", [])
    for candidate in relevant[index:]:
        _record_decision(
            state,
            stage="save",
            action="skipped",
            arxiv_id=candidate.get("arxiv_id"),
            score=candidate.get("analysis", {}).get("relevance_score"),
            reason=f"Skipped because save limit is {SAVE_LIMIT} papers per run.",
        )
    state["current_save_index"] = len(relevant)
    return state


async def _save_one_paper(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    index = int(state.get("current_save_index") or 0)
    relevant = state.get("relevant_candidates", [])
    if index >= len(relevant):
        return state

    candidate = relevant[index]
    try:
        save_result = await _save_candidate(candidate)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(
            state,
            stage="save",
            arxiv_id=candidate.get("arxiv_id"),
            message=f"Save failed: {e}",
        )
        _record_decision(
            state,
            stage="save",
            action="failed",
            arxiv_id=candidate.get("arxiv_id"),
            reason="Database save failed; workflow continued.",
        )
        state["current_save_index"] = index + 1
        return state

    status = save_result.get("status")
    if status == "saved":
        paper_id = save_result["paper_id"]
        state["stats"]["papers_saved"] += 1
        state["stats"].setdefault("saved_paper_ids", []).append(paper_id)
        _record_decision(
            state,
            stage="save",
            action="saved",
            arxiv_id=candidate.get("arxiv_id"),
            score=candidate.get("analysis", {}).get("relevance_score"),
            reason=candidate.get("analysis", {}).get("relevance_reason", ""),
            extra={"paper_id": paper_id},
        )
        await _send_progress("save", 85, f"Saved: {candidate.get('title', '')[:40]}")
    elif status == "exists":
        _record_decision(
            state,
            stage="save",
            action="duplicate",
            arxiv_id=candidate.get("arxiv_id"),
            reason="Paper already existed by save time.",
        )
    else:
        _record_decision(
            state,
            stage="save",
            action="skipped",
            arxiv_id=candidate.get("arxiv_id"),
            reason=save_result.get("message", "Paper was not saved."),
        )

    state["current_save_index"] = index + 1
    return state


async def _save_candidate(candidate: dict) -> dict:
    from backend.models.database import Paper, PaperRecommendation, get_session_factory
    from backend.services.vector_store import get_vector_store

    analysis = candidate.get("analysis", {})
    relevance_score = _safe_float(analysis.get("relevance_score"))
    if relevance_score < SAVE_RELEVANCE_THRESHOLD:
        return {
            "status": "skipped",
            "message": "Paper relevance score is below the save threshold.",
        }

    factory = get_session_factory()
    vector_store = get_vector_store()

    async with factory() as session:
        result = await session.execute(select(Paper).where(Paper.arxiv_id == candidate["arxiv_id"]))
        if result.scalar_one_or_none():
            return {"status": "exists", "arxiv_id": candidate["arxiv_id"]}

        try:
            pub_date = datetime.fromisoformat(
                str(candidate.get("published_date") or "").replace("Z", "+00:00")
            )
        except Exception:
            pub_date = datetime.now(UTC).replace(tzinfo=None)

        paper = Paper(
            arxiv_id=candidate["arxiv_id"],
            title=candidate.get("title", ""),
            authors=candidate.get("authors", []),
            abstract=candidate.get("abstract", ""),
            categories=candidate.get("categories", []),
            published_date=pub_date,
            pdf_url=candidate.get("pdf_url", ""),
            local_pdf_path=None,
            ai_summary=analysis.get("summary", ""),
            ai_summary_zh=analysis.get("summary_zh", ""),
            key_findings=analysis.get("key_findings", []),
            relevance_score=relevance_score,
            is_downloaded=False,
        )
        session.add(paper)
        await session.flush()

        matched_interest_ids = [
            interest_id
            for interest_id in (analysis.get("matched_interest_ids") or [])
            if interest_id is not None
        ]
        recommendation = PaperRecommendation(
            paper_id=paper.id,
            interest_id=matched_interest_ids[0] if matched_interest_ids else None,
            score=relevance_score,
            reason=analysis.get("relevance_reason", ""),
        )
        session.add(recommendation)
        await session.commit()
        paper_id = paper.id

    vector_metadata = {"relevance_score": relevance_score}
    if matched_interest_ids:
        vector_metadata["matched_interest_id"] = matched_interest_ids[0]

    try:
        await vector_store.add_paper(
            arxiv_id=candidate["arxiv_id"],
            title=candidate.get("title", ""),
            abstract=candidate.get("abstract", ""),
            metadata=vector_metadata,
        )
    except Exception as e:
        logger.warning(f"Vector store indexing failed for {candidate.get('arxiv_id')}: {e}")

    return {
        "status": "saved",
        "arxiv_id": candidate["arxiv_id"],
        "paper_id": paper_id,
        "is_downloaded": False,
    }


async def _finalize_discovery(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    stats = state.get("stats", _empty_stats())
    errors = state.get("errors", [])

    if not state.get("interests"):
        status = "success"
        final_message = "No active or selected interests were available."
    elif errors and not state.get("candidates") and stats.get("papers_saved", 0) == 0:
        status = "failed"
        final_message = f"Fetch failed before producing candidates: {errors[0].get('message')}"
    elif errors:
        status = "partial"
        final_message = (
            f"Fetch completed with recoverable errors: found {stats.get('papers_found', 0)}, "
            f"analyzed {stats.get('papers_analyzed', 0)}, saved {stats.get('papers_saved', 0)}."
        )
    else:
        status = "success"
        final_message = (
            f"Fetch completed: found {stats.get('papers_found', 0)}, "
            f"analyzed {stats.get('papers_analyzed', 0)}, saved {stats.get('papers_saved', 0)}."
        )

    if state.get("fallbacks_used"):
        final_message += f" Fallbacks used: {', '.join(state['fallbacks_used'])}."

    state["status"] = status
    state["final_message"] = final_message
    return state


async def _persist_fetch_log(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)

    if not state.get("interests") and state.get("fetch_log_id") is None:
        return state

    try:
        from backend.models.database import FetchLog, get_session_factory

        topics = [i.get("topic") for i in state.get("interests_data", []) if i.get("topic")]
        stats = state.get("stats", _empty_stats())
        factory = get_session_factory()
        async with factory() as session:
            log = FetchLog(
                fetch_date=datetime.now(UTC).replace(tzinfo=None),
                source=state.get("source", "manual"),
                categories_fetched=topics,
                papers_found=stats.get("papers_found", 0),
                papers_relevant=stats.get("papers_relevant", 0),
                papers_downloaded=0,
                status=state.get("status", "success"),
                error_message=_result_error_message(state),
            )
            session.add(log)
            await session.flush()
            state["fetch_log_id"] = log.id
            await session.commit()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(state, stage="persist_fetch_log", message=f"Failed to write fetch log: {e}")
        state["fetch_log_id"] = None

    return state


def _route_after_persist_fetch_log(state: PaperAgentState) -> str:
    if state.get("generate_report", True) and state.get("fetch_log_id") is not None:
        return "generate_report"
    return "complete_run"


async def _generate_report(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)

    await _send_progress("report", 92, "Generating research report...")

    try:
        from backend.services.report_service import get_report_service

        report = await get_report_service().generate_fetch_report(
            fetch_log_id=state.get("fetch_log_id"),
            agent_result=_result_payload_from_state(state),
            source=state.get("source", "manual"),
            interests_data=state.get("interests_data", []),
        )
        state["report_id"] = report.id
        state["report_status"] = report.status
        state["report_error"] = report.error_message
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _record_error(state, stage="generate_report", message=f"Research report generation failed: {e}")
        state["report_id"] = None
        state["report_status"] = "failed"
        state["report_error"] = str(e)

    return state


async def _complete_run(state: PaperAgentState) -> PaperAgentState:
    check_cancelled()
    state = _ensure_state_defaults(state)
    await _send_progress("complete", 95, f"Fetch completed: saved {state['stats'].get('papers_saved', 0)} papers")
    return state


def _result_error_message(state: PaperAgentState) -> Optional[str]:
    errors = state.get("errors") or []
    if not errors:
        return None
    return errors[0].get("message")


def _result_payload_from_state(state: PaperAgentState) -> dict:
    stats = state.get("stats", _empty_stats())
    result = {
        "status": state.get("status", "success"),
        "papers_found": stats.get("papers_found", 0),
        "papers_analyzed": stats.get("papers_analyzed", 0),
        "papers_relevant": stats.get("papers_relevant", 0),
        "papers_saved": stats.get("papers_saved", 0),
        "saved_paper_ids": stats.get("saved_paper_ids", []),
        "final_message": state.get("final_message", ""),
        "decisions": state.get("decisions", []),
        "errors": state.get("errors", []),
        "fallbacks_used": state.get("fallbacks_used", []),
    }
    error_message = _result_error_message(state)
    if error_message:
        result["error"] = error_message
    return result


async def run_paper_agent(
    interests_data: list[dict],
    days_back: int = 7,
    max_results: int = 30,
    source: str = "manual",
    generate_report: bool = True,
    task_id: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> dict:
    """Run the fetch workflow, including discovery, fetch logging, and report generation."""
    set_task_id(task_id)
    set_selected_interests(interests_data)
    set_cancel_event(cancel_event)

    stats = _empty_stats()
    _stats_ctx.set(stats)

    initial_state: PaperAgentState = {
        "interests_data": interests_data or [],
        "days_back": days_back,
        "max_results": max_results,
        "source": source,
        "generate_report": generate_report,
        "stats": stats,
        "decisions": [],
        "errors": [],
        "fallbacks_used": [],
    }

    await _send_progress("start", 5, "Starting explicit paper workflow...")

    try:
        result_state = await asyncio.wait_for(
            get_paper_agent().ainvoke(
                initial_state,
                config={"recursion_limit": WORKFLOW_RECURSION_LIMIT},
            ),
            timeout=300,
        )
        result_stats = result_state.get("stats", stats)
        logger.info(f"Paper workflow completed. Stats: {result_stats}")

        result = _result_payload_from_state(result_state)
        result["fetch_log_id"] = result_state.get("fetch_log_id")
        result["report_id"] = result_state.get("report_id")
        result["report_status"] = result_state.get("report_status")
        result["report_error"] = result_state.get("report_error")
        return result

    except asyncio.CancelledError as e:
        error_msg = str(e) or "Agent was cancelled"
        logger.error(f"Paper workflow cancelled: {error_msg}")
        result = _failed_result(error_msg, stats, source=source)
        fetch_log_id, report_id, report_status, report_error = await _persist_failure_artifacts(
            error_msg=error_msg,
            interests_data=interests_data or [],
            source=source,
            generate_report=generate_report,
        )
        result["fetch_log_id"] = fetch_log_id
        result["report_id"] = report_id
        result["report_status"] = report_status
        result["report_error"] = report_error
        return result
    except Exception as e:
        error_msg = str(e) or type(e).__name__
        if not error_msg or error_msg == "CancelledError":
            error_msg = "Agent timed out or was cancelled"
        logger.exception(f"Paper workflow failed: {error_msg}")
        result = _failed_result(error_msg, stats, source=source)
        fetch_log_id, report_id, report_status, report_error = await _persist_failure_artifacts(
            error_msg=error_msg,
            interests_data=interests_data or [],
            source=source,
            generate_report=generate_report,
        )
        result["fetch_log_id"] = fetch_log_id
        result["report_id"] = report_id
        result["report_status"] = report_status
        result["report_error"] = report_error
        return result
    finally:
        set_cancel_event(None)


def _failed_result(error_msg: str, stats: dict, source: str = "manual") -> dict:
    return {
        "status": "failed",
        "error": error_msg,
        "papers_found": stats.get("papers_found", 0),
        "papers_analyzed": stats.get("papers_analyzed", 0),
        "papers_relevant": stats.get("papers_relevant", 0),
        "papers_saved": stats.get("papers_saved", 0),
        "saved_paper_ids": stats.get("saved_paper_ids", []),
        "decisions": [],
        "errors": [{"stage": "workflow", "message": error_msg, "recoverable": False}],
        "fallbacks_used": [],
        "fetch_log_id": None,
        "report_id": None,
        "report_status": None,
        "report_error": None,
        "source": source,
    }


async def _persist_failure_artifacts(
    *,
    error_msg: str,
    interests_data: list[dict],
    source: str,
    generate_report: bool,
) -> tuple[int | None, int | None, str | None, str | None]:
    fetch_log_id: int | None = None
    report_id: int | None = None
    report_status: str | None = None
    report_error: str | None = None

    try:
        from backend.models.database import FetchLog, get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            log = FetchLog(
                fetch_date=datetime.now(UTC).replace(tzinfo=None),
                source=source,
                categories_fetched=[i.get("topic") for i in interests_data if i.get("topic")],
                papers_found=0,
                papers_relevant=0,
                papers_downloaded=0,
                status="failed",
                error_message=error_msg,
            )
            session.add(log)
            await session.flush()
            fetch_log_id = log.id
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to persist failure fetch log: {e}")

    if generate_report and fetch_log_id is not None:
        try:
            from backend.services.report_service import get_report_service

            report = await get_report_service().generate_fetch_report(
                fetch_log_id=fetch_log_id,
                agent_result={
                    "status": "failed",
                    "error": error_msg,
                    "papers_found": 0,
                    "papers_analyzed": 0,
                    "papers_relevant": 0,
                    "papers_saved": 0,
                    "saved_paper_ids": [],
                },
                source=source,
                interests_data=interests_data,
            )
            report_id = report.id
            report_status = report.status
            report_error = report.error_message
        except Exception as e:
            logger.error(f"Failed to generate failure report: {e}")
            report_status = "failed"
            report_error = str(e)

    return fetch_log_id, report_id, report_status, report_error


def get_paper_workflow():
    """Backward compatibility alias for the explicit paper workflow."""
    return get_paper_agent()
