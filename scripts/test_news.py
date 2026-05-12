"""
Standalone test harness for ROADMAP #1B (Google News RSS integration).

Usage (run via GitHub Actions workflow, not locally):
    python -m scripts.test_news                # fetches news for all active competitors across all businesses
    python -m scripts.test_news "Slack"        # fetches news for a single arbitrary name (no DB)
    python -m scripts.test_news --business-id <uuid>  # only competitors of one business

Prints results to stdout. Does not write to DB, does not call Claude, does not send email.
"""

import sys
import argparse
import logging

from src.crawler import crawler

logger = logging.getLogger(__name__)


def fetch_for_name(name: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    print(f"{'=' * 70}")

    result = crawler._crawl_news(name)
    status = result.get("status")
    print(f"  status:        {status}")

    if status != "success":
        print(f"  reason:        {result.get('reason', '(none)')}")
        return

    articles = result.get("articles", [])
    print(f"  lookback:      {result.get('lookback_hours')}h")
    print(f"  article count: {len(articles)}")
    print(f"  rss url:       {result.get('url')}")

    if not articles:
        print("  (no articles in window — either no recent mentions or Google has nothing indexed)")
        return

    for i, art in enumerate(articles, 1):
        print(f"\n  [{i}] {art.get('title', '(no title)')}")
        print(f"      source:    {art.get('source') or '(unknown)'}")
        print(f"      published: {art.get('published') or '(unknown)'}")
        print(f"      url:       {art.get('url') or '(none)'}")
        snippet = art.get("snippet") or ""
        if snippet:
            print(f"      snippet:   {snippet[:200]}")


def fetch_for_db_competitors(business_id_filter: str | None) -> None:
    # Import lazily so single-name mode doesn't require Supabase env vars to be set
    from src.db import Database

    db = Database()
    businesses = db.list_businesses()
    if business_id_filter:
        businesses = [b for b in businesses if b.get("id") == business_id_filter]

    if not businesses:
        print("No businesses found (after filter).")
        return

    for b in businesses:
        print(f"\n### Business: {b.get('name')} ({b.get('id')})")
        comps = db.get_competitors(b["id"])
        if not comps:
            print("  (no active competitors)")
            continue
        for c in comps:
            fetch_for_name(c.get("name", ""))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Test the news crawler in isolation.")
    parser.add_argument("name", nargs="?", help="Single competitor name to test (skips DB)")
    parser.add_argument("--business-id", help="Restrict to one business's competitors")
    args = parser.parse_args()

    if args.name:
        fetch_for_name(args.name)
    else:
        fetch_for_db_competitors(args.business_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
