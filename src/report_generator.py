import json
import logging
from typing import List, Dict, Any
from datetime import datetime

from anthropic import Anthropic
from src.config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)
client = Anthropic(api_key=CLAUDE_API_KEY)

class ReportGenerator:
    """Generate HTML email reports from crawl diffs."""

    def generate_report(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Generate full report and executive summary HTML.
        Returns dict with 'full_report' and 'summary' keys.
        """
        full_report_html = self._generate_full_report(business_name, competitors, diffs)
        summary_html = self._generate_summary(business_name, competitors, diffs)

        return {
            "full_report": full_report_html,
            "summary": summary_html,
        }

    def _generate_full_report(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> str:
        """Generate full detailed report HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Competitive Intel - {business_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1e40af; color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header p {{ margin: 5px 0 0 0; opacity: 0.9; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ color: #1e40af; border-bottom: 2px solid #1e40af; padding-bottom: 10px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; font-weight: bold; }}
        tr:hover {{ background: #f9f9f9; }}
        .competitor {{ background: #f5f5f5; padding: 15px; border-left: 4px solid #1e40af; margin-bottom: 15px; border-radius: 4px; }}
        .competitor h3 {{ margin: 0 0 10px 0; }}
        .no-changes {{ color: #666; font-style: italic; }}
        .change {{ color: #059669; font-weight: bold; }}
        .change-item {{ padding: 8px; background: #ecfdf5; border-left: 3px solid #059669; margin: 8px 0; border-radius: 3px; }}
        .timestamp {{ color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Competitive Intelligence Report</h1>
        <p>Business: <strong>{business_name}</strong></p>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>

    <div class="section">
        <h2>Competitor Overview</h2>
        <table>
            <thead>
                <tr>
                    <th>Competitor</th>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Changes</th>
                </tr>
            </thead>
            <tbody>
"""

        for comp in competitors:
            changes_count = 0
            for diff in diffs:
                if diff.get("competitor_id") == comp.get("id"):
                    changes_count = len(diff.get("changes", {}))
            status = "Active" if comp.get("is_active") else "Paused"
            html += f"""                <tr>
                    <td><strong>{comp.get('name', 'Unknown')}</strong></td>
                    <td>{comp.get('url', 'N/A')}</td>
                    <td>{status}</td>
                    <td><span class="change">{changes_count} changes</span></td>
                </tr>
"""

        html += """            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Change Log</h2>
"""

        has_changes = False
        for diff in diffs:
            competitor_id = diff.get("competitor_id")
            competitor = next((c for c in competitors if c.get("id") == competitor_id), None)
            if not competitor:
                continue

            changes = diff.get("changes", {})
            is_first = diff.get("is_first_crawl", False)

            if is_first:
                html += f"""        <div class="competitor">
            <h3>{competitor.get('name', 'Unknown')}</h3>
            <p class="no-changes">First crawl - no previous data to compare</p>
        </div>
"""
            elif not changes or changes.get("message") == "No changes detected":
                html += f"""        <div class="competitor">
            <h3>{competitor.get('name', 'Unknown')}</h3>
            <p class="no-changes">No changes detected since last crawl</p>
        </div>
"""
            else:
                has_changes = True
                html += f"""        <div class="competitor">
            <h3>{competitor.get('name', 'Unknown')}</h3>
"""
                for source_type, source_changes in changes.items():
                    if source_changes.get("status") == "no_changes":
                        continue
                    html += f"""            <div class="change-item">
                <strong>{source_type.upper()}:</strong><br/>
"""
                    if isinstance(source_changes, dict):
                        for key, value in source_changes.items():
                            if key != "status":
                                html += f"                {key}: {json.dumps(value)[:100]}...<br/>\n"
                    html += """            </div>
"""
                html += """        </div>
"""

        if not has_changes:
            html += """        <p class="no-changes">✓ No significant changes detected across all competitors in this reporting period.</p>
"""

        html += """    </div>

    <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
        <p>This report is automatically generated. For questions or to adjust tracking, reply to this email.</p>
    </div>

</body>
</html>
"""
        return html

    def _generate_summary(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> str:
        """Generate 15-minute executive summary HTML."""
        # Get key insights
        bullet_points = self._extract_key_insights(competitors, diffs)

        # Use Claude to generate "So What" and recommendations
        recommendations = self._generate_recommendations(business_name, competitors, diffs)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Executive Summary - {business_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1e40af; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .section {{ margin-bottom: 25px; }}
        .section h2 {{ color: #1e40af; font-size: 16px; margin-bottom: 10px; }}
        ul {{ margin: 0; padding-left: 20px; }}
        li {{ margin-bottom: 8px; }}
        .insight {{ background: #f0f7ff; padding: 12px; border-left: 3px solid #1e40af; margin-bottom: 10px; border-radius: 4px; }}
        .recommendation {{ background: #fef3c7; padding: 12px; border-left: 3px solid #d97706; margin-bottom: 10px; border-radius: 4px; }}
        .recommendation strong {{ color: #92400e; }}
        .timestamp {{ color: #666; font-size: 12px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Executive Summary</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">Quick intelligence brief for {business_name}</p>
    </div>

    <div class="section">
        <h2>Key Changes by Competitor</h2>
"""

        for comp_bullets in bullet_points:
            competitor_name = comp_bullets.get("name")
            bullets = comp_bullets.get("bullets", [])
            html += f"""        <div class="insight">
            <strong>{competitor_name}</strong><br/>
"""
            for bullet in bullets:
                html += f"            • {bullet}<br/>\n"
            html += """        </div>
"""

        html += f"""    </div>

    <div class="section">
        <h2>What This Means</h2>
        <p>{recommendations.get('what_it_means', 'No significant competitive signals detected.')}</p>
    </div>

    <div class="section">
        <h2>Recommended Actions</h2>
        <ol>
"""

        for idx, action in enumerate(recommendations.get("actions", [])[:3], 1):
            html += f"            <li><strong>{action.get('title', f'Action {idx}')}</strong>: {action.get('description', '')}</li>\n"

        html += """        </ol>
    </div>

    <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
        <p>💡 This summary is AI-generated from competitive intelligence. Review the full report for details.</p>
    </div>

</body>
</html>
"""
        return html

    def _extract_key_insights(self, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract 3-5 key bullets per competitor."""
        insights = []

        for comp in competitors:
            bullets = []
            for diff in diffs:
                if diff.get("competitor_id") != comp.get("id"):
                    continue

                changes = diff.get("changes", {})
                is_first = diff.get("is_first_crawl", False)

                if is_first:
                    bullets.append("Baseline established - will track changes from here")
                else:
                    # Extract notable changes
                    if "pricing" in changes:
                        pricing_changes = changes["pricing"]
                        if "pricing_changed" in pricing_changes:
                            bullets.append("Pricing updated")
                        if "tier_count_changed" in pricing_changes:
                            bullets.append("Pricing tier structure changed")

                    if "features" in changes:
                        feature_changes = changes["features"]
                        if "features_added" in feature_changes:
                            added_count = len(feature_changes["features_added"])
                            bullets.append(f"{added_count} new features added")
                        if "features_removed" in feature_changes:
                            removed_count = len(feature_changes["features_removed"])
                            bullets.append(f"{removed_count} features removed")

                    if "jobs" in changes:
                        job_changes = changes["jobs"]
                        if "headcount_signal" in job_changes:
                            change = job_changes["headcount_signal"].get("change", 0)
                            if change > 0:
                                bullets.append(f"Expanding: +{change} open positions")
                            elif change < 0:
                                bullets.append(f"Contracting: {change} fewer positions")

                    if "blog" in changes:
                        blog_changes = changes["blog"]
                        if "new_posts" in blog_changes:
                            bullets.append(f"{len(blog_changes['new_posts'])} new blog posts")

            insights.append({
                "name": comp.get("name", "Unknown"),
                "bullets": bullets[:5] if bullets else ["No changes detected"],
            })

        return insights

    def _generate_recommendations(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use Claude to generate strategic recommendations."""
        # Build context for Claude
        competitive_context = self._build_competitive_context(competitors, diffs)

        prompt = f"""You are a product strategy advisor. Based on the following competitive intelligence for {business_name}, provide:

1. A brief "What This Means" paragraph (2-3 sentences) on the collective competitive signals
2. 2-3 specific, prioritized "Recommended Actions" for product/positioning

Competitive Context:
{competitive_context}

Respond as valid JSON only (no markdown):
{{
  "what_it_means": "Your insight here...",
  "actions": [
    {{"title": "Action 1", "description": "Why and what to do..."}},
    {{"title": "Action 2", "description": "..."}}
  ]
}}
"""

        try:
            message = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text.strip()

            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return {
                "what_it_means": "Monitor competitors for strategic insights.",
                "actions": [
                    {"title": "Continue Monitoring", "description": "Keep tracking competitor signals daily"}
                ]
            }

    def _build_competitive_context(self, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> str:
        """Build a text summary of competitive landscape for Claude."""
        context = ""

        for comp in competitors:
            context += f"\n{comp.get('name', 'Unknown')}:\n"
            for diff in diffs:
                if diff.get("competitor_id") != comp.get("id"):
                    continue

                changes = diff.get("changes", {})
                if changes:
                    context += f"  Changes: {json.dumps(changes, indent=2)[:500]}\n"
                else:
                    context += "  No changes detected\n"

        return context if context else "No significant changes across competitors."

report_generator = ReportGenerator()
