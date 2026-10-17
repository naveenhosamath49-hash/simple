from __future__ import annotations

import datetime
import math
import logging
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Established authoritative domains get higher baseline quality ratings
REPUTABLE_DOMAINS = {
    "bbc.co.uk", "bbc.com", "reuters.com", "apnews.com", "npr.org",
    "nytimes.com", "wsj.com", "washingtonpost.com", "nature.com",
    "arstechnica.com", "techcrunch.com", "bloomberg.com", "ft.com",
}


class TrendAnalyzer:
    """
    Analyzes temporal frequency, multi-source velocity, and importance scoring.
    Enforces strict objectivity:
    - Never declares a topic trending based on a single article.
    - Never equates popularity with factual veracity.
    """

    def __init__(self, observation_window_hours: int = 48):
        self.observation_window_hours = observation_window_hours

    def calculate_importance(
        self,
        published_at: datetime.datetime,
        publisher_domain: Optional[str] = None,
        independent_sources_count: int = 1,
        content_length: int = 500,
        query: Optional[str] = None,
        title: str = "",
    ) -> Dict[str, Any]:
        """
        Calculate transparent importance score on a 0.0 to 10.0 scale.
        Breakdown includes:
        - Recency (0-10)
        - Source Diversity (0-10)
        - Source Quality (0-10)
        - Estimated Public Impact (0-10)
        - Query Relevance (0-10, if query provided)
        """
        now = datetime.datetime.utcnow()
        hours_old = max(0.0, (now - published_at).total_seconds() / 3600.0)

        # 1. Recency Decay (exponential half-life of 24 hours)
        recency_score = 10.0 * math.exp(-0.028 * hours_old)
        recency_score = max(1.0, min(10.0, recency_score))

        # 2. Source Diversity (multi-source confirmation)
        if independent_sources_count >= 5:
            diversity_score = 10.0
        elif independent_sources_count >= 3:
            diversity_score = 8.5
        elif independent_sources_count == 2:
            diversity_score = 6.0
        else:
            diversity_score = 3.5  # Single source reporting

        # 3. Source Quality
        clean_domain = (publisher_domain or "").lower()
        if any(rep in clean_domain for rep in REPUTABLE_DOMAINS):
            quality_score = 9.0
        elif clean_domain:
            quality_score = 6.5
        else:
            quality_score = 5.0

        # 4. Public Impact Indicator (keyword / scope heuristic)
        impact_keywords = [
            "crisis", "treaty", "outbreak", "breakthrough", "sanction", "merger",
            "regulation", "resignation", "verdict", "discovery", "emergency", "election",
            "summit", "accord", "ban", "passed", "security", "war", "peace"
        ]
        title_lower = title.lower()
        impact_matches = sum(1 for kw in impact_keywords if kw in title_lower)
        impact_score = min(10.0, 4.0 + (impact_matches * 2.0))

        # 5. Query Relevance
        if query:
            q_words = [w.lower() for w in query.split() if len(w) > 2]
            if q_words:
                matches = sum(1 for w in q_words if w in title_lower)
                relevance_score = min(10.0, (matches / len(q_words)) * 10.0)
            else:
                relevance_score = 7.0
        else:
            relevance_score = 7.0

        # Weighted calculation
        # Weights: Recency 25%, Diversity 25%, Impact 25%, Quality 15%, Relevance 10%
        final_score = (
            (recency_score * 0.25)
            + (diversity_score * 0.25)
            + (impact_score * 0.25)
            + (quality_score * 0.15)
            + (relevance_score * 0.10)
        )
        final_score = round(max(0.0, min(10.0, final_score)), 2)

        return {
            "score": final_score,
            "breakdown": {
                "recency": round(recency_score, 2),
                "source_diversity": round(diversity_score, 2),
                "independent_sources": independent_sources_count,
                "source_quality": round(quality_score, 2),
                "public_impact": round(impact_score, 2),
                "relevance": round(relevance_score, 2),
            },
        }

    def extract_topic_keywords(self, articles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Group articles into topics based on normalized entity overlaps and significant phrase tokens.
        Ensures a topic is only flagged as trending if supported by >= 2 independent publishers.
        """
        now = datetime.datetime.utcnow()
        cutoff = now - datetime.timedelta(hours=self.observation_window_hours)

        topic_clusters: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "articles": [],
            "publishers": set(),
            "first_seen": now,
            "last_seen": cutoff,
        })

        for art in articles:
            pub_date = art.get("published_at")
            if isinstance(pub_date, str):
                try:
                    pub_date = datetime.datetime.fromisoformat(pub_date)
                except Exception:
                    pub_date = now

            # Extract candidate topic labels from entities if available, or significant title bigrams
            candidate_topics = []
            entities = art.get("entities") or {}
            for org in entities.get("organizations", [])[:2]:
                if len(org) > 3:
                    candidate_topics.append(org)
            for comp in entities.get("companies", [])[:2]:
                if len(comp) > 3:
                    candidate_topics.append(comp)
            for evt in entities.get("events", [])[:2]:
                if len(evt) > 3:
                    candidate_topics.append(evt)

            # Fallback to key title phrases if no entities
            if not candidate_topics:
                title = art.get("title", "")
                words = [w for w in re.sub(r"[^\w\s]", "", title).split() if len(w) > 4 and w.lower() not in {"about", "their", "after", "which", "there", "first", "could", "would"}]
                if len(words) >= 2:
                    candidate_topics.append(f"{words[0]} {words[1]}")
                elif len(words) == 1:
                    candidate_topics.append(words[0])

            publisher = art.get("publisher_name") or "Unknown"

            for topic_name in candidate_topics:
                topic_key = topic_name.strip().title()
                if len(topic_key) < 3:
                    continue

                cluster = topic_clusters[topic_key]
                cluster["articles"].append(art)
                cluster["publishers"].add(publisher)
                if pub_date < cluster["first_seen"]:
                    cluster["first_seen"] = pub_date
                if pub_date > cluster["last_seen"]:
                    cluster["last_seen"] = pub_date

        results: Dict[str, Dict[str, Any]] = {}

        for topic_key, cluster in topic_clusters.items():
            num_articles = len(cluster["articles"])
            num_publishers = len(cluster["publishers"])

            # RULE: A topic cannot be trending unless reported by >= 2 independent sources
            is_trending = num_articles >= 2 and num_publishers >= 2

            # Velocity: articles per hour over observation window
            span_hours = max(1.0, (cluster["last_seen"] - cluster["first_seen"]).total_seconds() / 3600.0)
            velocity = round(num_articles / span_hours, 2)

            # Trend Score: combines article volume, publisher diversity, and recency velocity
            trend_score = (num_articles * 1.5) + (num_publishers * 2.0) + (velocity * 3.0)
            if not is_trending:
                trend_score = min(trend_score, 2.5)  # Cap single-source topics

            # Emerging flag: topic first appeared within last 12 hours with >= 2 sources
            hours_since_first = (now - cluster["first_seen"]).total_seconds() / 3600.0
            is_emerging = is_trending and hours_since_first <= 12.0 and velocity >= 0.5

            results[topic_key] = {
                "name": topic_key,
                "article_count": num_articles,
                "publisher_count": num_publishers,
                "publishers": list(cluster["publishers"]),
                "first_seen": cluster["first_seen"],
                "last_seen": cluster["last_seen"],
                "velocity": velocity,
                "trend_score": round(trend_score, 2),
                "is_trending": is_trending,
                "is_emerging": is_emerging,
                "sample_articles": [
                    {"id": a.get("id"), "title": a.get("title"), "url": a.get("url")}
                    for a in cluster["articles"][:3]
                ],
            }

        return results
