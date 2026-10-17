from __future__ import annotations

import argparse
import os
import sys

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import SessionLocal, init_db
from app.services.ingestion import IngestionService


def main():
    parser = argparse.ArgumentParser(description="AI News Intelligence Agent - Ingestion Runner")
    parser.add_argument("--query", "-q", type=str, default=None, help="Search query filter")
    parser.add_argument("--no-newsapi", action="store_true", help="Disable News API connector")
    parser.add_argument("--no-rss", action="store_true", help="Disable RSS feeds connector")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI processing (fetch and store only)")
    parser.add_argument("--max-articles", "-m", type=int, default=30, help="Maximum articles to collect")

    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        service = IngestionService(db=db, enable_ai=not args.no_ai)
        print(f"[*] Starting ingestion run (query={args.query}, max={args.max_articles})...")

        results = service.run_pipeline(
            include_news_api=not args.no_newsapi,
            include_rss=not args.no_rss,
            max_articles=args.max_articles,
            query=args.query,
        )

        print("\n[+] Ingestion Run Completed Successfully:")
        print(f"    - Articles Fetched:       {results['fetched']}")
        print(f"    - Articles Inserted:      {results['inserted']}")
        print(f"    - Exact Duplicates:       {results['exact_duplicates']}")
        print(f"    - Near Duplicates:        {results['near_duplicates']}")
        print(f"    - AI Analyses Generated:  {results['ai_processed']}")
        print(f"    - Connectors Status:      {results['connectors']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
