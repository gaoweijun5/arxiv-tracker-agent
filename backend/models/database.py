"""Database models and connection setup."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Paper(Base):
    """ArXiv paper model."""

    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    arxiv_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    authors = Column(JSON, nullable=False)  # List of author names
    abstract = Column(Text, nullable=False)
    categories = Column(JSON, nullable=False)  # List of arXiv categories
    published_date = Column(DateTime, nullable=False)
    updated_date = Column(DateTime, nullable=True)
    pdf_url = Column(String(500), nullable=True)
    local_pdf_path = Column(String(500), nullable=True)

    # AI-generated content
    ai_summary = Column(Text, nullable=True)
    ai_summary_zh = Column(Text, nullable=True)  # Chinese summary
    key_findings = Column(JSON, nullable=True)  # List of key findings
    relevance_score = Column(Float, nullable=True)

    # Status tracking
    is_downloaded = Column(Boolean, default=False)
    is_relevant = Column(Boolean, nullable=True)  # User feedback
    is_read = Column(Boolean, default=False)
    is_bookmarked = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    recommendations = relationship("PaperRecommendation", back_populates="paper")
    conversations = relationship("Conversation", back_populates="paper")

    def to_dict(self) -> dict:
        """Convert paper to dictionary."""
        return {
            "id": self.id,
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "categories": self.categories,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "pdf_url": self.pdf_url,
            "ai_summary": self.ai_summary,
            "ai_summary_zh": self.ai_summary_zh,
            "key_findings": self.key_findings,
            "relevance_score": self.relevance_score,
            "is_downloaded": self.is_downloaded,
            "is_relevant": self.is_relevant,
            "is_read": self.is_read,
            "is_bookmarked": self.is_bookmarked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserInterest(Base):
    """User research interest model."""

    __tablename__ = "user_interests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)  # List of keywords
    categories = Column(JSON, nullable=True)  # Preferred arXiv categories
    weight = Column(Float, default=1.0)  # Importance weight
    is_active = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert interest to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "description": self.description,
            "keywords": self.keywords,
            "categories": self.categories,
            "weight": self.weight,
            "is_active": self.is_active,
        }


class PaperRecommendation(Base):
    """Paper recommendation record."""

    __tablename__ = "paper_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    interest_id = Column(Integer, ForeignKey("user_interests.id"), nullable=True)
    score = Column(Float, nullable=False)  # Recommendation score
    reason = Column(Text, nullable=True)  # Why this paper is recommended
    is_viewed = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)

    # Metadata
    recommended_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    paper = relationship("Paper", back_populates="recommendations")
    interest = relationship("UserInterest")

    def to_dict(self) -> dict:
        """Convert recommendation to dictionary."""
        return {
            "id": self.id,
            "paper": self.paper.to_dict() if self.paper else None,
            "score": self.score,
            "reason": self.reason,
            "is_viewed": self.is_viewed,
            "is_dismissed": self.is_dismissed,
            "recommended_at": self.recommended_at.isoformat() if self.recommended_at else None,
        }


class Conversation(Base):
    """Conversation history for paper Q&A."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    context_used = Column(Text, nullable=True)  # RAG context used

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    paper = relationship("Paper", back_populates="conversations")

    def to_dict(self) -> dict:
        """Convert conversation to dictionary."""
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "user_message": self.user_message,
            "ai_response": self.ai_response,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FetchLog(Base):
    """Log of arXiv fetch operations."""

    __tablename__ = "fetch_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fetch_date = Column(DateTime, nullable=False)
    source = Column(String(20), default="manual")  # manual, auto
    categories_fetched = Column(JSON, nullable=True)
    papers_found = Column(Integer, default=0)
    papers_relevant = Column(Integer, default=0)
    papers_downloaded = Column(Integer, default=0)
    status = Column(String(20), nullable=False)  # success, failed, partial
    error_message = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


class SchedulerConfig(Base):
    """Scheduler configuration."""

    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(50), unique=True, nullable=False)
    hour = Column(Integer, nullable=False, default=8)
    minute = Column(Integer, nullable=False, default=0)
    is_enabled = Column(Boolean, default=True)

    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "hour": self.hour,
            "minute": self.minute,
            "is_enabled": self.is_enabled,
        }


# Database engine and session factory
_engine = None
_session_factory = None


def get_engine(database_url: str = "sqlite+aiosqlite:///./data/arxiv_tracker.db"):
    """Get or create async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(database_url, echo=False)
    return _engine


def get_session_factory(database_url: str = "sqlite+aiosqlite:///./data/arxiv_tracker.db"):
    """Get or create session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(database_url: str = "sqlite+aiosqlite:///./data/arxiv_tracker.db"):
    """Initialize database tables."""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
