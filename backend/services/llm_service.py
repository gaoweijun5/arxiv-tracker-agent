"""LLM service for AI-powered paper analysis and summarization."""

import json
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from loguru import logger

from backend.core.config import get_settings


class PaperSummary(BaseModel):
    """Structured paper summary."""

    summary: str = Field(description="Concise summary of the paper")
    summary_zh: str = Field(description="Chinese translation of the summary")
    key_findings: list[str] = Field(description="List of key findings or contributions")
    methodology: str = Field(description="Brief description of the methodology")
    relevance_score: float = Field(description="Relevance score from 0 to 1")
    relevance_reason: str = Field(description="Explanation of relevance score")


class RelevanceCheck(BaseModel):
    """Paper relevance check result."""

    is_relevant: bool = Field(description="Whether the paper is relevant")
    score: float = Field(description="Relevance score from 0 to 1")
    reason: str = Field(description="Explanation of relevance")


def parse_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response text."""
    # Try to find JSON in the response
    text = text.strip()

    # If response starts with ```json, extract the JSON block
    if text.startswith("```json"):
        text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    elif text.startswith("```"):
        text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try to parse as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    # If all fails, return empty dict
    logger.warning(f"Failed to parse JSON from response: {text[:200]}...")
    return {}


class LLMService:
    """Service for LLM-powered paper analysis."""

    def __init__(self):
        self.settings = get_settings()
        from backend.services.llm_factory import create_llm
        self.llm = create_llm()
        self._setup_chains()

    def _setup_chains(self):
        """Set up LangChain processing chains."""

        # Paper summarization chain - using JSON mode prompt
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert research paper analyst. Analyze the given paper and provide a structured summary.

You MUST respond with valid JSON only, no other text. Use this exact format:
{{
    "summary": "Concise summary of the paper (2-3 sentences)",
    "summary_zh": "Chinese translation of the summary",
    "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
    "methodology": "Brief description of the methodology",
    "relevance_score": 0.8,
    "relevance_reason": "Explanation of relevance score"
}}"""),
            ("human", """Paper Title: {title}
Authors: {authors}
Abstract: {abstract}
Categories: {categories}

Analyze this paper and provide a structured summary as JSON."""),
        ])
        self.summary_chain = summary_prompt | self.llm | StrOutputParser()

        # Relevance checking chain
        relevance_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a research paper relevance checker. Given a paper and user interests,
score how relevant the paper is to the user on a 0-1 scale.

SCORING RUBRIC:
- 0.9-1.0: Paper directly addresses the user's core topic with matching methods or applications
- 0.7-0.8: Paper is in the same research area, shares key concepts or techniques
- 0.5-0.6: Paper is tangentially related, shares some themes but different focus
- 0.3-0.4: Paper is in a broadly related field but not aligned with user's specific interests
- 0.0-0.2: Paper is unrelated to the user's interests

For each score dimension, evaluate:
1. TOPIC MATCH: Does the paper's subject overlap with the user's interests?
2. METHOD MATCH: Does the paper use techniques relevant to the user's work?
3. CATEGORY MATCH: Are the arXiv categories aligned with the user's preferred categories?
4. KEYWORD MATCH: Do the paper's key terms appear in the user's interest keywords?

Combine these dimensions: topic and method matter most, category and keyword are supporting signals.

You MUST respond with valid JSON only, no other text. Use this exact format:
{{
    "is_relevant": true,
    "score": 0.85,
    "reason": "Brief explanation citing which dimensions match or don't"
}}"""),
            ("human", """User Research Interests:
{interests}

Paper Title: {title}
Abstract: {abstract}
Categories: {categories}

Score this paper's relevance to the user's interests. Respond as JSON."""),
        ])
        self.relevance_chain = relevance_prompt | self.llm | StrOutputParser()

        # Q&A chain for paper discussion
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful research assistant discussing a specific paper.
Use the provided context from the paper to answer questions accurately.
If the answer isn't in the context, say so honestly.

Context from the paper:
{context}

Paper Title: {title}
Authors: {authors}"""),
            ("human", "{question}"),
        ])
        self.qa_chain = qa_prompt | self.llm | StrOutputParser()

        # Daily digest chain
        digest_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a research news curator. Create an engaging, newspaper-style digest
of today's research papers. Make it informative yet accessible.

Format each paper as a brief news article with:
- An attention-grabbing headline
- 2-3 sentence summary
- Why it matters

Write in a engaging, journalistic style."""),
            ("human", """Create a research digest for these papers:

{papers}

