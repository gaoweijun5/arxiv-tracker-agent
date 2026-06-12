"""Hybrid SQLite FTS + Chroma retrieval for paper Q&A."""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from loguru import logger
from sqlalchemy import delete, select, text

from backend.core.config import get_settings
from backend.models.database import PaperChunk, get_session_factory
from backend.services.pdf_service import ParsedPaper, ParsedPaperChunk, get_pdf_service
from backend.services.vector_store import get_vector_store


@dataclass
class RetrievedChunk:
    """A chunk returned by hybrid retrieval."""

    chunk: PaperChunk
    rrf_score: float = 0.0
    semantic_score: float = 0.0
    keyword_score: float = 0.0

    @property
    def confidence(self) -> float:
        return max(self.semantic_score, self.keyword_score)

    def to_source_dict(self) -> dict:
        return {
            "id": self.chunk.id,
            "chunk_index": self.chunk.chunk_index,
            "page_start": self.chunk.page_start,
            "page_end": self.chunk.page_end,
            "confidence": round(self.confidence, 4),
            "semantic_score": round(self.semantic_score, 4),
            "keyword_score": round(self.keyword_score, 4),
            "rrf_score": round(self.rrf_score, 6),
            "snippet": self.chunk.content[:300],
        }


class HybridRetrievalService:
    """Retrieve paper chunks using both semantic and keyword signals."""

    def __init__(self):
        self.settings = get_settings()
        self.vector_store = get_vector_store()
        self.pdf_service = get_pdf_service()

    async def replace_paper_chunks_from_pdf(
        self,
        paper_id: int,
        arxiv_id: str,
        title: str,
        pdf_path: Path | str,
    ) -> tuple[list[PaperChunk], ParsedPaper]:
        """Parse a PDF with Docling, replace chunks, and sync SQLite FTS + Chroma."""
        parsed = await asyncio.to_thread(self.pdf_service.parse_pdf, Path(pdf_path))
        chunk_rows = await self._replace_parsed_chunks(
            paper_id=paper_id,
            arxiv_id=arxiv_id,
            title=title,
            chunks=parsed.chunks,
            parser=parsed.parser,
            chunker=parsed.chunker,
        )
        return chunk_rows, parsed

    async def _replace_parsed_chunks(
        self,
        paper_id: int,
        arxiv_id: str,
        title: str,
        chunks: list[ParsedPaperChunk],
        parser: str,
        chunker: str,
    ) -> list[PaperChunk]:
        """Replace persisted chunks for a paper and sync SQLite FTS + Chroma."""
        chunk_texts = [chunk.content for chunk in chunks]

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text("DELETE FROM paper_chunks_fts WHERE arxiv_id = :arxiv_id"),
                {"arxiv_id": arxiv_id},
            )
            await session.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))

            try:
                await self.vector_store.delete_paper_chunks(arxiv_id)
            except Exception as e:
                logger.warning(f"Failed to delete old Chroma chunks for {arxiv_id}: {e}")

            if not chunks:
                await session.commit()
                logger.warning(f"No chunks generated for paper {arxiv_id}")
                return []

            chunk_rows = [
                PaperChunk(
                    paper_id=paper_id,
                    arxiv_id=arxiv_id,
                    chunk_index=i,
                    content=chunk.content,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
                for i, chunk in enumerate(chunks)
            ]
            session.add_all(chunk_rows)
            await session.flush()

            metadatas = [
                self._chunk_metadata(
                    chunk=chunk,
                    parsed_chunk=chunks[i],
                    parser=parser,
                    chunker=chunker,
                )
                for i, chunk in enumerate(chunk_rows)
            ]

            try:
                vector_ids = await self.vector_store.add_paper_chunks(
                    arxiv_id=arxiv_id,
                    title=title,
                    chunks=chunk_texts,
                    metadatas=metadatas,
                )
                for chunk, vector_id in zip(chunk_rows, vector_ids):
                    chunk.vector_id = vector_id
            except Exception as e:
                logger.warning(f"Failed to sync paper chunks to Chroma: {e}")

            for chunk in chunk_rows:
                await session.execute(
                    text("""
                        INSERT INTO paper_chunks_fts(rowid, paper_chunk_id, arxiv_id, content)
                        VALUES (:rowid, :paper_chunk_id, :arxiv_id, :content)
                    """),
                    {
                        "rowid": chunk.id,
                        "paper_chunk_id": chunk.id,
                        "arxiv_id": arxiv_id,
                        "content": chunk.content,
                    },
                )

            await session.commit()
            logger.info(f"Persisted {len(chunk_rows)} chunks for paper {arxiv_id}")
            return chunk_rows

    def _chunk_metadata(
        self,
        chunk: PaperChunk,
        parsed_chunk: ParsedPaperChunk,
        parser: str,
        chunker: str,
    ) -> dict:
        metadata = {
            "paper_chunk_id": chunk.id,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_heading": parsed_chunk.heading,
            "chunk_kind": parsed_chunk.kind,
            "block_count": parsed_chunk.block_count,
            "parser": parser,
            "chunker": chunker,
        }
        return {key: value for key, value in metadata.items() if value is not None}

    async def has_chunks(self, paper_id: int) -> bool:
        """Return whether a paper has persisted chunks."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(PaperChunk.id).where(PaperChunk.paper_id == paper_id).limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def get_full_text_from_chunks(self, paper_id: int) -> str:
        """Reconstruct full paper text from SQLite chunks."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(PaperChunk)
                .where(PaperChunk.paper_id == paper_id)
                .order_by(PaperChunk.chunk_index)
            )
            chunks = result.scalars().all()
        return "\n\n".join(chunk.content for chunk in chunks)

    async def hybrid_search(
        self,
        paper_id: int,
        arxiv_id: str,
        query: str,
    ) -> tuple[list[RetrievedChunk], bool]:
        """Run semantic + keyword retrieval and decide whether chunks are confident enough."""
        candidate_limit = self.settings.rag_retrieval_candidates
        semantic_ranked = await self._semantic_search(arxiv_id, query, candidate_limit)
        keyword_ranked = await self._keyword_search(paper_id, query, candidate_limit)
        merged = await self._merge_rankings(paper_id, query, semantic_ranked, keyword_ranked)
        top_chunks = merged[: self.settings.rag_chunk_top_k]
        max_confidence = max((c.confidence for c in top_chunks), default=0.0)
        use_chunks = max_confidence >= self.settings.rag_confidence_threshold
        return top_chunks, use_chunks

    async def _semantic_search(
        self,
        arxiv_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[int, float]]:
        results = await self.vector_store.search_papers(
            query=query,
            k=limit,
            filter_dict={"arxiv_id": arxiv_id, "type": "paper_chunk"},
        )

        ranked = []
        for doc, distance in results:
            chunk_id = await self._chunk_id_from_document(arxiv_id, doc)
            if chunk_id is None:
                continue
            ranked.append((chunk_id, self._semantic_confidence(distance)))
        return ranked

    async def _keyword_search(
        self,
        paper_id: int,
        query: str,
        limit: int,
    ) -> list[tuple[int, float]]:
        fts_query = self._fts_query(query)
        if not fts_query:
            return []

        factory = get_session_factory()
        try:
            async with factory() as session:
                result = await session.execute(
                    text("""
                        SELECT pc.id, pc.content
                        FROM paper_chunks_fts fts
                        JOIN paper_chunks pc ON pc.id = fts.paper_chunk_id
                        WHERE pc.paper_id = :paper_id
                          AND paper_chunks_fts MATCH :query
                        ORDER BY bm25(paper_chunks_fts)
                        LIMIT :limit
                    """),
                    {"paper_id": paper_id, "query": fts_query, "limit": limit},
                )
                rows = result.all()
        except Exception as e:
            logger.warning(f"SQLite FTS chunk search failed: {e}")
            return []

        query_tokens = self._tokens(query)
        return [
            (int(row.id), self._keyword_confidence(row.content, query_tokens))
            for row in rows
        ]

    async def _merge_rankings(
        self,
        paper_id: int,
        query: str,
        semantic_ranked: list[tuple[int, float]],
        keyword_ranked: list[tuple[int, float]],
    ) -> list[RetrievedChunk]:
        scores: dict[int, RetrievedChunk] = {}
        chunk_ids = list(dict.fromkeys(
            [chunk_id for chunk_id, _ in semantic_ranked]
            + [chunk_id for chunk_id, _ in keyword_ranked]
        ))
        chunks = await self._load_chunks(paper_id, chunk_ids)

        for chunk_id in chunk_ids:
            chunk = chunks.get(chunk_id)
            if chunk:
                scores[chunk_id] = RetrievedChunk(chunk=chunk)

        rrf_k = self.settings.rag_rrf_k
        for rank, (chunk_id, semantic_score) in enumerate(semantic_ranked, start=1):
            if chunk_id in scores:
                scores[chunk_id].rrf_score += 1.0 / (rrf_k + rank)
                scores[chunk_id].semantic_score = max(scores[chunk_id].semantic_score, semantic_score)

        for rank, (chunk_id, keyword_score) in enumerate(keyword_ranked, start=1):
            if chunk_id in scores:
                scores[chunk_id].rrf_score += 1.0 / (rrf_k + rank)
                scores[chunk_id].keyword_score = max(scores[chunk_id].keyword_score, keyword_score)

        return sorted(
            scores.values(),
            key=lambda item: (item.rrf_score, item.confidence, -item.chunk.chunk_index),
            reverse=True,
        )

    async def _load_chunks(self, paper_id: int, chunk_ids: list[int]) -> dict[int, PaperChunk]:
        if not chunk_ids:
            return {}
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(PaperChunk)
                .where(PaperChunk.paper_id == paper_id, PaperChunk.id.in_(chunk_ids))
            )
            chunks = result.scalars().all()
        return {chunk.id: chunk for chunk in chunks}

    async def _chunk_id_from_document(self, arxiv_id: str, doc: Document) -> Optional[int]:
        chunk_id = doc.metadata.get("paper_chunk_id")
        if chunk_id is not None:
            return int(chunk_id)

        chunk_index = doc.metadata.get("chunk_index")
        if chunk_index is None:
            return None

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(PaperChunk.id)
                .where(PaperChunk.arxiv_id == arxiv_id, PaperChunk.chunk_index == int(chunk_index))
                .limit(1)
            )
            return result.scalar_one_or_none()

    def _page_range(self, chunk: str) -> tuple[Optional[int], Optional[int]]:
        pages = [int(page) for page in re.findall(r"\[Page\s+(\d+)\]", chunk)]
        if not pages:
            return None, None
        return min(pages), max(pages)

    def _semantic_confidence(self, distance: float) -> float:
        """Convert ChromaDB L2 distance to a 0-1 confidence score."""
        try:
            d = float(distance)
            return max(0.0, min(1.0, 1.0 / (1.0 + d)))
        except Exception:
            return 0.0

    def _keyword_confidence(self, content: str, query_tokens: list[str]) -> float:
        if not query_tokens:
            return 0.0
        content_tokens = set(self._tokens(content))
        if not content_tokens:
            return 0.0
        matched = sum(1 for token in query_tokens if token in content_tokens)
        return matched / len(query_tokens)

    def _fts_query(self, query: str) -> str:
        tokens = self._tokens(query)
        return " OR ".join(f'"{token}"' for token in tokens[:12])

    def _tokens(self, text_value: str) -> list[str]:
        return [
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", text_value or "")
        ]


_hybrid_retrieval_service: Optional[HybridRetrievalService] = None


def get_hybrid_retrieval_service() -> HybridRetrievalService:
    """Get or create hybrid retrieval service singleton."""
    global _hybrid_retrieval_service
    if _hybrid_retrieval_service is None:
        _hybrid_retrieval_service = HybridRetrievalService()
    return _hybrid_retrieval_service
