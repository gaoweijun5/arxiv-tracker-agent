"""Conversations API endpoints for paper Q&A."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db, Paper, Conversation

router = APIRouter(prefix="/conversations", tags=["conversations"])


class QuestionRequest(BaseModel):
    """Question request model."""
    paper_id: int
    question: str
    conversation_history: Optional[list[dict]] = None


class ConversationResponse(BaseModel):
    """Conversation response model."""
    id: int
    paper_id: int
    user_message: str
    ai_response: str
    created_at: Optional[datetime]


@router.post("/ask")
async def ask_question(request: QuestionRequest):
    """Ask a question about a paper."""
    # Get paper using a short-lived session (avoid holding db open during LLM call)
    from backend.models.database import get_session_factory
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(select(Paper).where(Paper.id == request.paper_id))
        paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Use RAG service for Q&A
    from backend.services.rag_service import get_rag_service
    rag_service = get_rag_service()

    response = await rag_service.ask_question(
        paper_id=request.paper_id,
        arxiv_id=paper.arxiv_id,
        question=request.question,
        conversation_history=request.conversation_history,
    )

    result_payload = {
        "response": response["response"],
        "sources": response.get("sources", []),
        "retrieval_mode": response.get("retrieval_mode"),
        "source_chunks": response.get("source_chunks", []),
        "paper": {
            "id": paper.id,
            "title": paper.title,
            "arxiv_id": paper.arxiv_id,
        },
    }
    if response.get("error"):
        result_payload["error"] = response["error"]
    if response.get("requires_download"):
        result_payload["requires_download"] = True

    return result_payload


@router.get("/{paper_id}", response_model=list[ConversationResponse])
async def get_paper_conversations(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get conversation history for a paper."""
    # Verify paper exists
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Get conversations
    result = await db.execute(
        select(Conversation)
        .where(Conversation.paper_id == paper_id)
        .order_by(Conversation.created_at)
    )
    conversations = result.scalars().all()

    return [ConversationResponse(**c.to_dict()) for c in conversations]


@router.delete("/paper/{paper_id}")
async def clear_paper_conversations(paper_id: int, db: AsyncSession = Depends(get_db)):
    """Delete all conversations for a paper."""
    result = await db.execute(
        select(Conversation).where(Conversation.paper_id == paper_id)
    )
    conversations = result.scalars().all()

    for conv in conversations:
        await db.delete(conv)
    await db.commit()

    return {"message": f"Deleted {len(conversations)} conversations"}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a conversation."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversation deleted"}
