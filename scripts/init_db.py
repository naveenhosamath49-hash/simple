from __future__ import annotations

import datetime
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import SessionLocal, init_db
from app.database.repository import NewsRepository
from app.connectors.base import compute_article_hash, normalize_url

SEED_ARTICLES = [
    {
        "title": "NVIDIA Unveils Next-Gen AI Inference Microservices and Blackwell Platform Expansion",
        "description": "NVIDIA announced broader availability of its NIM microservices and enterprise software stack designed to accelerate generative AI deployment across global data centers.",
        "content": "SANTA CLARA, Calif. — NVIDIA has expanded its enterprise AI ecosystem with new production-ready NIM microservices, optimized for high-throughput inference across multi-cloud environments. The platform integrates accelerated computing libraries with leading open-source models, enabling enterprises to reduce latency and infrastructure costs while maintaining data governance.",
        "url": "https://www.reuters.com/technology/nvidia-announces-ai-platform-expansion-2026-10-14/",
        "publisher_name": "Reuters",
        "publisher_domain": "reuters.com",
        "author": "Stephen Nellis",
        "category": "Artificial Intelligence",
        "country": "us",
        "language": "en",
        "source_type": "official",
        "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        "ai_summary": "NVIDIA announced the expansion of its NIM microservices suite and Blackwell enterprise AI platform to optimize generative model inference across multi-cloud enterprise deployments.",
        "entities": {
            "people": ["Jensen Huang", "Stephen Nellis"],
            "organizations": ["Open Source Initiative"],
            "companies": ["NVIDIA", "Reuters"],
            "locations": ["Santa Clara", "California"],
            "events": ["NVIDIA AI Summit"],
            "products": ["NIM Microservices", "Blackwell Platform"],
        },
        "importance_score": 9.2,
        "importance_breakdown": {"recency": 9.5, "source_diversity": 9.0, "source_quality": 9.5, "public_impact": 9.0},
        "topic": "Generative AI Infrastructure",
    },
    {
        "title": "Global Tech Firms Expand AI Data Center Infrastructure Amid Rising Compute Demand",
        "description": "Major cloud providers and chipmakers are ramping up capital investments in energy-efficient data center architectures to meet surging generative AI workloads.",
        "content": "LONDON — European and American cloud providers announced collaborative ventures to build sustainable data centers powered by nuclear and renewable energy. The investments follow unprecedented demand for large language model training and inference compute capabilities.",
        "url": "https://www.bbc.com/news/technology/data-center-ai-expansion-2026",
        "publisher_name": "BBC News",
        "publisher_domain": "bbc.com",
        "author": "Zoe Kleinman",
        "category": "Technology",
        "country": "gb",
        "language": "en",
        "source_type": "rss",
        "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=4),
        "ai_summary": "Cloud giants are partnering with green energy producers to build next-generation data centers capable of satisfying the massive compute requirements of AI models.",
        "entities": {
            "people": ["Zoe Kleinman"],
            "organizations": ["European Energy Union"],
            "companies": ["BBC", "Microsoft", "Google"],
            "locations": ["London", "Europe"],
            "events": ["Global Green Compute Summit"],
            "products": ["Hyperscale Cloud", "Modular Reactors"],
        },
        "importance_score": 8.7,
        "importance_breakdown": {"recency": 9.0, "source_diversity": 8.5, "source_quality": 9.0, "public_impact": 8.5},
        "topic": "Generative AI Infrastructure",
    },
    {
        "title": "Quantum Computing Breakthrough: Researchers Achieve Fault-Tolerant Logical Qubit Threshold",
        "description": "A consortium of quantum physicists has demonstrated real-time quantum error correction, marking a critical milestone toward practical quantum advantage.",
        "content": "CAMBRIDGE, Mass. — Scientists at Harvard and partner research institutions have demonstrated fault-tolerant quantum error correction with physical error rates below threshold, allowing complex quantum circuits to run without decoherence degradation.",
        "url": "https://arstechnica.com/science/2026/10/quantum-error-correction-milestone/",
        "publisher_name": "Ars Technica",
        "publisher_domain": "arstechnica.com",
        "author": "John Timmer",
        "category": "Science",
        "country": "us",
        "language": "en",
        "source_type": "rss",
        "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=8),
        "ai_summary": "Physicists have successfully demonstrated fault-tolerant quantum error correction, surpassing the threshold necessary for practical logical qubits and commercial quantum computation.",
        "entities": {
            "people": ["John Timmer", "Mikhail Lukin"],
            "organizations": ["Harvard University", "MIT"],
            "companies": ["QuEra Computing"],
            "locations": ["Cambridge", "Massachusetts"],
            "events": ["Quantum Physics Forum"],
            "products": ["Logical Qubits", "Neutral Atom Processor"],
        },
        "importance_score": 8.5,
        "importance_breakdown": {"recency": 8.0, "source_diversity": 8.0, "source_quality": 9.0, "public_impact": 9.0},
        "topic": "Quantum Computing",
    },
    {
        "title": "Federal Reserve Holds Benchmark Interest Rates Steady Amid Mixed Inflation Indicators",
        "description": "The central bank opted to maintain its target interest rate range, emphasizing continued monitoring of labor market conditions and service sector inflation.",
        "content": "WASHINGTON — The Federal Open Market Committee announced its unanimous decision to hold benchmark interest rates steady at 4.75%-5.00%. Policymakers noted that while headline inflation has moderated significantly, shelter and wage growth require sustained vigilance before further easing.",
        "url": "https://www.wsj.com/economy/central-banking/fed-rate-decision-october-2026",
        "publisher_name": "The Wall Street Journal",
        "publisher_domain": "wsj.com",
        "author": "Nick Timiraos",
        "category": "Business",
        "country": "us",
        "language": "en",
        "source_type": "official",
        "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=14),
        "ai_summary": "The Federal Reserve left interest rates unchanged at 4.75%-5.00%, adopting a data-dependent stance as inflation cools but labor markets remain balanced.",
        "entities": {
            "people": ["Jerome Powell", "Nick Timiraos"],
            "organizations": ["Federal Reserve", "FOMC"],
            "companies": ["Wall Street Journal"],
            "locations": ["Washington", "United States"],
            "events": ["FOMC Press Conference"],
            "products": ["Treasury Bonds", "Benchmark Rate"],
        },
        "importance_score": 8.8,
        "importance_breakdown": {"recency": 7.5, "source_diversity": 9.0, "source_quality": 9.5, "public_impact": 9.5},
        "topic": "Monetary Policy & Inflation",
    },
    {
        "title": "Global Leaders Convene in Geneva for International Treaty on Autonomous Defense Systems",
        "description": "Diplomats and ethical experts from 85 nations are drafting safety standards and human-in-the-loop oversight mandates for autonomous military systems.",
        "content": "GENEVA — High-level multilateral negotiations opened at the United Nations European headquarters to formalize binding treaties on autonomous weapons systems. Proponents argue mandatory human oversight protocols are vital to global stability.",
        "url": "https://www.reuters.com/world/geneva-autonomous-defense-treaty-summit-2026/",
        "publisher_name": "Reuters",
        "publisher_domain": "reuters.com",
        "author": "Emma Farge",
        "category": "Politics",
        "country": "ch",
        "language": "en",
        "source_type": "official",
        "published_at": datetime.datetime.utcnow() - datetime.timedelta(hours=20),
        "ai_summary": "Representatives from 85 nations gathered at the UN in Geneva to negotiate binding regulations requiring human oversight for autonomous AI defense systems.",
        "entities": {
            "people": ["Emma Farge", "Antonio Guterres"],
            "organizations": ["United Nations", "International Committee of the Red Cross"],
            "companies": ["Reuters"],
            "locations": ["Geneva", "Switzerland"],
            "events": ["UN Autonomous Weapons Convention"],
            "products": ["Autonomous Systems", "Treaty Draft"],
        },
        "importance_score": 8.9,
        "importance_breakdown": {"recency": 7.0, "source_diversity": 9.0, "source_quality": 9.5, "public_impact": 10.0},
        "topic": "AI Defense & Governance",
    },
]


