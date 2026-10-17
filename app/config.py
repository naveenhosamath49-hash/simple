from __future__ import annotations

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment and .env file."""

    # Project metadata
    PROJECT_NAME: str = "AI News Intelligence Agent"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="development | production | testing")
    LOG_LEVEL: str = Field(default="INFO", description="Logging verbosity")

    # Server configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    BACKEND_API_URL: str = "http://localhost:8000"
    STREAMLIT_SERVER_PORT: int = 8501

    # Security & CORS
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501,http://localhost:3000"
    SECRET_KEY: str = "news-intelligence-dev-secret-change-in-production"

    # News API Configuration
    NEWS_API_KEY: Optional[str] = None
    NEWS_API_BASE_URL: str = "https://newsapi.org/v2"
    NEWS_API_TIMEOUT_SECONDS: int = 15
    NEWS_API_MAX_RETRIES: int = 3

    # NVIDIA NIM LLM Configuration
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3.1-70b-instruct"
    NVIDIA_TIMEOUT_SECONDS: int = 8
    NVIDIA_MAX_RETRIES: int = 2
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1500

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./news_intelligence.db"

    # Supabase Configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Agmarknet / data.gov.in Configuration
    AGMARKNET_API_URL: str = "https://api.data.gov.in/resource"
    AGMARKNET_RESOURCE_ID: str = "9ef84268-d588-465a-a308-a864a43d0070"
    AGMARKNET_API_KEY: Optional[str] = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
    AGMARKNET_TIMEOUT_SECONDS: int = 15
    MARKET_CACHE_TTL_SECONDS: int = 3600

    # Alerts & Notification Configuration
    ALERT_POLL_INTERVAL_MINUTES: int = 60
    MAX_ALERT_ATTEMPTS: int = 5
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    # Processing & Pipeline Settings
    INGESTION_INTERVAL_MINUTES: int = 30
    MAX_ARTICLES_PER_FETCH: int = 50
    DEDUPLICATION_SIMILARITY_THRESHOLD: float = 0.82
    MAX_ARTICLE_CONTENT_LENGTH: int = 6000

    # Categorization taxonomy
    DEFAULT_CATEGORIES: List[str] = [
        "Politics",
        "Business",
        "Technology",
        "Artificial Intelligence",
        "Science",
        "Education",
        "Health",
        "Sports",
        "Entertainment",
        "Local News",
        "International News",
    ]

    # Pre-configured high-reputation RSS Feeds for live news aggregation
    DEFAULT_RSS_FEEDS: List[dict] = [
        {
            "name": "BBC News - World",
            "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
            "category": "International News",
            "language": "en",
            "country": "gb",
        },
        {
            "name": "BBC News - Technology",
            "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "category": "Technology",
            "language": "en",
            "country": "gb",
        },
        {
            "name": "Ars Technica",
            "url": "https://feeds.arstechnica.com/arstechnica/index",
            "category": "Technology",
            "language": "en",
            "country": "us",
        },
        {
            "name": "NPR World News",
            "url": "https://feeds.npr.org/1004/rss.xml",
            "category": "International News",
            "language": "en",
            "country": "us",
        },
        {
            "name": "NPR Technology",
            "url": "https://feeds.npr.org/1019/rss.xml",
            "category": "Technology",
            "language": "en",
            "country": "us",
        },
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a clean list."""
        if not self.CORS_ORIGINS:
            return ["http://localhost:8501"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Global settings singleton
settings = Settings()
