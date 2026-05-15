"""RAG (Retrieval-Augmented Generation) service for paper Q&A."""

from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage
from loguru import logger

from backend.services.vector_store import get_vector_store
from backend.services.llm_service import get_llm_service
from backend.models.database import get_session_factory, Paper, Conversation


class RAGService:
    """Service for RAG-based paper question answering."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.llm_service = get_llm_service()

    async def ask_question(
        self,
        paper_id: int,
        arxiv_id: str,
        question: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """Ask a question about a paper using RAG.

        Args:
            paper_id: Paper ID in database
            arxiv_id: ArXiv paper ID
            question: User's question
            conversation_history: Previous conversation messages

        Returns:
            Dictionary with response and metadata
        """
        logger.info(f"Processing question for paper {arxiv_id}: {question[:50]}...")

        # Get paper info from database
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(Paper).where(Paper.id == paper_id))
            paper = result.scalar_one_or_none()

        if not paper:
            return {
                "response": "Paper not found in database.",
                "sources": [],
                "error": "Paper not found",
            }

        # Retrieve relevant context from vector store
        try:
            context = await self.vector_store.get_paper_context(
                arxiv_id=arxiv_id,
                query=question,
                k=5,
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve context: {e}")
            context = paper.abstract  # Fallback to abstract

        # Build conversation context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n".join([
                f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
                for msg in conversation_history[-5:]  # Last 5 messages
            ])

        # Generate response
        full_context = f"{context}\n\nPrevious conversation:\n{conversation_context}" if conversation_context else context

        try:
            response = await self.llm_service.answer_question(
                question=question,
                context=full_context,
                title=paper.title,
                authors=paper.authors,
            )

            # Save conversation to database
            async with factory() as session:
                conversation = Conversation(
                    paper_id=paper_id,
                    user_message=question,
                    ai_response=response,
                    context_used=context[:1000],
                )
                session.add(conversation)
                await session.commit()

            return {
                "response": response,
                "sources": [f"Paper: {paper.title}"],
                "context_used": len(context),
            }

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return {
                "response": "I encountered an error while processing your question. Please try again.",
                "sources": [],
                "error": str(e),
            }

    async def get_paper_summary(self, paper_id: int) -> Optional[dict]:
        """Get paper summary and key information.

        Args:
            paper_id: Paper ID in database

        Returns:
            Paper summary dictionary
        """
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(Paper).where(Paper.id == paper_id))
            paper = result.scalar_one_or_none()

        if not paper:
            return None

        return {
            "id": paper.id,
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "ai_summary": paper.ai_summary,
            "ai_summary_zh": paper.ai_summary_zh,
            "key_findings": paper.key_findings,
            "relevance_score": paper.relevance_score,
        }

    async def get_conversation_history(self, paper_id: int) -> list[dict]:
        """Get conversation history for a paper.

        Args:
            paper_id: Paper ID in database

        Returns:
            List of conversation messages
        """
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Conversation)
                .where(Conversation.paper_id == paper_id)
                .order_by(Conversation.created_at)
            )
            conversations = result.scalars().all()

        return [
            {
                "id": conv.id,
                "user_message": conv.user_message,
                "ai_response": conv.ai_response,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
            }
            for conv in conversations
        ]

    async def search_similar_papers(self, query: str, k: int = 10) -> list[dict]:
        """Search for papers similar to a query.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of similar papers
        """
        results = await self.vector_store.search_papers(
            query=query,
            k=k,
            filter_dict={"type": "paper"},
        )

        papers = []
        for doc, score in results:
            papers.append({
                "arxiv_id": doc.metadata.get("arxiv_id"),
                "title": doc.metadata.get("title"),
                "score": float(score),
                "snippet": doc.page_content[:200],
            })

        return papers


# Singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