Format the output as a daily research newsletter."""),
        ])
        self.digest_chain = digest_prompt | self.llm | StrOutputParser()

        # Research report chain
        report_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a research curator writing a concise Markdown report after a paper fetch run.
The audience is a researcher who wants to decide what to read next.

Write a practical report with these sections:
# Research Report
## Executive Summary
## Top Papers
## Topic Signals
## Suggested Next Steps

For each paper, explain why it matters and why it matched the user's interests.
Do not invent facts beyond the provided metadata and summaries."""),
            ("human", """Fetch source: {source}
Search interests: {interests}
Fetch stats: {stats}

Papers:
{papers}

Create the Markdown research report."""),
        ])
        self.report_chain = report_prompt | self.llm | StrOutputParser()

    async def generate_summary(
        self,
        title: str,
        abstract: str,
        authors: list[str],
        categories: list[str],
    ) -> PaperSummary:
        """Generate AI summary for a paper.

        Args:
            title: Paper title
            abstract: Paper abstract
            authors: List of authors
            categories: arXiv categories

        Returns:
            PaperSummary object
        """
        try:
            response = await self.summary_chain.ainvoke({
                "title": title,
                "abstract": abstract,
                "authors": ", ".join(authors),
                "categories": ", ".join(categories),
            })

            # Parse JSON response
            data = parse_json_from_response(response)

            if not data:
                # Fallback if JSON parsing fails
                return PaperSummary(
                    summary=abstract[:200] + "...",
                    summary_zh="",
                    key_findings=["Summary generation failed"],
                    methodology="Unknown",
                    relevance_score=0.5,
                    relevance_reason="Unable to analyze"
                )

            logger.info(f"Generated summary for: {title[:50]}...")
            return PaperSummary(**data)

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            # Return fallback summary
            return PaperSummary(
                summary=abstract[:200] + "...",
                summary_zh="",
                key_findings=["Summary generation failed"],
                methodology="Unknown",
                relevance_score=0.5,
                relevance_reason=f"Error: {str(e)[:100]}"
            )

    async def check_relevance(
        self,
        title: str,
        abstract: str,
        categories: list[str],
        interests: list[dict],
    ) -> RelevanceCheck:
        """Check if a paper is relevant to user interests.

        Args:
            title: Paper title
            abstract: Paper abstract
            categories: arXiv categories
            interests: List of user interests

        Returns:
            RelevanceCheck object
        """
        interests_text = "\n".join([
            f"- {i['topic']}: {i.get('description', '')} (Keywords: {', '.join(i.get('keywords', []))})"
            for i in interests
        ])

        try:
            response = await self.relevance_chain.ainvoke({
                "title": title,
                "abstract": abstract,
                "categories": ", ".join(categories),
                "interests": interests_text,
            })

            # Parse JSON response
            data = parse_json_from_response(response)

            if not data:
                # Fallback if JSON parsing fails
                return RelevanceCheck(
                    is_relevant=False,
                    score=0.0,
                    reason="Unable to determine relevance"
                )

            logger.info(f"Relevance check for '{title[:50]}...': {data.get('is_relevant', False)} ({data.get('score', 0):.2f})")
            return RelevanceCheck(**data)

        except Exception as e:
            logger.error(f"Failed to check relevance: {e}")
            return RelevanceCheck(
                is_relevant=False,
                score=0.0,
                reason=f"Error: {str(e)[:100]}"
            )

    async def answer_question(
        self,
        question: str,
        context: str,
        title: str,
        authors: list[str],
    ) -> str:
        """Answer a question about a paper using RAG context.

        Args:
            question: User's question
            context: Retrieved context from paper
            title: Paper title
            authors: Paper authors

        Returns:
            AI response
        """
        try:
            response = await self.qa_chain.ainvoke({
                "question": question,
                "context": context,
                "title": title,
                "authors": ", ".join(authors),
            })
            return response
        except Exception as e:
            logger.error(f"Failed to answer question: {e}")
            raise

    async def generate_daily_digest(self, papers: list[dict]) -> str:
        """Generate a newspaper-style digest of papers.

        Args:
            papers: List of paper dictionaries with summaries

        Returns:
            Formatted digest string
        """
        papers_text = "\n\n".join([
            f"Title: {p['title']}\nSummary: {p.get('ai_summary') or p.get('abstract', '')[:200]}"
            for p in papers[:10]  # Limit to 10 papers for digest
        ])

        try:
            digest = await self.digest_chain.ainvoke({"papers": papers_text})
            return digest
        except Exception as e:
            logger.error(f"Failed to generate digest: {e}")
            raise

    async def generate_research_report(
        self,
        papers: list[dict],
        stats: dict,
        interests: list[dict],
        source: str,
    ) -> str:
        """Generate a Markdown research report for one fetch run."""
        papers_text = "\n\n".join([
            "\n".join([
                f"Title: {p.get('title', '')}",
                f"Authors: {', '.join(p.get('authors') or [])}",
                f"Categories: {', '.join(p.get('categories') or [])}",
                f"Score: {p.get('relevance_score')}",
                f"Summary: {p.get('ai_summary') or p.get('abstract', '')[:500]}",
                f"Key findings: {'; '.join(p.get('key_findings') or [])}",
            ])
            for p in papers[:10]
        ])
        interests_text = "\n".join([
            f"- {i.get('topic', '')}: {', '.join(i.get('keywords') or [])}"
            for i in interests
        ])

        try:
            return await self.report_chain.ainvoke({
                "source": source,
                "interests": interests_text or "No explicit interests provided.",
                "stats": json.dumps(stats, ensure_ascii=False),
                "papers": papers_text or "No papers saved in this fetch.",
            })
        except Exception as e:
            logger.error(f"Failed to generate research report: {e}")
            raise


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
