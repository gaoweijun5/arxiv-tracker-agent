import json

import pytest

from backend.agents import tools
from backend.agents.tools import _constrain_search_to_selected_interests


@pytest.fixture(autouse=True)
def clear_agent_context():
    tools.set_selected_interests(None)
    tools.set_task_id(None)
    yield
    tools.set_selected_interests(None)
    tools.set_task_id(None)


def test_unselected_context_keeps_requested_search_params():
    keywords, categories, constrained = _constrain_search_to_selected_interests(
        keywords=["diffusion"],
        categories=["cs.CV"],
        selected_interests=None,
    )

    assert keywords == ["diffusion"]
    assert categories == ["cs.CV"]
    assert constrained is False


def test_selected_context_replaces_unrelated_agent_keywords():
    selected = [
        {
            "topic": "graph neural networks",
            "keywords": ["GNN", "message passing"],
            "categories": ["cs.LG"],
        }
    ]

    keywords, categories, constrained = _constrain_search_to_selected_interests(
        keywords=["computer vision", "diffusion"],
        categories=["cs.CV"],
        selected_interests=selected,
    )

    assert keywords == ["graph neural networks", "GNN", "message passing"]
    assert categories == ["cs.LG"]
    assert constrained is True


def test_selected_context_strips_unchecked_topics_from_mixed_request():
    selected = [
        {
            "topic": "large language model agents",
            "keywords": ["tool use", "planning"],
            "categories": ["cs.AI", "cs.CL"],
        },
        {
            "topic": "graph neural networks",
            "keywords": ["GNN"],
            "categories": ["cs.LG"],
        },
    ]

    keywords, categories, constrained = _constrain_search_to_selected_interests(
        keywords=["GNN", "diffusion models", "tool use"],
        categories=["cs.LG", "cs.CV"],
        selected_interests=selected,
    )

    assert keywords == ["GNN", "tool use"]
    assert categories == ["cs.LG"]
    assert constrained is True


def test_explicit_empty_selection_blocks_broad_search():
    keywords, categories, constrained = _constrain_search_to_selected_interests(
        keywords=["anything"],
        categories=["cs.AI"],
        selected_interests=[],
    )

    assert keywords == []
    assert categories == []
    assert constrained is True


@pytest.mark.asyncio
async def test_search_arxiv_tool_sends_only_selected_scope(monkeypatch):
    calls = {}

    class FakeArxivService:
        async def search_papers(self, categories, keywords, days_back, max_results):
            calls["categories"] = categories
            calls["keywords"] = keywords
            calls["days_back"] = days_back
            calls["max_results"] = max_results
            return []

    import backend.services.arxiv_service as arxiv_service_module

    monkeypatch.setattr(
        arxiv_service_module,
        "get_arxiv_service",
        lambda: FakeArxivService(),
    )
    tools.set_selected_interests([
        {
            "topic": "large language model agents",
            "keywords": ["tool use"],
            "categories": ["cs.AI"],
        }
    ])

    result = await tools.search_arxiv.ainvoke({
        "keywords": ["diffusion models"],
        "categories": ["cs.CV"],
        "days_back": 3,
        "max_results": 10,
    })

    assert json.loads(result) == []
    assert calls == {
        "categories": ["cs.AI"],
        "keywords": ["large language model agents", "tool use"],
        "days_back": 3,
        "max_results": 10,
    }


@pytest.mark.asyncio
async def test_search_arxiv_tool_allows_selected_category_only_scope(monkeypatch):
    calls = {}

    class FakeArxivService:
        async def search_papers(self, categories, keywords, days_back, max_results):
            calls["categories"] = categories
            calls["keywords"] = keywords
            calls["days_back"] = days_back
            calls["max_results"] = max_results
            return []

    import backend.services.arxiv_service as arxiv_service_module

    monkeypatch.setattr(
        arxiv_service_module,
        "get_arxiv_service",
        lambda: FakeArxivService(),
    )
    tools.set_selected_interests([
        {
            "topic": "large language model agents",
            "keywords": ["tool use"],
            "categories": ["cs.AI"],
        }
    ])

    result = await tools.search_arxiv.ainvoke({
        "keywords": [],
        "categories": ["cs.AI"],
        "days_back": 3,
        "max_results": 10,
    })

    assert json.loads(result) == []
    assert calls == {
        "categories": ["cs.AI"],
        "keywords": None,
        "days_back": 3,
        "max_results": 10,
    }