def seed_database():
    """Initialize DB and seed foundational intelligence data."""
    print("[init_db] Initializing database tables...")
    init_db()

    db = SessionLocal()
    repo = NewsRepository(db)

    print("[init_db] Seeding reference articles and topics...")
    for item in SEED_ARTICLES:
        canon_url = normalize_url(item["url"])
        art_hash = compute_article_hash(canon_url, item["title"])

        art_dict = {
            "original_id": art_hash[:16],
            "title": item["title"],
            "description": item["description"],
            "content": item["content"],
            "url": item["url"],
            "canonical_url": canon_url,
            "article_hash": art_hash,
            "publisher_name": item["publisher_name"],
            "publisher_domain": item["publisher_domain"],
            "author": item["author"],
            "published_at": item["published_at"],
            "language": item["language"],
            "country": item["country"],
            "category": item["category"],
            "source_type": item["source_type"],
            "is_duplicate": False,
            "raw_metadata": {"seeded": True},
        }

        art_obj, was_new = repo.insert_article(art_dict)
        if was_new or not art_obj.ai_analysis:
            repo.save_ai_analysis(
                article_id=art_obj.id,
                summary=item["ai_summary"],
                entities=item["entities"],
                classification={"primary_category": item["category"], "confidence": 0.95},
                importance_score=item["importance_score"],
                importance_breakdown=item["importance_breakdown"],
                claims=[item["title"]],
                model_used="meta/llama-3.1-70b-instruct",
            )

        # Link Topic
        topic_name = item.get("topic")
        if topic_name:
            t = repo.get_or_create_topic(topic_name)
            repo.link_article_to_topic(art_obj.id, t.id)

    # Log initial success
    repo.log_system_event(
        connector_name="SeedService",
        operation="database_initialization",
        status="SUCCESS",
        articles_inserted=len(SEED_ARTICLES),
    )

    db.close()
    print(f"[init_db] Successfully initialized and seeded {len(SEED_ARTICLES)} intelligence records.")


if __name__ == "__main__":
    seed_database()
