"""RAG (Retrieval-Augmented Generation) service for paper Q&A."""

from pathlib import Path
from typing import Optional
from loguru import logger

from backend.services.vector_store import get_vector_store
from backend.services.llm_service import get_llm_service
from backend.services.pdf_service import get_pdf_service
from backend.models.database import get_session_factory, Paper, Conversation


class RAGService:
    """Service for RAG-based paper question answering."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.llm_service = get_llm_service()
        self.pdf_service = get_pdf_service()
        from backend.services.hybrid_retrieval_service import get_hybrid_retrieval_service
        self.hybrid_retrieval = get_hybrid_retrieval_service()

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

        context = ""
        retrieval_mode = "full_text"
        source_chunks = []

        has_chunks = await self.hybrid_retrieval.has_chunks(paper_id)
        has_local_pdf = bool(paper.local_pdf_path and Path(paper.local_pdf_path).exists())
        if not has_chunks and not has_local_pdf:
            logger.info("PDF is not available locally; refusing automatic download for Q&A")
            return {
                "response": "PDF is not downloaded yet. Click the download button first, then ask again.",
                "sources": [],
                "error": "pdf_not_downloaded",
                "requires_download": True,
            }

        if has_chunks:
            retrieved_chunks, use_chunks = await self.hybrid_retrieval.hybrid_search(
                paper_id=paper_id,
                arxiv_id=arxiv_id,
                query=question,
            )
            source_chunks = [chunk.to_source_dict() for chunk in retrieved_chunks]
            if use_chunks:
                retrieval_mode = "hybrid_chunks"
                context = "\n\n---\n\n".join([
                    self._format_chunk_context(chunk.to_source_dict(), chunk.chunk.content)
                    for chunk in retrieved_chunks
                ])
                top_conf = retrieved_chunks[0].confidence if retrieved_chunks else 0.0
                logger.info(
                    f"Using {len(retrieved_chunks)} retrieved chunks for {arxiv_id}; "
                    f"top confidence={top_conf:.3f}"
                )

        if not context:
            retrieval_mode = "full_text"
            if has_local_pdf:
                try:
                    context = self.pdf_service.extract_text(Path(paper.local_pdf_path)) or ""
                    logger.info(f"Loaded {len(context)} chars from local PDF")
                except Exception as e:
                    logger.warning(f"Failed to extract text from PDF: {e}")

            if not context and has_chunks:
                context = await self.hybrid_retrieval.get_full_text_from_chunks(paper_id)
                logger.info(f"Reconstructed {len(context)} chars from persisted chunks")

        if not context:
            return {
                "response": "I could not load enough local paper context to answer. Please download the PDF again.",
                "sources": [],
                "error": "context_unavailable",
            }

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
                "sources": self._sources_for_response(paper.title, retrieval_mode, source_chunks),
                "context_used": len(context),
                "retrieval_mode": retrieval_mode,
                "source_chunks": source_chunks if retrieval_mode == "hybrid_chunks" else [],
            }

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return {
                "response": "I encountered an error while processing your question. Please try again.",
                "sources": [],
                "error": str(e),
            }

    def _format_chunk_context(self, source: dict, content: str) -> str:
        page_start = source.get("page_start")
        page_end = source.get("page_end")
        if page_start and page_end and page_start != page_end:
            page_label = f"pages {page_start}-{page_end}"
        elif page_start:
            page_label = f"page {page_start}"
        else:
            page_label = "page unknown"
        return (
            f"[Chunk {source.get('chunk_index')} | {page_label} | "
            f"confidence {source.get('confidence')}]\n{content}"
        )

    def _sources_for_response(
        self,
        paper_title: str,
        retrieval_mode: str,
        source_chunks: list[dict],
    ) -> list[str]:
        if retrieval_mode != "hybrid_chunks":
            return [f"Paper: {paper_title}"]
        sources = []
        for source in source_chunks:
            page_start = source.get("page_start")
            if page_start:
                sources.append(f"Chunk {source.get('chunk_index')} (page {page_start})")
            else:
                sources.append(f"Chunk {source.get('chunk_index')}")
        return sources

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
