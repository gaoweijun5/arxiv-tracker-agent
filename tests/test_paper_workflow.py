import pytest

from backend.agents import paper_agent
from backend.agents import tools
from backend.services.llm_service import PaperSummary, RelevanceCheck


@pytest.fixture(autouse=True)
def clear_agent_context():
    tools.set_selected_interests(None)
    tools.set_task_id(None)
    tools.set_cancel_event(None)
    yield
    tools.set_selected_interests(None)
    tools.set_task_id(None)
    tools.set_cancel_event(None)


def _stats():
    return {
        "papers_found": 0,
        "papers_analyzed": 0,
        "papers_relevant": 0,
        "papers_saved": 0,
        "saved_paper_ids": [],
    }


class _AsyncSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_search_candidates_uses_scoped_fallback(monkeypatch):
    calls = []

    async def fake_search_arxiv_attempt(*, attempt, max_results, plan):
        calls.append(attempt["mode"])
        if attempt["mode"] == "primary":
            return []
        return [
            {
                "arxiv_id": "2601.00001",
                "title": "Tool Use for Language Model Agents",
                "abstract": "A paper about tool use and planning.",
                "authors": ["A. Author"],
                "categories": ["cs.AI"],
                "pdf_url": "https://arxiv.org/pdf/2601.00001",
                "published_date": "2026-01-01T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr(paper_agent, "_search_arxiv_attempt", fake_search_arxiv_attempt)

    state = {
        "query_plans": [
            {
                "interest_id": 1,
                "topic": "language model agents",
                "attempts": [
                    {
                        "mode": "primary",
                        "keywords": ["language model agents", "tool use"],
                        "categories": ["cs.AI"],
                        "days_back": 7,
                    },
                    {
                        "mode": "category_only",
                        "keywords": [],
                        "categories": ["cs.AI"],
                        "days_back": 7,
                    },
                ],
            }
        ],
        "max_results": 10,
        "stats": _stats(),
    }

    result = await paper_agent._init_search_loop(state)

    result = await paper_agent._search_attempt(result)
    assert paper_agent._route_after_search_attempt(result) == "next_attempt"

    result = await paper_agent._next_search_attempt(result)
    result = await paper_agent._search_attempt(result)
    assert paper_agent._route_after_search_attempt(result) == "next_plan"

    result = await paper_agent._next_query_plan(result)
    assert paper_agent._route_query_plan_loop(result) == "finish_search"

    result = await paper_agent._search_candidates(result)

    assert calls == ["primary", "category_only"]
    assert result["fallbacks_used"] == ["category_only"]
    assert result["stats"]["papers_found"] == 1
    assert result["candidates"][0]["arxiv_id"] == "2601.00001"
    assert any(d["action"] == "fallback_succeeded" for d in result["decisions"])


@pytest.mark.asyncio
async def test_rank_candidates_skips_weak_local_matches():
    state = {
        "interests": [
            {
                "id": 1,
                "topic": "language model agents",
                "keywords": ["tool use", "planning"],
                "categories": ["cs.AI"],
                "weight": 1.0,
            }
        ],
        "new_candidates": [
            {
                "arxiv_id": "2601.00001",
                "title": "Tool Use for Language Model Agents",
                "abstract": "Planning and tool use for language model agents.",
                "categories": ["cs.AI"],
                "published_date": "2026-01-01T00:00:00+00:00",
            },
            {
                "arxiv_id": "2601.00002",
                "title": "A Study of Unrelated Hardware",
                "abstract": "Circuit layouts and timing closure.",
                "categories": ["cs.AR"],
                "published_date": "2026-01-01T00:00:00+00:00",
            },
        ],
        "stats": _stats(),
    }

    result = await paper_agent._init_rank_loop(state)
    while paper_agent._route_rank_loop(result) == "score_candidate":
        result = await paper_agent._score_one_candidate(result)
    result = await paper_agent._finalize_ranking(result)

    assert [paper["arxiv_id"] for paper in result["ranked_candidates"]] == ["2601.00001"]
    assert result["ranked_candidates"][0]["local_score"] >= 0.6
    assert any(
        decision["stage"] == "rank"
        and decision["action"] == "skipped"
        and decision["arxiv_id"] == "2601.00002"
        for decision in result["decisions"]
    )


@pytest.mark.asyncio
async def test_analyze_candidate_uses_conservative_local_fallback(monkeypatch):
    class FakeLLMService:
        async def generate_summary(self, title, abstract, authors, categories):
            return PaperSummary(
                summary="A concise summary.",
                summary_zh="",
                key_findings=["Finding"],
                methodology="Experiment",
                relevance_score=0.0,
                relevance_reason="",
            )

        async def check_relevance(self, title, abstract, categories, interests):
            return RelevanceCheck(
                is_relevant=False,
                score=0.0,
                reason="Error: upstream model unavailable",
            )

    import backend.services.llm_service as llm_service_module

    monkeypatch.setattr(llm_service_module, "get_llm_service", lambda: FakeLLMService())

    analysis = await paper_agent._analyze_candidate(
        {
            "arxiv_id": "2601.00001",
            "title": "Tool Use for Language Model Agents",
            "abstract": "Planning and tool use for language model agents.",
            "authors": ["A. Author"],
            "categories": ["cs.AI"],
            "local_score": 0.9,
            "local_reason": "Matched selected interest strongly.",
            "matched_interest_ids": [1],
        },
        [
            {
                "id": 1,
                "topic": "language model agents",
                "keywords": ["tool use", "planning"],
                "categories": ["cs.AI"],
                "weight": 1.0,
            }
        ],
    )

    assert analysis["is_relevant"] is True
    assert analysis["relevance_score"] >= 0.6
    assert analysis["fallback_used"] == "local_relevance_after_llm_failure"


@pytest.mark.asyncio
async def test_analyze_candidate_skips_weak_local_signal_after_llm_failure(monkeypatch):
    class FakeLLMService:
        async def generate_summary(self, title, abstract, authors, categories):
            return PaperSummary(
                summary="A concise summary.",
                summary_zh="",
                key_findings=["Finding"],
                methodology="Experiment",
                relevance_score=0.0,
                relevance_reason="",
            )

        async def check_relevance(self, title, abstract, categories, interests):
            return RelevanceCheck(
                is_relevant=False,
                score=0.0,
                reason="Unable to determine relevance",
            )

    import backend.services.llm_service as llm_service_module

    monkeypatch.setattr(llm_service_module, "get_llm_service", lambda: FakeLLMService())

    analysis = await paper_agent._analyze_candidate(
        {
            "arxiv_id": "2601.00002",
            "title": "Weak Match",
            "abstract": "A broad paper.",
            "authors": ["A. Author"],
            "categories": ["cs.AI"],
            "local_score": 0.4,
            "local_reason": "Only category matched.",
            "matched_interest_ids": [1],
        },
        [
            {
                "id": 1,
                "topic": "language model agents",
                "keywords": ["tool use", "planning"],
                "categories": ["cs.AI"],
                "weight": 1.0,
            }
        ],
    )

    assert analysis["is_relevant"] is False
    assert analysis["relevance_score"] == 0.0
    assert analysis["fallback_used"] == "skip_after_llm_failure"


@pytest.mark.asyncio
async def test_persist_fetch_log_writes_fetch_log_id(monkeypatch):
    created = {}

    class FakeFetchLog:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.id = 42

    class FakeSession:
        def add(self, obj):
            created["added"] = obj

        async def flush(self):
            return None

        async def commit(self):
            return None

    import backend.models.database as database_module

    monkeypatch.setattr(database_module, "FetchLog", FakeFetchLog)
    monkeypatch.setattr(
        database_module,
        "get_session_factory",
        lambda: (lambda: _AsyncSessionContext(FakeSession())),
    )

    state = {
        "interests": [{"topic": "language model agents"}],
        "interests_data": [{"topic": "language model agents"}],
        "stats": _stats(),
        "status": "success",
        "errors": [],
    }

    result = await paper_agent._persist_fetch_log(state)

    assert result["fetch_log_id"] == 42
    assert created["source"] == "manual"
    assert created["categories_fetched"] == ["language model agents"]


@pytest.mark.asyncio
async def test_generate_report_updates_state(monkeypatch):
    class FakeReport:
        id = 7
        status = "generated"
        error_message = None

    class FakeReportService:
        async def generate_fetch_report(self, fetch_log_id, agent_result, source, interests_data):
            assert fetch_log_id == 42
            assert source == "manual"
            assert agent_result["papers_saved"] == 1
            assert interests_data == [{"topic": "language model agents"}]
            return FakeReport()

    import backend.services.report_service as report_service_module

    monkeypatch.setattr(report_service_module, "get_report_service", lambda: FakeReportService())

    state = {
        "fetch_log_id": 42,
        "stats": {
            "papers_found": 3,
            "papers_analyzed": 2,
            "papers_relevant": 1,
            "papers_saved": 1,
            "saved_paper_ids": [99],
        },
        "status": "success",
        "final_message": "done",
        "interests_data": [{"topic": "language model agents"}],
    }

    result = await paper_agent._generate_report(state)

    assert result["report_id"] == 7
    assert result["report_status"] == "generated"
    assert result["report_error"] is None
