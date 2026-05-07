import logging
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
import re

import requests
from bs4 import BeautifulSoup
import feedparser

from src.config import CRAWL_TIMEOUT_SECONDS, CRAWL_DELAY_SECONDS, MAX_RETRIES

logger = logging.getLogger(__name__)

class Crawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.timeout = CRAWL_TIMEOUT_SECONDS
        self.delay = CRAWL_DELAY_SECONDS

    def crawl_competitor(self, competitor_name: str, competitor_url: str) -> Dict[str, Any]:
        """
        Crawl a competitor and extract all available data.
        Returns a dict with sources as keys and extracted data as values.
        """
        logger.info(f"Starting crawl for {competitor_name} ({competitor_url})")

        sources = {}

        # Crawl homepage for messaging
        sources["homepage"] = self._crawl_homepage(competitor_url)
        time.sleep(self.delay)

        # Crawl pricing page
        sources["pricing"] = self._crawl_pricing(competitor_url)
        time.sleep(self.delay)

        # Crawl features page
        sources["features"] = self._crawl_features(competitor_url)
        time.sleep(self.delay)

        # Crawl blog/changelog for recent announcements
        sources["blog"] = self._crawl_blog(competitor_url)
        time.sleep(self.delay)

        # Crawl careers/jobs page
        sources["jobs"] = self._crawl_jobs(competitor_url)
        time.sleep(self.delay)

        # Try to fetch news mentions (via simple search)
        sources["news"] = self._crawl_news(competitor_name)
        time.sleep(self.delay)

        logger.info(f"Completed crawl for {competitor_name}")
        return sources

    def _crawl_with_retry(self, url: str, method: str = "GET") -> Optional[str]:
        """Fetch a URL with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403 or response.status_code == 401:
                    logger.warning(f"Access forbidden for {url} (status: {response.status_code})")
                    return None
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
            except requests.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{MAX_RETRIES} for {url}")
            except Exception as e:
                logger.warning(f"Error on attempt {attempt + 1}/{MAX_RETRIES} for {url}: {e}")

            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt  # Exponential backoff
                time.sleep(wait)

        logger.error(f"Failed to crawl {url} after {MAX_RETRIES} retries")
        return None

    def _crawl_homepage(self, base_url: str) -> Dict[str, Any]:
        """Extract homepage messaging, taglines, CTAs."""
        html = self._crawl_with_retry(base_url)
        if not html:
            return {"status": "failed", "reason": "Could not fetch homepage"}

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract title and meta description
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""

        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""

        # Extract main heading (h1)
        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else ""

        # Extract first 500 chars of body text
        body_text = " ".join(soup.stripped_strings)[:500]

        return {
            "status": "success",
            "title": title_text,
            "meta_description": description,
            "main_heading": h1_text,
            "body_preview": body_text,
            "crawled_at": time.time(),
        }

    def _crawl_pricing(self, base_url: str) -> Dict[str, Any]:
        """Extract pricing page information."""
        # Try common pricing page paths
        pricing_urls = [
            urljoin(base_url, "/pricing"),
            urljoin(base_url, "/plans"),
            urljoin(base_url, "/pricing/"),
            urljoin(base_url, "/plans/"),
        ]

        for pricing_url in pricing_urls:
            html = self._crawl_with_retry(pricing_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")

                # Extract pricing tiers (look for common patterns)
                tiers = []
                for tier in soup.find_all(["div", "section"], class_=re.compile(r"(tier|plan|pricing)", re.I)):
                    tier_name = tier.find(["h2", "h3"])
                    tier_price = tier.find(["span", "div"], class_=re.compile(r"price", re.I))
                    if tier_name or tier_price:
                        tiers.append({
                            "name": tier_name.get_text(strip=True) if tier_name else "Unknown",
                            "price": tier_price.get_text(strip=True) if tier_price else "Contact",
                        })

                # Extract first 1000 chars of pricing content
                content_text = " ".join(soup.stripped_strings)[:1000]

                return {
                    "status": "success",
                    "url": pricing_url,
                    "tiers": tiers if tiers else "Could not parse tiers",
                    "content_preview": content_text,
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find pricing page"}

    def _crawl_features(self, base_url: str) -> Dict[str, Any]:
        """Extract features/product page information."""
        feature_urls = [
            urljoin(base_url, "/features"),
            urljoin(base_url, "/product"),
            urljoin(base_url, "/solutions"),
            urljoin(base_url, "/features/"),
            urljoin(base_url, "/product/"),
        ]

        for features_url in feature_urls:
            html = self._crawl_with_retry(features_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")

                # Extract feature lists
                features = []
                for li in soup.find_all("li")[:20]:  # First 20 list items
                    features.append(li.get_text(strip=True))

                # Extract headings as feature categories
                headings = []
                for h in soup.find_all(["h2", "h3"])[:10]:
                    headings.append(h.get_text(strip=True))

                content_text = " ".join(soup.stripped_strings)[:1000]

                return {
                    "status": "success",
                    "url": features_url,
                    "features": features if features else "Could not parse features",
                    "feature_categories": headings if headings else [],
                    "content_preview": content_text,
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find features page"}

    def _crawl_blog(self, base_url: str) -> Dict[str, Any]:
        """Extract blog/changelog recent posts (via RSS or page scrape)."""
        # Try RSS feed first
        rss_urls = [
            urljoin(base_url, "/feed"),
            urljoin(base_url, "/feed.xml"),
            urljoin(base_url, "/rss"),
            urljoin(base_url, "/blog/feed"),
        ]

        for rss_url in rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                if feed.entries:
                    posts = []
                    for entry in feed.entries[:5]:  # First 5 posts
                        posts.append({
                            "title": entry.get("title", "Untitled"),
                            "published": entry.get("published", ""),
                            "link": entry.get("link", ""),
                        })
                    return {
                        "status": "success",
                        "type": "rss",
                        "url": rss_url,
                        "posts": posts,
                        "crawled_at": time.time(),
                    }
            except Exception as e:
                logger.debug(f"RSS parse failed for {rss_url}: {e}")

        # Try blog page scrape
        blog_urls = [
            urljoin(base_url, "/blog"),
            urljoin(base_url, "/changelog"),
            urljoin(base_url, "/updates"),
            urljoin(base_url, "/blog/"),
        ]

        for blog_url in blog_urls:
            html = self._crawl_with_retry(blog_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")

                # Extract article links
                articles = []
                for link in soup.find_all("a", href=True)[:10]:
                    text = link.get_text(strip=True)
                    if text and len(text) > 5:
                        articles.append({
                            "title": text,
                            "link": urljoin(blog_url, link["href"]),
                        })

                return {
                    "status": "success",
                    "type": "blog_page",
                    "url": blog_url,
                    "articles": articles if articles else "Could not parse articles",
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find blog/changelog"}

    def _crawl_jobs(self, base_url: str) -> Dict[str, Any]:
        """Extract job listings from careers page."""
        job_urls = [
            urljoin(base_url, "/careers"),
            urljoin(base_url, "/jobs"),
            urljoin(base_url, "/careers/"),
            urljoin(base_url, "/jobs/"),
        ]

        for jobs_url in job_urls:
            html = self._crawl_with_retry(jobs_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")

                # Extract job listings
                jobs = []
                for job_item in soup.find_all(["div", "li"], class_=re.compile(r"(job|position)", re.I))[:15]:
                    job_title = job_item.find(["h3", "h2", "a"])
                    if job_title:
                        jobs.append(job_title.get_text(strip=True))

                return {
                    "status": "success",
                    "url": jobs_url,
                    "jobs_count": len(jobs),
                    "sample_jobs": jobs[:10] if jobs else "Could not parse jobs",
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find jobs page"}

    def _crawl_news(self, company_name: str) -> Dict[str, Any]:
        """Search for recent news mentions (simplified; would use a news API in production)."""
        # Placeholder: In production, use Google News API or similar
        return {
            "status": "not_implemented",
            "reason": "News crawling requires API (Google News, NewsAPI, etc.)",
            "note": f"To enable, add API for company: {company_name}",
        }

crawler = Crawler()
