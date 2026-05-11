import logging
import time
import re
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import feedparser
from playwright.async_api import async_playwright

from src.config import CRAWL_TIMEOUT_SECONDS, CRAWL_DELAY_SECONDS, MAX_RETRIES

logger = logging.getLogger(__name__)

# Keywords used to identify navigation links
PAGE_KEYWORDS = {
    "pricing": ["pricing", "plans", "price", "packages", "subscription"],
    "features": ["features", "product", "platform", "solution", "capabilities", "what-we-do"],
    "blog": ["blog", "changelog", "updates", "news", "resources", "insights", "articles"],
    "jobs": ["careers", "jobs", "join-us", "team", "open positions", "openings", "we're hiring"],
}

class Crawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.timeout = CRAWL_TIMEOUT_SECONDS
        self.delay = CRAWL_DELAY_SECONDS
        self.playwright_timeout = 40000  # milliseconds for Playwright operations

    def crawl_competitor(self, competitor_name: str, competitor_url: str) -> Dict[str, Any]:
        """
        Crawl a competitor and extract all available data.
        Strategy: Fetch homepage → discover real URLs from nav → crawl each.
        """
        logger.info(f"Starting crawl for {competitor_name} ({competitor_url})")

        sources = {}

        # 1. Crawl homepage and discover navigation links
        homepage_data, discovered_urls = self._crawl_homepage_with_discovery(competitor_url)
        sources["homepage"] = homepage_data
        time.sleep(self.delay)

        if discovered_urls:
            logger.info(f"Discovered URLs for {competitor_name}: {discovered_urls}")

        # 2-5. Crawl each section using discovered URLs (or fallbacks)
        sources["pricing"] = self._crawl_pricing(competitor_url, discovered_urls.get("pricing"))
        time.sleep(self.delay)

        sources["features"] = self._crawl_features(competitor_url, discovered_urls.get("features"))
        time.sleep(self.delay)

        sources["blog"] = self._crawl_blog(competitor_url, discovered_urls.get("blog"))
        time.sleep(self.delay)

        sources["jobs"] = self._crawl_jobs(competitor_url, discovered_urls.get("jobs"))
        time.sleep(self.delay)

        sources["news"] = self._crawl_news(competitor_name)

        logger.info(f"Completed crawl for {competitor_name}")
        return sources

    def _is_javascript_heavy(self, html: str) -> bool:
        """
        Detect if HTML appears to be JavaScript-heavy (SPA).
        Heuristics:
        - Body text suspiciously short (< 200 chars after removing scripts)
        - Many <script> tags relative to other content
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract body text
        body_text = " ".join(soup.stripped_strings)
        text_length = len(body_text)

        # Count script tags (from original HTML before decomposing)
        script_count = html.count("<script")

        # If body text is too short, likely needs JS rendering
        if text_length < 200:
            logger.debug(f"Detected JS-heavy page: body text only {text_length} chars")
            return True

        # If many scripts relative to content, likely JS-heavy
        if script_count > 5 and text_length < 1000:
            logger.debug(f"Detected JS-heavy page: {script_count} scripts with only {text_length} chars text")
            return True

        return False

    async def _render_with_playwright(self, url: str) -> Optional[str]:
        """
        Render a page using Playwright (Chromium headless).
        Waits for network idle before extracting content.
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=self.playwright_timeout)

                # Get rendered HTML
                html = await page.content()

                await context.close()
                await browser.close()

                return html
        except Exception as e:
            logger.warning(f"Playwright rendering failed for {url}: {e}")
            return None

    def _crawl_with_playwright(self, url: str) -> Optional[str]:
        """Wrapper to run async Playwright in sync context."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._render_with_playwright(url))
            loop.close()
            return result
        except Exception as e:
            logger.warning(f"Failed to run Playwright for {url}: {e}")
            return None

    def _crawl_with_retry(self, url: str, method: str = "GET") -> Optional[str]:
        """
        Fetch a URL with retry logic. Don't retry 404s.
        Falls back to Playwright if static fetch returns JS-heavy content.
        """
        html = None

        # Try static fetch with retries
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=self.timeout, allow_redirects=True)
                if response.status_code == 200:
                    html = response.text
                    break
                elif response.status_code in (403, 401):
                    logger.warning(f"Access forbidden for {url} (status: {response.status_code})")
                    return None
                elif response.status_code == 404:
                    return None  # Don't retry, URL doesn't exist
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
            except requests.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{MAX_RETRIES} for {url}")
            except Exception as e:
                logger.warning(f"Error on attempt {attempt + 1}/{MAX_RETRIES} for {url}: {e}")

            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                time.sleep(wait)

        # If we got HTML, check if it's JS-heavy
        if html:
            if self._is_javascript_heavy(html):
                logger.info(f"Detected JS-heavy content for {url}, falling back to Playwright")
                playwright_html = self._crawl_with_playwright(url)
                if playwright_html:
                    html = playwright_html
        else:
            # Static fetch completely failed, try Playwright as last resort
            logger.info(f"Static fetch failed for {url}, trying Playwright")
            html = self._crawl_with_playwright(url)

        return html

    def _discover_links(self, html: str, base_url: str) -> Dict[str, str]:
        """Parse HTML to find navigation links matching keyword categories."""
        soup = BeautifulSoup(html, "html.parser")
        discovered = {}

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            text = link.get_text(strip=True).lower()

            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)

            # Same domain only
            base_domain = urlparse(base_url).netloc.replace("www.", "")
            link_domain = urlparse(full_url).netloc
            if base_domain not in link_domain:
                continue

            href_lower = href.lower()
            for category, keywords in PAGE_KEYWORDS.items():
                if category in discovered:
                    continue
                if any(kw in text for kw in keywords) or any(kw in href_lower for kw in keywords):
                    discovered[category] = full_url
                    break

        return discovered

    def _crawl_homepage_with_discovery(self, base_url: str) -> tuple:
        """Fetch homepage, extract messaging, discover navigation URLs."""
        html = self._crawl_with_retry(base_url)
        if not html:
            return ({"status": "failed", "reason": "Could not fetch homepage"}, {})

        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()

        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""

        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        og_description = og_desc.get("content", "") if og_desc else ""

        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else ""

        h2 = soup.find("h2")
        h2_text = h2.get_text(strip=True) if h2 else ""

        body_text = " ".join(soup.stripped_strings)[:800]

        homepage_data = {
            "status": "success",
            "title": title_text,
            "meta_description": description or og_description,
            "main_heading": h1_text,
            "sub_heading": h2_text,
            "body_preview": body_text,
            "crawled_at": time.time(),
        }

        discovered = self._discover_links(html, base_url)
        return homepage_data, discovered

    def _crawl_pricing(self, base_url: str, discovered_url: Optional[str] = None) -> Dict[str, Any]:
        """Extract pricing information."""
        candidate_urls = []
        if discovered_url:
            candidate_urls.append(discovered_url)
        for path in ["/pricing", "/plans", "/pricing/", "/plans/"]:
            url = urljoin(base_url, path)
            if url not in candidate_urls:
                candidate_urls.append(url)

        for pricing_url in candidate_urls:
            html = self._crawl_with_retry(pricing_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()

                tiers = []
                for tier in soup.find_all(["div", "section", "article"], class_=re.compile(r"(tier|plan|pricing|package)", re.I))[:10]:
                    tier_name = tier.find(["h2", "h3", "h4"])
                    tier_price = tier.find(["span", "div", "p"], class_=re.compile(r"price|amount|cost", re.I))
                    if tier_name or tier_price:
                        tiers.append({
                            "name": tier_name.get_text(strip=True) if tier_name else "Unknown",
                            "price": tier_price.get_text(strip=True)[:50] if tier_price else "Contact",
                        })

                content_text = " ".join(soup.stripped_strings)[:1500]

                return {
                    "status": "success",
                    "url": pricing_url,
                    "tiers": tiers,
                    "content_preview": content_text,
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find pricing page"}

    def _crawl_features(self, base_url: str, discovered_url: Optional[str] = None) -> Dict[str, Any]:
        """Extract features/product information."""
        candidate_urls = []
        if discovered_url:
            candidate_urls.append(discovered_url)
        for path in ["/features", "/product", "/platform", "/solutions", "/features/", "/product/"]:
            url = urljoin(base_url, path)
            if url not in candidate_urls:
                candidate_urls.append(url)

        for features_url in candidate_urls:
            html = self._crawl_with_retry(features_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()

                features = []
                for li in soup.find_all("li")[:30]:
                    text = li.get_text(strip=True)
                    if text and 5 < len(text) < 200:
                        features.append(text)

                headings = []
                for h in soup.find_all(["h2", "h3"])[:15]:
                    text = h.get_text(strip=True)
                    if text and len(text) < 100:
                        headings.append(text)

                content_text = " ".join(soup.stripped_strings)[:1500]

                return {
                    "status": "success",
                    "url": features_url,
                    "features": features[:20],
                    "feature_categories": headings,
                    "content_preview": content_text,
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find features page"}

    def _crawl_blog(self, base_url: str, discovered_url: Optional[str] = None) -> Dict[str, Any]:
        """Extract blog/changelog posts."""
        # RSS first
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
                    posts = [{
                        "title": e.get("title", "Untitled"),
                        "published": e.get("published", ""),
                        "link": e.get("link", ""),
                    } for e in feed.entries[:5]]
                    return {
                        "status": "success",
                        "type": "rss",
                        "url": rss_url,
                        "posts": posts,
                        "crawled_at": time.time(),
                    }
            except Exception:
                pass

        # Fallback to scraping blog page
        candidate_urls = []
        if discovered_url:
            candidate_urls.append(discovered_url)
        for path in ["/blog", "/changelog", "/updates", "/news", "/resources"]:
            url = urljoin(base_url, path)
            if url not in candidate_urls:
                candidate_urls.append(url)

        for blog_url in candidate_urls:
            html = self._crawl_with_retry(blog_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()

                articles = []
                for link in soup.find_all("a", href=True)[:30]:
                    text = link.get_text(strip=True)
                    href = link["href"]
                    if text and 10 < len(text) < 200:
                        articles.append({
                            "title": text,
                            "link": urljoin(blog_url, href),
                        })

                return {
                    "status": "success",
                    "type": "blog_page",
                    "url": blog_url,
                    "articles": articles[:10],
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find blog/changelog"}

    def _crawl_jobs(self, base_url: str, discovered_url: Optional[str] = None) -> Dict[str, Any]:
        """Extract job listings."""
        candidate_urls = []
        if discovered_url:
            candidate_urls.append(discovered_url)
        for path in ["/careers", "/jobs", "/careers/", "/jobs/", "/about/careers"]:
            url = urljoin(base_url, path)
            if url not in candidate_urls:
                candidate_urls.append(url)

        for jobs_url in candidate_urls:
            html = self._crawl_with_retry(jobs_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()

                jobs = []
                for job_item in soup.find_all(["div", "li", "article"], class_=re.compile(r"(job|position|opening|role|career)", re.I))[:30]:
                    job_title = job_item.find(["h3", "h2", "h4", "a"])
                    if job_title:
                        text = job_title.get_text(strip=True)
                        if text and 5 < len(text) < 150:
                            jobs.append(text)

                if not jobs:
                    for link in soup.find_all("a", href=True)[:50]:
                        text = link.get_text(strip=True)
                        href = link["href"].lower()
                        if (5 < len(text) < 150) and any(kw in href for kw in ["job", "career", "position"]):
                            jobs.append(text)

                return {
                    "status": "success",
                    "url": jobs_url,
                    "jobs_count": len(jobs),
                    "sample_jobs": jobs[:10],
                    "crawled_at": time.time(),
                }

        return {"status": "not_found", "reason": "Could not find jobs page"}

    def _crawl_news(self, company_name: str) -> Dict[str, Any]:
        """News crawling placeholder."""
        return {
            "status": "not_implemented",
            "reason": "News crawling requires API integration",
            "note": f"To enable, integrate Google News API or similar for: {company_name}",
        }

crawler = Crawler()
