from __future__ import annotations

import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    Table,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.database.database import Base


# Many-to-Many association between Articles and Topics
ArticleTopic = Table(
    "article_topics",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", Integer, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
)


class Article(Base):
    """Normalized news article stored in database."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_hash = Column(String(64), unique=True, index=True, nullable=False, doc="SHA-256 fingerprint for exact deduplication")
    original_id = Column(String(255), nullable=True, doc="Identifier provided by source API")
    title = Column(String(512), nullable=False, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    url = Column(String(2048), nullable=False, index=True)
    canonical_url = Column(String(2048), nullable=False, index=True)
    image_url = Column(String(2048), nullable=True)
    publisher_name = Column(String(255), nullable=False, index=True)
    publisher_domain = Column(String(255), nullable=True, index=True)
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    retrieved_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    language = Column(String(10), default="en", index=True)
    country = Column(String(10), default="us", index=True)
    category = Column(String(100), default="General", index=True)
    source_type = Column(String(50), default="newsapi", index=True)
    raw_metadata = Column(JSON, nullable=True)
    
    # Deduplication and clustering flags
    is_duplicate = Column(Boolean, default=False, index=True)
    duplicate_of_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    cluster_id = Column(String(64), nullable=True, index=True)

    # Relationships
    ai_analysis = relationship("AIAnalysis", back_populates="article", uselist=False, cascade="all, delete-orphan")
    topics = relationship("Topic", secondary=ArticleTopic, back_populates="articles")

    __table_args__ = (
        Index("ix_articles_published_category", "published_at", "category"),
        Index("ix_articles_domain_date", "publisher_domain", "published_at"),
    )

    def to_dict(self) -> dict:
        """Serialize article model to dictionary."""
        return {
            "id": self.id,
            "article_hash": self.article_hash,
            "original_id": self.original_id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "image_url": self.image_url,
            "publisher_name": self.publisher_name,
            "publisher_domain": self.publisher_domain,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "language": self.language,
            "country": self.country,
            "category": self.category,
            "source_type": self.source_type,
            "is_duplicate": self.is_duplicate,
            "duplicate_of_id": self.duplicate_of_id,
            "cluster_id": self.cluster_id,
            "ai_analysis": self.ai_analysis.to_dict() if self.ai_analysis else None,
        }


class AIAnalysis(Base):
    """AI analysis metadata and insights generated for an article."""
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    entities = Column(JSON, default=dict, nullable=False, doc="Extracted people, organizations, locations, etc.")
    classification = Column(JSON, default=dict, nullable=False, doc="Category, confidence, subcategories")
    importance_score = Column(Float, default=5.0, index=True, doc="0.0 to 10.0 scale")
    importance_breakdown = Column(JSON, default=dict, nullable=True)
    claims = Column(JSON, default=list, nullable=True, doc="Key factual claims extracted from article")
    model_used = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationship
    article = relationship("Article", back_populates="ai_analysis")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "summary": self.summary,
            "entities": self.entities,
            "classification": self.classification,
            "importance_score": self.importance_score,
            "importance_breakdown": self.importance_breakdown,
            "claims": self.claims,
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Topic(Base):
    """Aggregated topic or story cluster tracked across multiple articles."""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    first_observed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_observed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    article_count = Column(Integer, default=1, index=True)
    trend_score = Column(Float, default=1.0, index=True)
    is_emerging = Column(Boolean, default=False, index=True)
    trend_metrics = Column(JSON, default=dict, nullable=True)

    # Relationships
    articles = relationship("Article", secondary=ArticleTopic, back_populates="topics")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "first_observed_at": self.first_observed_at.isoformat() if self.first_observed_at else None,
            "last_observed_at": self.last_observed_at.isoformat() if self.last_observed_at else None,
            "article_count": self.article_count,
            "trend_score": round(self.trend_score, 2),
            "is_emerging": self.is_emerging,
            "trend_metrics": self.trend_metrics,
        }


class SystemLog(Base):
    """Operational audit log for connector actions, sync events, and errors."""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    connector_name = Column(String(100), nullable=False, index=True)
    operation = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True, doc="SUCCESS | ERROR | WARNING | SKIPPED")
    error_details = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    articles_fetched = Column(Integer, default=0)
    articles_inserted = Column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connector_name": self.connector_name,
            "operation": self.operation,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
            "error_details": self.error_details,
            "retry_count": self.retry_count,
            "articles_fetched": self.articles_fetched,
            "articles_inserted": self.articles_inserted,
        }
