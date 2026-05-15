"""RAG (Retrieval-Augmented Generation) service for paper Q&A."""

from pathlib import Path
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage
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

        # Retrieve full paper text: vector store -> local PDF -> download PDF -> abstract
        context = ""
        try:
            context = await self.vector_store.get_full_paper_text(
                arxiv_id=arxiv_id,
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve from vector store: {e}")

        # Fallback: extract text directly from local PDF
        if not context and paper.local_pdf_path and Path(paper.local_pdf_path).exists():
            try:
                logger.info(f"Extracting text from local PDF: {paper.local_pdf_path}")
                context = self.pdf_service.extract_text(Path(paper.local_pdf_path)) or ""
                logger.info(f"Extracted {len(context)} chars from PDF")
            except Exception as e:
                logger.warning(f"Failed to extract text from PDF: {e}")

        # Auto-download PDF if not available locally
        if not context and paper.pdf_url:
            try:
                context = await self._download_and_extract_pdf(paper, factory)
            except Exception as e:
                logger.warning(f"Failed to auto-download PDF: {e}")

        # Final fallback: use abstract
        if not context:
            logger.info("Using abstract as context (no full text available)")
            context = paper.abstract

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

    async def _download_and_extract_pdf(self, paper, factory) -> str:
        """Download PDF and extract full text.

        Args:
            paper: Paper ORM object
            factory: Database session factory

        Returns:
            Extracted full text or empty string
        """
        from backend.core.config import get_settings
        import httpx

        settings = get_settings()
        settings.papers_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = settings.papers_dir / f"{paper.arxiv_id.replace('/', '_')}.pdf"

        # Download if not cached
        if not pdf_path.exists():
            logger.info(f"Auto-downloading PDF for Q&A: {paper.pdf_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(paper.pdf_url, follow_redirects=True, timeout=60.0)
                response.raise_for_status()
                pdf_path.write_bytes(response.content)

        # Extract text
        full_text = self.pdf_service.extract_text(pdf_path)
        if not full_text:
            return ""

        # Update database with local path
        async with factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(Paper).where(Paper.id == paper.id))
            db_paper = result.scalar_one_or_none()
            if db_paper:
                db_paper.local_pdf_path = str(pdf_path)
                db_paper.is_downloaded = True
                await session.commit()

        # Also index into vector store for future use
        try:
            chunks = self.pdf_service.chunk_text(full_text)
            if chunks:
                await self.vector_store.add_paper_chunks(
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    chunks=chunks,
                )
        except Exception as e:
            logger.warning(f"Failed to index chunks to vector store: {e}")

        logger.info(f"Auto-downloaded and extracted {len(full_text)} chars for {paper.arxiv_id}")
        return full_text

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
