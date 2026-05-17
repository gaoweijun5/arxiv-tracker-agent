"""Vector store service using ChromaDB for semantic search."""

from typing import Optional, List
import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from loguru import logger

from backend.core.config import get_settings


class OpenAICompatibleEmbeddings(Embeddings):
    """Embeddings wrapper for any OpenAI-compatible API (DeepSeek, DashScope, OpenAI, etc.)."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model

    def _call_api(self, texts: List[str]) -> List[List[float]:
        """Call OpenAI-compatible embedding API."""
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": texts,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        # Sort by index to maintain order
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        all_embeddings = []
        chunk_size = 10
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i + chunk_size]
            embeddings = self._call_api(chunk)
            all_embeddings.extend(embeddings)
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self._call_api([text])[0]


class VectorStoreService:
    """Service for managing vector embeddings and semantic search."""

    _embeddings = None
    _initialized = False

    def __init__(self):
        self.settings = get_settings()
        self._papers_store = None
        self._interests_store = None

    @property
    def embeddings(self):
        """Get embeddings - use configured embedding API."""
        if VectorStoreService._embeddings is None and not VectorStoreService._initialized:
            VectorStoreService._initialized = True
            try:
                VectorStoreService._embeddings = OpenAICompatibleEmbeddings(
                    api_key=self.settings.embedding_api_key,
                    base_url=self.settings.embedding_api_base,
                    model=self.settings.embedding_model,
                )
                logger.info(f"Using embedding API: {self.settings.embedding_model} @ {self.settings.embedding_api_base}")
            except Exception as e:
                logger.warning(f"Failed to init embedding API: {e}")
                VectorStoreService._embeddings = None
        return VectorStoreService._embeddings

    @property
    def papers_store(self):
        """Get or create papers vector store."""
        if self._papers_store is None and self.embeddings is not None:
            try:
                from langchain_community.vectorstores import Chroma
                self._papers_store = Chroma(
                    collection_name="papers",
                    embedding_function=self.embeddings,
                    persist_directory=self.settings.chroma_persist_dir,
                )
            except Exception as e:
                logger.warning(f"Failed to create papers store: {e}")
        return self._papers_store

    @property
    def interests_store(self):
        """Get or create interests vector store."""
        if self._interests_store is None and self.embeddings is not None:
            try:
                from langchain_community.vectorstores import Chroma
                self._interests_store = Chroma(
                    collection_name="interests",
                    embedding_function=self.embeddings,
                    persist_directory=self.settings.chroma_persist_dir,
                )
            except Exception as e:
                logger.warning(f"Failed to create interests store: {e}")
        return self._interests_store

    async def add_paper(
        self,
        arxiv_id: str,
        title: str,
        abstract: str,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Add a paper to the vector store.

        Args:
            arxiv_id: ArXiv paper ID
            title: Paper title
            abstract: Paper abstract
            metadata: Additional metadata

        Returns:
            Document ID in vector store or None if unavailable
        """
        if self.papers_store is None:
            logger.warning("Vector store unavailable, skipping paper addition")
            return None

        doc = Document(
            page_content=f"{title}\n\n{abstract}",
            metadata={
                "arxiv_id": arxiv_id,
                "title": title,
                "type": "paper",
                **(metadata or {}),
            },
        )
        doc_id = self.papers_store.add_documents([doc])[0]
        logger.info(f"Added paper {arxiv_id} to vector store")
        return doc_id

    async def add_paper_chunks(
        self,
        arxiv_id: str,
        title: str,
        chunks: list[str],
        metadata: Optional[dict] = None,
    ) -> list[str]:
        """Add paper content chunks to the vector store for RAG.

        Args:
            arxiv_id: ArXiv paper ID
            title: Paper title
            chunks: List of text chunks from the paper
            metadata: Additional metadata

        Returns:
            List of document IDs
        """
        if self.papers_store is None:
            logger.warning("Vector store unavailable, skipping chunks addition")
            return []

        docs = [
            Document(
                page_content=chunk,
                metadata={
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "chunk_index": i,
                    "type": "paper_chunk",
                    **(metadata or {}),
                },
            )
            for i, chunk in enumerate(chunks)
        ]
        doc_ids = self.papers_store.add_documents(docs)
        logger.info(f"Added {len(chunks)} chunks for paper {arxiv_id}")
        return doc_ids

    async def add_interest(
        self,
        interest_id: int,
        topic: str,
        description: str,
        keywords: list[str],
    ) -> Optional[str]:
        """Add a user interest to the vector store.

        Args:
            interest_id: Interest ID in database
            topic: Interest topic
            description: Interest description
            keywords: Related keywords

        Returns:
            Document ID in vector store or None if unavailable
        """
        if self.interests_store is None:
            logger.warning("Vector store unavailable, skipping interest addition")
            return None

        content = f"{topic}\n{description}\nKeywords: {', '.join(keywords)}"
        doc = Document(
            page_content=content,
            metadata={
                "interest_id": interest_id,
                "topic": topic,
                "type": "interest",
            },
        )
        doc_id = self.interests_store.add_documents([doc])[0]
        logger.info(f"Added interest '{topic}' to vector store")
        return doc_id

    async def search_papers(
        self,
        query: str,
        k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[tuple[Document, float]]:
        """Search for relevant papers using semantic similarity.

        Args:
            query: Search query
            k: Number of results
            filter_dict: Metadata filter

        Returns:
            List of (document, score) tuples
        """
        if self.papers_store is None:
            logger.warning("Vector store unavailable, returning empty results")
            return []

        results = self.papers_store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter_dict,
        )
        return results

    async def search_papers_for_interest(
        self,
        interest_topic: str,
        interest_keywords: list[str],
        k: int = 20,
    ) -> list[tuple[Document, float]]:
        """Search papers matching a specific interest.

        Args:
            interest_topic: Interest topic
            interest_keywords: Interest keywords
            k: Number of results

        Returns:
            List of matching papers with scores
        """
        query = f"{interest_topic} {' '.join(interest_keywords)}"
        return await self.search_papers(query=query, k=k, filter_dict={"type": "paper"})

    async def search_similar_papers(
        self,
        query: str,
        k: int = 10,
    ) -> list[dict]:
        """Search for similar papers and return as dict list.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of paper dicts with scores
        """
        results = await self.search_papers(
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

    async def get_paper_context(
        self,
        arxiv_id: str,
        query: str,
        k: int = 5,
    ) -> str:
        """Get relevant context from a paper for RAG Q&A.

        Args:
            arxiv_id: ArXiv paper ID
            query: User's question
            k: Number of chunks to retrieve

        Returns:
            Concatenated context string
        """
        if self.papers_store is None:
            logger.warning("Vector store unavailable, returning empty context")
            return ""

        results = self.papers_store.similarity_search(
            query=query,
            k=k,
            filter={"arxiv_id": arxiv_id, "type": "paper_chunk"},
        )
        context = "\n\n---\n\n".join([doc.page_content for doc in results])
        return context

    async def get_full_paper_text(self, arxiv_id: str) -> str:
        """Get the full text of a paper by retrieving all chunks.

        Args:
            arxiv_id: ArXiv paper ID

        Returns:
            Full paper text with chunks joined in order
        """
        if self.papers_store is None:
            logger.warning("Vector store unavailable, returning empty text")
            return ""

        # Get all chunks for this paper
        results = self.papers_store.get(
            where={"arxiv_id": arxiv_id, "type": "paper_chunk"},
        )

        if not results or not results.get("documents"):
            logger.warning(f"No chunks found for paper {arxiv_id}")
            return ""

        # Sort by chunk_index from metadata
        docs_with_meta = zip(
            results["documents"],
            results.get("metadatas", [{}] * len(results["documents"])),
        )
        sorted_docs = sorted(
            docs_with_meta, key=lambda x: x[1].get("chunk_index", 0)
        )

        full_text = "\n\n".join(doc for doc, _ in sorted_docs)
        logger.info(f"Retrieved full text for {arxiv_id}: {len(full_text)} chars")
        return full_text

    async def delete_paper(self, arxiv_id: str) -> None:
        """Delete a paper from the vector store."""
        if self.papers_store is None:
            logger.warning("Vector store unavailable, skipping paper deletion")
            return

        # Get all documents with this arxiv_id
        self.papers_store.delete(where={"arxiv_id": arxiv_id})
        logger.info(f"Deleted paper {arxiv_id} from vector store")

    async def delete_interest(self, interest_id: int) -> None:
        """Delete an interest from the vector store."""
        if self.interests_store is None:
            logger.warning("Vector store unavailable, skipping interest deletion")
            return

        self.interests_store.delete(where={"interest_id": interest_id})
        logger.info(f"Deleted interest {interest_id} from vector store")


# Singleton instance
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store() -> VectorStoreService:
    """Get or create vector store service singleton."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service
