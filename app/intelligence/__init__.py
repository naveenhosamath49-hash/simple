"""Intelligence layer integrating NVIDIA LLM and news analysis engines."""
from app.intelligence.llm_provider import get_llm_provider, BaseLLMProvider, NvidiaLLMProvider, MockLLMProvider
from app.intelligence.summarizer import ArticleSummarizer
from app.intelligence.classifier import NewsClassifier
from app.intelligence.entity_extractor import EntityExtractor
from app.intelligence.trend_analyzer import TrendAnalyzer
from app.intelligence.claim_comparator import ClaimComparator
from app.intelligence.qa import QuestionAnsweringEngine

__all__ = [
    "get_llm_provider",
    "BaseLLMProvider",
    "NvidiaLLMProvider",
    "MockLLMProvider",
    "ArticleSummarizer",
    "NewsClassifier",
    "EntityExtractor",
    "TrendAnalyzer",
    "ClaimComparator",
    "QuestionAnsweringEngine",
]
