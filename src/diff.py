import logging
from typing import Optional, Dict, Any, List
from difflib import unified_diff

logger = logging.getLogger(__name__)

class DiffEngine:
    """Compare crawl results and generate structured diffs."""

    def generate_diff(self, previous_crawl: Optional[Dict[str, Any]], current_crawl: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a diff between two crawl results.
        If previous_crawl is None, this is the first crawl.
        Returns a dict of changes by source type.
        """
        if previous_crawl is None:
            return {
                "is_first_crawl": True,
                "message": "First crawl - no previous data to compare",
                "changes": {}
            }

        changes = {}

        for source_type in current_crawl:
            if source_type not in previous_crawl:
                continue

            current_source = current_crawl[source_type]
            previous_source = previous_crawl[source_type]

            # Skip sources that failed or weren't implemented
            if isinstance(current_source, dict):
                if current_source.get("status") in ["failed", "not_found", "not_implemented"]:
                    continue
                if previous_source.get("status") in ["failed", "not_found", "not_implemented"]:
                    changes[source_type] = {
                        "type": "availability_change",
                        "message": f"Source now available (was: {previous_source.get('status', 'unknown')})"
                    }
                    continue

            # Compare by source type
            if source_type == "homepage":
                changes[source_type] = self._diff_homepage(previous_source, current_source)
            elif source_type == "pricing":
                changes[source_type] = self._diff_pricing(previous_source, current_source)
            elif source_type == "features":
                changes[source_type] = self._diff_features(previous_source, current_source)
            elif source_type == "blog":
                changes[source_type] = self._diff_blog(previous_source, current_source)
            elif source_type == "jobs":
                changes[source_type] = self._diff_jobs(previous_source, current_source)
            elif source_type == "news":
                changes[source_type] = self._diff_news(previous_source, current_source)
            elif source_type == "linkedin":
                changes[source_type] = self._diff_linkedin(previous_source, current_source)

        return {
            "is_first_crawl": False,
            "changes": changes if changes else {"message": "No changes detected"},
        }

    def _diff_homepage(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """Diff homepage messaging changes."""
        changes = {}

        # Check title change
        if prev.get("title") != curr.get("title"):
            changes["title_changed"] = {
                "previous": prev.get("title", ""),
                "current": curr.get("current", ""),
            }

        # Check meta description change
        if prev.get("meta_description") != curr.get("meta_description"):
            changes["description_changed"] = {
                "previous": prev.get("meta_description", ""),
                "current": curr.get("meta_description", ""),
            }

        # Check main heading change
        if prev.get("main_heading") != curr.get("main_heading"):
            changes["heading_changed"] = {
                "previous": prev.get("main_heading", ""),
                "current": curr.get("main_heading", ""),
            }

        return changes if changes else {"status": "no_changes"}

    def _diff_pricing(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """Diff pricing changes."""
        changes = {}

        # Extract tiers safely
        prev_tiers = prev.get("tiers", [])
        curr_tiers = curr.get("tiers", [])

        # If tiers is a string (parse error), skip detailed diff
        if isinstance(prev_tiers, str) or isinstance(curr_tiers, str):
            return {"status": "could_not_parse_tiers"}

        # Compare tier counts
        if len(prev_tiers) != len(curr_tiers):
            changes["tier_count_changed"] = {
                "previous": len(prev_tiers),
                "current": len(curr_tiers),
            }

        # Compare tier names and prices
        prev_tier_names = [t.get("name", "") for t in prev_tiers]
        curr_tier_names = [t.get("name", "") for t in curr_tiers]

        if prev_tier_names != curr_tier_names:
            changes["tier_structure_changed"] = {
                "previous_names": prev_tier_names,
                "current_names": curr_tier_names,
            }

        # Price changes
        prev_prices = [t.get("price", "") for t in prev_tiers]
        curr_prices = [t.get("price", "") for t in curr_tiers]

        if prev_prices != curr_prices:
            changes["pricing_changed"] = {
                "previous": prev_prices,
                "current": curr_prices,
            }

        return changes if changes else {"status": "no_changes"}

    def _diff_features(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """Diff features changes."""
        changes = {}

        prev_features = prev.get("features", [])
        curr_features = curr.get("features", [])

        # If features is a string, skip detailed diff
        if isinstance(prev_features, str) or isinstance(curr_features, str):
            return {"status": "could_not_parse_features"}

        # Compare feature counts
        if len(prev_features) != len(curr_features):
            changes["feature_count_changed"] = {
                "previous": len(prev_features),
                "current": len(curr_features),
            }

        # Compare feature lists (simple set diff)
        prev_set = set(prev_features)
        curr_set = set(curr_features)

        added = list(curr_set - prev_set)
        removed = list(prev_set - curr_set)

        if added:
            changes["features_added"] = added[:10]  # First 10
        if removed:
            changes["features_removed"] = removed[:10]

        return changes if changes else {"status": "no_changes"}

    def _diff_blog(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """Diff blog/changelog post changes."""
        changes = {}

        prev_posts = prev.get("posts", []) if isinstance(prev.get("posts"), list) else []
        curr_posts = curr.get("posts", []) if isinstance(curr.get("posts"), list) else []

        # Compare post counts
        if len(prev_posts) != len(curr_posts):
            changes["post_count_changed"] = {
                "previous": len(prev_posts),
                "current": len(curr_posts),
            }

        # Check for new posts (simplified - just title comparison)
        prev_titles = {p.get("title") for p in prev_posts}
        curr_titles = {p.get("title") for p in curr_posts}

        new_posts = list(curr_titles - prev_titles)
        if new_posts:
            changes["new_posts"] = new_posts[:5]

        return changes if changes else {"status": "no_changes"}

    def _diff_jobs(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """Diff job listing changes (headcount, new roles)."""
        changes = {}

        prev_count = prev.get("jobs_count", 0)
        curr_count = curr.get("jobs_count", 0)

        if prev_count != curr_count:
            changes["headcount_signal"] = {
                "previous_open_jobs": prev_count,
                "current_open_jobs": curr_count,
                "change": curr_count - prev_count,
            }

        # Check for new job titles
        prev_jobs = set(prev.get("sample_jobs", []))
        curr_jobs = set(curr.get("sample_jobs", []))

        new_jobs = list(curr_jobs - prev_jobs)
        if new_jobs:
            changes["new_jobs"] = new_jobs[:5]

        return changes if changes else {"status": "no_changes"}

    def _diff_linkedin(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Diff LinkedIn signals — employee count and follower count.
        Counts are stored as strings (e.g., "11-50", "1,234", "10K+") because
        LinkedIn formats vary. We compare them as strings; any change is reported.
        """
        changes = {}

        prev_emp = prev.get("employee_count")
        curr_emp = curr.get("employee_count")
        if prev_emp != curr_emp and (prev_emp or curr_emp):
            changes["employee_count_changed"] = {
                "previous": prev_emp,
                "current": curr_emp,
            }

        prev_fol = prev.get("follower_count")
        curr_fol = curr.get("follower_count")
        if prev_fol != curr_fol and (prev_fol or curr_fol):
            changes["follower_count_changed"] = {
                "previous": prev_fol,
                "current": curr_fol,
            }

        return changes if changes else {"status": "no_changes"}

    def _diff_news(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Diff news mentions: identify articles that appear in the current crawl
        but were not in the previous one. Identity is article URL (with title
        as a fallback if URL is missing).
        """
        prev_articles = prev.get("articles", []) if isinstance(prev.get("articles"), list) else []
        curr_articles = curr.get("articles", []) if isinstance(curr.get("articles"), list) else []

        def article_key(a: Dict[str, Any]) -> str:
            return a.get("url") or a.get("title", "")

        prev_keys = {article_key(a) for a in prev_articles if article_key(a)}
        new_articles = [a for a in curr_articles if article_key(a) and article_key(a) not in prev_keys]

        if not new_articles:
            return {"status": "no_changes"}

        return {
            "new_articles": [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", ""),
                    "url": a.get("url", ""),
                    "published": a.get("published", ""),
                    "snippet": a.get("snippet", ""),
                }
                for a in new_articles[:10]
            ],
            "new_article_count": len(new_articles),
        }

diff_engine = DiffEngine()
