"""
Standalone test harness for the news (#1B) and LinkedIn (#1C) crawler sources.

Usage (run via GitHub Actions workflow, not locally):
    python -m scripts.test_crawler                       # all active competitors across all businesses
    python -m scripts.test_crawler "Acme Corp"            # single ad-hoc name (skips DB)
    python -m scripts.test_crawler "Acme Corp" --linkedin-url https://linkedin.com/company/acme
    python -m scripts.test_crawler --business-id <uuid>  # restrict to one business
    python -m scripts.test_crawler --only news           # skip the LinkedIn fetch (faster)
    python -m scripts.test_crawler --only linkedin       # skip the news fetch

Prints results to stdout. Does not write to DB, does not call Claude, does not send email.
"""

import sys
import argparse
import logging
from typing import Optional

from src.crawler import crawler

logger = logging.getLogger(__name__)


def print_news(name: str) -> None:
    print(f"\n  --- NEWS ---")
    result = crawler._crawl_news(name)
    status = result.get("status")
    print(f"  status:        {status}")

    if status != "success":
        print(f"  reason:        {result.get('reason', '(none)')}")
        return

    articles = result.get("articles", [])
    print(f"  lookback:      {result.get('lookback_hours')}h")
    print(f"  article count: {len(articles)}")

    if not articles:
        print("  (no articles in window)")
        return

    for i, art in enumerate(articles, 1):
        print(f"\n  [{i}] {art.get('title', '(no title)')}")
        print(f"      source:    {art.get('source') or '(unknown)'}")
        print(f"      published: {art.get('published') or '(unknown)'}")
        url = art.get("url") or ""
        if url:
            print(f"      url:       {url[:120]}{'...' if len(url) > 120 else ''}")


def print_linkedin(name: str, linkedin_url: Optional[str] = None) -> None:
    print(f"\n  --- LINKEDIN ---")
    if linkedin_url:
        print(f"  override url:  {linkedin_url}")
    result = crawler._crawl_linkedin(name, linkedin_url)
    status = result.get("status")
    print(f"  status:        {status}")
    print(f"  strategy:      {result.get('source_strategy', '(n/a)')}")

    if status != "success":
        print(f"  reason:        {result.get('reason', '(none)')}")
        if result.get("note"):
            print(f"  note:          {result['note']}")
        return

    print(f"  url:           {result.get('url') or '(none)'}")
    print(f"  employees:     {result.get('employee_count') or '(not found)'}")
    print(f"  followers:     {result.get('follower_count') or '(not found)'}")


def fetch_for_name(name: str, only: Optional[str] = None, linkedin_url: Optional[str] = None) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    print(f"{'=' * 70}")
    if only in (None, "news"):
        print_news(name)
    if only in (None, "linkedin"):
        print_linkedin(name, linkedin_url)


def fetch_for_db_competitors(business_id_filter: Optional[str], only: Optional[str]) -> None:
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
            fetch_for_name(
                c.get("name", ""),
                only=only,
                linkedin_url=c.get("linkedin_url"),
            )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Test the news and LinkedIn crawlers in isolation.")
    parser.add_argument("name", nargs="?", help="Single competitor name to test (skips DB)")
    parser.add_argument("--business-id", help="Restrict DB mode to one business")
    parser.add_argument("--linkedin-url", help="(With positional name) override LinkedIn URL — tests direct-fetch path")
    parser.add_argument("--only", choices=["news", "linkedin"], help="Limit to one source")
    args = parser.parse_args()

    if args.name:
        fetch_for_name(args.name, only=args.only, linkedin_url=args.linkedin_url)
    else:
        fetch_for_db_competitors(args.business_id, only=args.only)

    return 0


if __name__ == "__main__":
    sys.exit(main())
