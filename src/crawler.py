import logging
import time
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse, quote_plus

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

    def crawl_competitor(
        self,
        competitor_name: str,
        competitor_url: str,
        linkedin_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crawl a competitor and extract all available data.
        Strategy: Fetch homepage → discover real URLs from nav → crawl each.
        If linkedin_url is provided, the crawler uses it directly for LinkedIn data;
        otherwise it falls back to Google search discovery.
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
        time.sleep(self.delay)

        sources["linkedin"] = self._crawl_linkedin(competitor_name, linkedin_url)

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

    def _crawl_with_retry(
        self,
        url: str,
        method: str = "GET",
        use_playwright_fallback: bool = True,
    ) -> Optional[str]:
        """
        Fetch a URL with retry logic. Don't retry 404s.
        Falls back to Playwright if static fetch returns JS-heavy content,
        unless use_playwright_fallback=False (used for sites where Playwright
        provides no benefit, e.g. Google SERPs and LinkedIn auth-wall pages).
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

        if not use_playwright_fallback:
            return html

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

    def _crawl_news(self, company_name: str, lookback_hours: int = 48, max_articles: int = 10) -> Dict[str, Any]:
        """
        Fetch recent news mentions via Google News RSS (no API key required).
        Returns articles from the last `lookback_hours` window (default 48h to allow
        some slack around the daily crawl cadence).
        """
        if not company_name:
            return {"status": "not_found", "reason": "No company name provided"}

        query = quote_plus(f'"{company_name}"')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            logger.warning(f"News RSS fetch failed for {company_name}: {e}")
            return {"status": "failed", "reason": str(e)}

        if not feed.entries:
            return {
                "status": "success",
                "url": rss_url,
                "articles": [],
                "crawled_at": time.time(),
            }

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        articles = []

        for entry in feed.entries:
            published_dt = self._parse_feed_date(entry)

            # Skip articles older than the cutoff (when we can parse the date)
            if published_dt and published_dt < cutoff:
                continue

            # Google News RSS embeds source name in <source> element or in title suffix
            source_name = ""
            if hasattr(entry, "source") and entry.source:
                source_name = entry.source.get("title", "") if isinstance(entry.source, dict) else str(entry.source)

            title = entry.get("title", "Untitled")
            # Google News titles often end with " - {Source}" — split it out as a fallback
            if not source_name and " - " in title:
                title, source_name = title.rsplit(" - ", 1)

            articles.append({
                "title": title.strip(),
                "source": source_name.strip() if source_name else "",
                "published": entry.get("published", ""),
                "url": entry.get("link", ""),
                "snippet": self._strip_html(entry.get("summary", ""))[:300],
            })

            if len(articles) >= max_articles:
                break

        return {
            "status": "success",
            "url": rss_url,
            "articles": articles,
            "lookback_hours": lookback_hours,
            "crawled_at": time.time(),
        }

    def _parse_feed_date(self, entry) -> Optional[datetime]:
        """Best-effort parse of a feed entry's published date as a UTC datetime."""
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                return None
        return None

    def _strip_html(self, raw: str) -> str:
        """Strip HTML tags from a snippet (Google News summaries often contain anchor tags)."""
        if not raw:
            return ""
        try:
            return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
        except Exception:
            return raw

    # ----- LinkedIn (ROADMAP #1C) -----
    # LinkedIn aggressively blocks scrapers. Strategy, in order of preference:
    #   1. If user supplied a linkedin_url, fetch that page directly (often returns
    #      meta tags / og:description with employee count before the auth wall).
    #   2. Otherwise, scrape Google search results for `site:linkedin.com/company "{name}"`
    #      — extract the LinkedIn URL and any employee count in the snippet.
    #   3. If both fail, mark status:"blocked" with a note suggesting manual linkedin_url entry.

    # Match phrases like "1,234 employees", "11-50 employees", "10K+ employees on LinkedIn"
    LINKEDIN_EMPLOYEE_RE = re.compile(
        r"([\d,]+(?:\s*[-–]\s*[\d,]+)?(?:\.\d+)?[KkMm]?\+?)\s*(?:employees?|people who work here)",
        re.IGNORECASE,
    )
    LINKEDIN_FOLLOWER_RE = re.compile(
        r"([\d,]+(?:\.\d+)?[KkMm]?\+?)\s*followers?",
        re.IGNORECASE,
    )
    LINKEDIN_COMPANY_URL_RE = re.compile(
        r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[a-zA-Z0-9._%+\-/]+",
        re.IGNORECASE,
    )

    def _crawl_linkedin(self, company_name: str, linkedin_url: Optional[str] = None) -> Dict[str, Any]:
        """Extract LinkedIn company signals (employee count, followers, URL)."""
        if not company_name:
            return {"status": "not_found", "reason": "No company name provided"}

        # Path 1: explicit URL — try direct fetch first
        if linkedin_url:
            direct = self._linkedin_via_direct_fetch(linkedin_url)
            if direct and direct.get("status") == "success":
                direct["source_strategy"] = "direct_fetch"
                return direct
            # Fall through to Google if direct fetch yielded nothing usable

        # Path 2: Google search discovery
        via_google = self._linkedin_via_google(company_name)
        if via_google and via_google.get("status") == "success":
            via_google["source_strategy"] = "google_search"
            return via_google

        # Path 3: blocked
        return {
            "status": "blocked",
            "reason": "Could not discover LinkedIn data via direct fetch or Google search",
            "note": (
                "LinkedIn blocks scrapers. To make this competitor's LinkedIn data reliable, "
                "set the `linkedin_url` column on the competitors row in Supabase."
            ),
            "crawled_at": time.time(),
        }

    def _linkedin_via_direct_fetch(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """Try fetching the LinkedIn company page directly. Often returns auth-wall HTML,
        but meta tags / og:description usually contain employee count regardless.
        Playwright fallback is disabled — it just renders the same auth wall."""
        html = self._crawl_with_retry(linkedin_url, use_playwright_fallback=False)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Look in og:description, meta description, and visible text
        candidate_texts = []
        for meta_name in [("property", "og:description"), ("name", "description")]:
            tag = soup.find("meta", attrs={meta_name[0]: meta_name[1]})
            if tag and tag.get("content"):
                candidate_texts.append(tag["content"])

        candidate_texts.append(" ".join(soup.stripped_strings)[:2000])

        employees, followers = self._extract_linkedin_counts(" \n ".join(candidate_texts))
        if not employees and not followers:
            return None

        return {
            "status": "success",
            "url": linkedin_url,
            "employee_count": employees,
            "follower_count": followers,
            "crawled_at": time.time(),
        }

    def _linkedin_via_google(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Scrape Google search results for `site:linkedin.com/company "{name}"`.
        Playwright fallback is disabled — running headless Chromium against Google
        with no cookies/profile triggers more anti-bot heuristics than static fetch."""
        query = quote_plus(f'site:linkedin.com/company "{company_name}"')
        search_url = f"https://www.google.com/search?q={query}&hl=en"

        html = self._crawl_with_retry(search_url, use_playwright_fallback=False)
        if not html:
            return None

        # Look for any LinkedIn company URL in the page
        url_match = self.LINKEDIN_COMPANY_URL_RE.search(html)
        discovered_url = url_match.group(0) if url_match else None

        # Search the full visible text for employee/follower counts
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        page_text = " ".join(soup.stripped_strings)

        employees, followers = self._extract_linkedin_counts(page_text)

        if not discovered_url and not employees and not followers:
            return None

        return {
            "status": "success",
            "url": discovered_url,
            "employee_count": employees,
            "follower_count": followers,
            "crawled_at": time.time(),
        }

    def _extract_linkedin_counts(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Pull the first employee count and follower count from a blob of text."""
        if not text:
            return None, None
        emp_match = self.LINKEDIN_EMPLOYEE_RE.search(text)
        fol_match = self.LINKEDIN_FOLLOWER_RE.search(text)
        employees = emp_match.group(1).strip() if emp_match else None
        followers = fol_match.group(1).strip() if fol_match else None
        return employees, followers

crawler = Crawler()
