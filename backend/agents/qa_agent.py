"""LangGraph agent for paper Q&A conversations."""

from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from loguru import logger


class QAState(TypedDict):
    """State for the Q&A agent."""

    # Paper context
    paper_id: int
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str

    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    context: str  # Retrieved context from RAG

    # Output
    response: Optional[str]
    sources: list[str]  # Which parts of paper were used


def create_qa_workflow() -> StateGraph:
    """Create the paper Q&A workflow.

    Returns:
        Compiled StateGraph workflow
    """

    async def retrieve_context(state: QAState) -> QAState:
        """Node: Retrieve relevant context from paper using RAG."""
        logger.info("Retrieving context for Q&A...")
        from backend.services.vector_store import get_vector_store

        vector_store = get_vector_store()

        # Get the latest user message
        messages = state.get("messages", [])
        if not messages:
            return {**state, "context": "", "sources": []}

        question = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""

        if not question:
            return {**state, "context": "", "sources": []}

        # Retrieve relevant chunks
        arxiv_id = state.get("arxiv_id", "")
        try:
            context = await vector_store.get_paper_context(
                arxiv_id=arxiv_id,
                query=question,
                k=5,
            )
            logger.info(f"Retrieved {len(context)} chars of context")
            return {**state, "context": context}
        except Exception as e:
            logger.warning(f"Failed to retrieve context: {e}")
            # Fallback to abstract
            return {**state, "context": state.get("abstract", "")}

    async def generate_response(state: QAState) -> QAState:
        """Node: Generate AI response using context."""
        logger.info("Generating Q&A response...")
        from backend.services.llm_service import get_llm_service

        llm_service = get_llm_service()

        messages = state.get("messages", [])
        if not messages:
            return {**state, "response": "No question provided."}

        question = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
        context = state.get("context", "")
        title = state.get("title", "")
        authors = state.get("authors", [])

        try:
            response = await llm_service.answer_question(
                question=question,
                context=context,
                title=title,
                authors=authors,
            )
            logger.info("Generated Q&A response")
            return {
                **state,
                "response": response,
                "messages": [AIMessage(content=response)],
            }
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            error_msg = "I'm sorry, I encountered an error while processing your question. Please try again."
            return {
                **state,
                "response": error_msg,
                "messages": [AIMessage(content=error_msg)],
            }

    async def save_conversation(state: QAState) -> QAState:
        """Node: Save conversation to database."""
        logger.info("Saving conversation...")
        from backend.models.database import get_session_factory, Conversation

        factory = get_session_factory()
        messages = state.get("messages", [])

        if len(messages) >= 2:
            user_msg = messages[-2].content if isinstance(messages[-2], HumanMessage) else ""
            ai_msg = messages[-1].content if isinstance(messages[-1], AIMessage) else ""

            async with factory() as session:
                conversation = Conversation(
                    paper_id=state.get("paper_id"),
                    user_message=user_msg,
                    ai_response=ai_msg,
                    context_used=state.get("context", "")[:1000],  # Truncate for storage
                )
                session.add(conversation)
                await session.commit()

        return state

    # Build the workflow graph
    workflow = StateGraph(QAState)

    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("save_conversation", save_conversation)

    # Define edges
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "generate_response")
    workflow.add_edge("generate_response", "save_conversation")
    workflow.add_edge("save_conversation", END)

    # Compile the workflow
    return workflow.compile()


# Singleton instance
_qa_workflow = None


def get_qa_workflow() -> StateGraph:
    """Get or create Q&A workflow singleton."""
    global _qa_workflow
    if _qa_workflow is None:
        _qa_workflow = create_qa_workflow()
    return _qa_workflow
