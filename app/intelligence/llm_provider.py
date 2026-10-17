from __future__ import annotations

import abc
import json
import logging
import time
from typing import List, Dict, Optional, Any
import httpx

from app.config import settings
from app.security.validation import mask_secret

logger = logging.getLogger(__name__)


class BaseLLMProvider(abc.ABC):
    """Abstract provider interface for interchangeable language model integrations."""

    @abc.abstractmethod
    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format_json: bool = False,
    ) -> str:
        """Execute chat completion against LLM backend."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check whether LLM credentials and endpoint are operational."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Return identifier of active model."""
        pass


class NvidiaLLMProvider(BaseLLMProvider):
    """
    NVIDIA NIM API LLM provider (https://integrate.api.nvidia.com/v1).
    Utilizes hosted foundation models from the NVIDIA API Catalog with exponential backoff.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 45,
        max_retries: int = 3,
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")
        self._model_name = model or settings.NVIDIA_MODEL
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        """Check if NVIDIA API key is populated and not a placeholder."""
        return bool(
            self.api_key
            and self.api_key.strip()
            and self.api_key != "your_nvidia_api_key_here"
            and not self.api_key.startswith("nvapi-placeholder")
        )

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format_json: bool = False,
    ) -> str:
        """
        Invoke NVIDIA chat completions endpoint with retry logic and error isolation.
        """
        if not self.is_available():
            raise ValueError("NVIDIA_API_KEY is not configured or contains placeholder.")

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AINewsIntelligenceAgent/1.0",
        }

        payload: Dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
        }

        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 429:
                    logger.warning(f"[NVIDIA LLM] Rate limited (HTTP 429). Attempt {attempt}/{self.max_retries}.")
                    if attempt == self.max_retries:
                        raise RuntimeError("NVIDIA NIM API rate limit exceeded.")
                    time.sleep(delay)
                    delay *= 2
                    continue

                if response.status_code == 401:
                    logger.error("[NVIDIA LLM] Authentication failure (HTTP 401). Invalid API key.")
                    raise PermissionError("Invalid NVIDIA API Key provided.")

                if response.status_code >= 500:
                    logger.warning(f"[NVIDIA LLM] Server error (HTTP {response.status_code}). Retrying...")
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise ValueError("NVIDIA API returned empty choices list.")

                content = choices[0].get("message", {}).get("content", "")
                return content.strip()

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.error(f"[NVIDIA LLM] Network error (attempt {attempt}): {exc}")
                if attempt == self.max_retries:
                    raise RuntimeError(f"NVIDIA API communication failed: {exc}")
                time.sleep(delay)
                delay *= 2

        raise RuntimeError("Failed to obtain LLM completion after multiple attempts.")


class MockLLMProvider(BaseLLMProvider):
    """
    High-fidelity heuristic intelligence provider for offline testing, local validation,
    and graceful fallback when external NVIDIA API keys are not supplied.
    """

    def __init__(self, model_name: str = "mock-intelligence-engine-v1"):
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return True

    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format_json: bool = False,
    ) -> str:
        """Produce structured response based on message content."""
        prompt_text = " ".join([m.get("content", "") for m in messages])

        # If requesting JSON (summarization/classification/entities)
        if response_format_json or "json" in prompt_text.lower():
            # Check prompt context
            if "claim" in prompt_text.lower() and "compare" in prompt_text.lower():
                return json.dumps({
                    "summary_of_consensus": "Multiple reporting outlets corroborate key timeline facts, while specific casualty or impact figures show slight variance across independent reports.",
                    "supported_by_multiple_sources": [
                        "Primary event occurrence and geographical location verified by all reporting outlets.",
                        "Official spokesperson statements matched across independent wires."
                    ],
                    "single_source_claims": [
                        "Exclusive preliminary impact estimations reported only by initial local correspondent."
                    ],
                    "conflicting_claims": [
                        "Variance between initial source headline and revised official dispatch regarding project completion date."
                    ],
                    "unverified_claims": [
                        "Anonymous social commentary cited in secondary reporting."
                    ],
                    "confidence_score": 0.85
                })

            # Check if this is Question Answering
            if "answer" in prompt_text.lower() and "question" in prompt_text.lower():
                return json.dumps({
                    "answer": "Based on the collected intelligence reports, technology developments are focused on generative AI infrastructure and regulatory compliance, while global trade and market reports highlight cautious expansion in semiconductor and energy sectors.",
                    "evidence_level": "SUFFICIENT",
                    "key_points": [
                        "Multiple independent articles cite advancements in enterprise compute hardware.",
                        "Global regulatory oversight is expanding across North America and Europe."
                    ]
                })

            # Default article analysis JSON
            # Infer category heuristically
            cat = "Technology"
            if any(k in prompt_text.lower() for k in ["politics", "election", "government", "parliament", "senate", "minister"]):
                cat = "Politics"
            elif any(k in prompt_text.lower() for k in ["stock", "market", "economy", "revenue", "quarterly", "profit", "bank"]):
                cat = "Business"
            elif any(k in prompt_text.lower() for k in ["health", "vaccine", "hospital", "medical", "disease", "cancer"]):
                cat = "Health"
            elif any(k in prompt_text.lower() for k in ["science", "space", "nasa", "physics", "climate", "planet"]):
                cat = "Science"
            elif any(k in prompt_text.lower() for k in ["ai", "nvidia", "artificial intelligence", "llm", "deep learning"]):
                cat = "Artificial Intelligence"

            return json.dumps({
                "summary": "This report details significant current developments within the sector, synthesizing statements from primary industry stakeholders, official statistics, and market context to outline near-term implications.",
                "category": cat,
                "subcategories": ["Current Affairs", "Industry Developments"],
                "confidence": 0.92,
                "entities": {
                    "people": ["Industry Spokesperson", "Lead Analyst"],
                    "organizations": ["Regulatory Agency", "Research Consortium"],
                    "companies": ["Key Publisher Corp", "Global Enterprises"],
                    "locations": ["Washington", "London", "Global"],
                    "events": ["Annual Industry Forum", "Quarterly Briefing"],
                    "products": ["Enterprise AI Platform", "Next-Gen Infrastructure"]
                },
                "importance_score": 7.8,
                "importance_breakdown": {
                    "recency": 8.5,
                    "relevance": 8.0,
                    "source_credibility": 7.5,
                    "public_impact": 7.2
                },
                "key_claims": [
                    "Stakeholders confirmed revised delivery targets for upcoming operational cycle.",
                    "Independent economic metrics indicated continued resilience across reporting sectors."
                ]
            })

        # Plain text response
        return "Intelligence assessment indicates steady sector activity with key developments documented in recent dispatches."


def get_llm_provider(force_mock: bool = False) -> BaseLLMProvider:
    """
    Factory creating either live NVIDIA LLM provider or MockLLMProvider
    depending on available API credentials and configuration.
    """
    if force_mock:
        return MockLLMProvider()

    nvidia_provider = NvidiaLLMProvider()
    if nvidia_provider.is_available():
        logger.info(f"Using live NVIDIA LLM provider with model: {nvidia_provider.model_name}")
        return nvidia_provider

    logger.warning("NVIDIA_API_KEY not configured or invalid. Activating high-fidelity fallback intelligence provider.")
    return MockLLMProvider()
