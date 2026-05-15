import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from anthropic import Anthropic
from src.config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)
client = Anthropic(api_key=CLAUDE_API_KEY)

class ReportGenerator:
    """Generate HTML email reports from crawl data and diffs."""

    def generate_report(
        self,
        business: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        diffs: List[Dict[str, Any]],
        crawl_sources_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Generate full report and executive summary HTML.
        If this is the first crawl for the business (all competitors have no prior data),
        generates a comprehensive initial competitive analysis.
        Otherwise, generates the standard change-tracking report.
        """
        is_first_crawl_overall = self._is_first_crawl(diffs)

        if is_first_crawl_overall and crawl_sources_map:
            logger.info("Generating comprehensive initial competitive analysis...")
            analysis = self._generate_comprehensive_analysis(business, competitors, crawl_sources_map)
            full_report_html = self._render_initial_report(business, competitors, analysis)
            summary_html = self._render_initial_summary(business, competitors, analysis)
        else:
            logger.info("Generating change-tracking report...")
            full_report_html = self._generate_full_report(business.get("name", "Unknown"), competitors, diffs)
            summary_html = self._generate_summary(business.get("name", "Unknown"), competitors, diffs)

        return {
            "full_report": full_report_html,
            "summary": summary_html,
        }

    def _is_first_crawl(self, diffs: List[Dict[str, Any]]) -> bool:
        """Returns True if all competitors are on their first crawl."""
        if not diffs:
            return False
        return all(diff.get("is_first_crawl", False) for diff in diffs)

    # =====================================================
    # COMPREHENSIVE INITIAL ANALYSIS (FIRST CRAWL)
    # =====================================================

    def _generate_comprehensive_analysis(
        self,
        business: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        crawl_sources_map: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Use Claude to generate a deep competitive analysis."""
        # Build context from crawl data
        context_parts = []
        context_parts.append(f"## YOUR BUSINESS")
        context_parts.append(f"Name: {business.get('name', 'Unknown')}")
        context_parts.append(f"URL: {business.get('url', 'N/A')}")
        context_parts.append(f"Description: {business.get('description', 'N/A')}")
        context_parts.append("")
        context_parts.append("## COMPETITORS DATA")

        for comp in competitors:
            comp_id = comp.get("id")
            sources = crawl_sources_map.get(comp_id, {})
            context_parts.append(f"\n### {comp.get('name')}")
            context_parts.append(f"URL: {comp.get('url')}")

            # Homepage
            homepage = sources.get("homepage", {})
            if homepage.get("status") == "success":
                context_parts.append(f"Homepage Title: {homepage.get('title', '')}")
                context_parts.append(f"Meta Description: {homepage.get('meta_description', '')[:300]}")
                context_parts.append(f"Main Heading: {homepage.get('main_heading', '')}")
                context_parts.append(f"Body Preview: {homepage.get('body_preview', '')[:300]}")

            # Pricing
            pricing = sources.get("pricing", {})
            if pricing.get("status") == "success":
                tiers = pricing.get("tiers", [])
                if isinstance(tiers, list) and tiers:
                    context_parts.append(f"Pricing Tiers: {json.dumps(tiers[:5])}")
                context_parts.append(f"Pricing Page: {pricing.get('content_preview', '')[:300]}")

            # Features
            features = sources.get("features", {})
            if features.get("status") == "success":
                feature_list = features.get("features", [])
                if isinstance(feature_list, list) and feature_list:
                    context_parts.append(f"Features (first 10): {feature_list[:10]}")
                cats = features.get("feature_categories", [])
                if cats:
                    context_parts.append(f"Feature Categories: {cats[:5]}")

            # Jobs
            jobs = sources.get("jobs", {})
            if jobs.get("status") == "success":
                context_parts.append(f"Open Jobs Count: {jobs.get('jobs_count', 0)}")
                sample_jobs = jobs.get("sample_jobs", [])
                if isinstance(sample_jobs, list) and sample_jobs:
                    context_parts.append(f"Sample Jobs: {sample_jobs[:5]}")

            # Blog
            blog = sources.get("blog", {})
            if blog.get("status") == "success":
                if blog.get("type") == "rss":
                    posts = blog.get("posts", [])
                    if posts:
                        titles = [p.get("title", "") for p in posts[:3]]
                        context_parts.append(f"Recent Blog Posts: {titles}")

            # News mentions
            news = sources.get("news", {})
            if news.get("status") == "success":
                articles = news.get("articles", [])
                if articles:
                    headlines = [f"{a.get('title', '')} ({a.get('source', 'unknown')})" for a in articles[:5]]
                    context_parts.append(f"Recent News Mentions: {headlines}")

            # LinkedIn signals
            linkedin = sources.get("linkedin", {})
            if linkedin.get("status") == "success":
                emp = linkedin.get("employee_count")
                fol = linkedin.get("follower_count")
                bits = []
                if emp:
                    bits.append(f"employees: {emp}")
                if fol:
                    bits.append(f"followers: {fol}")
                if bits:
                    context_parts.append(f"LinkedIn: {', '.join(bits)}")

        context = "\n".join(context_parts)

        prompt = f"""You are a senior competitive intelligence analyst creating an initial deep-dive competitive analysis report.

{context}

Based on this data, generate a comprehensive competitive analysis. Output as valid JSON ONLY (no markdown, no explanation outside JSON):

{{
  "executive_overview": "2-3 paragraph narrative summarizing the competitive landscape, market dynamics, and key insights for {business.get('name')}. Be specific and reference competitors by name.",
  "market_positioning": {{
    "market_size_signal": "Indicator of market maturity and size",
    "competitive_intensity": "low/medium/high with brief explanation",
    "key_battlegrounds": ["Battleground 1 (e.g., AI features)", "Battleground 2 (e.g., pricing)"]
  }},
  "comparison_matrix": [
    {{
      "competitor": "Competitor Name",
      "value_proposition": "Their core promise to customers in one sentence",
      "pricing_model": "Free/Freemium/Paid tiers/Enterprise/Custom",
      "target_market": "SMB/Mid-Market/Enterprise/Federal/etc",
      "key_features": ["Feature 1", "Feature 2", "Feature 3"],
      "differentiators": "What makes them unique",
      "hiring_signal": "Hiring trend if visible"
    }}
  ],
  "swot": {{
    "Competitor Name": {{
      "strengths": ["Strength 1", "Strength 2", "Strength 3"],
      "weaknesses": ["Weakness 1", "Weakness 2"],
      "opportunities": ["Opportunity for them 1", "Opportunity for them 2"],
      "threats": ["Threat to them 1", "Threat to them 2"]
    }}
  }},
  "market_gaps": [
    "Gap 1: Underserved use case or segment that {business.get('name')} could capture",
    "Gap 2: ...",
    "Gap 3: ..."
  ],
  "strategic_recommendations": [
    {{
      "title": "Specific recommendation",
      "description": "Why this matters and what to do",
      "priority": "high",
      "rationale": "Evidence from competitor data"
    }}
  ]
}}

Important rules:
- Include SWOT for ALL competitors listed above
- Include comparison matrix entries for ALL competitors
- Provide 5-7 strategic recommendations
- Provide 3-5 market gaps
- Be specific, reference actual data, no generic advice
- Strategic recommendations must be actionable for {business.get('name')}'s product team
"""

        # Try multiple model names for resilience to API renames / SDK age
        model_candidates = [
            "claude-opus-4-7",
            "claude-opus-4-5",
            "claude-sonnet-4-7",
            "claude-sonnet-4-5",
            "claude-3-5-sonnet-latest",
            "claude-3-5-sonnet-20241022",
        ]

        last_error = None
        response_text = None
        used_model = None

        for model in model_candidates:
            try:
                logger.info(f"Attempting Claude analysis with model: {model}")
                message = client.messages.create(
                    model=model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text.strip()
                used_model = model
                logger.info(f"Claude analysis succeeded with model: {model} ({len(response_text)} chars)")
                break
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)[:300]}"
                logger.warning(f"Model {model} failed: {last_error}")
                continue

        if response_text is None:
            error_detail = last_error or "All model candidates failed"
            logger.error(f"Failed to generate comprehensive analysis: {error_detail}")
            return {
                "executive_overview": (
                    f"⚠️ Analysis generation failed for {len(competitors)} competitors.\n\n"
                    f"**Error:** {error_detail}\n\n"
                    f"This is a fallback message — the full SWOT, comparison matrix, and "
                    f"strategic recommendations could not be generated. Most common causes:\n"
                    f"1. Claude API credits depleted (top up at console.anthropic.com)\n"
                    f"2. Model name `claude-opus-4-7` not recognized — SDK may need upgrade\n"
                    f"3. API key missing or invalid\n\n"
                    f"Tried these models in order: {', '.join(model_candidates)}"
                ),
                "market_positioning": {},
                "comparison_matrix": [],
                "swot": {},
                "market_gaps": [],
                "strategic_recommendations": [],
            }

        try:
            # Strip markdown if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            logger.info(f"Successfully parsed analysis from {used_model}: "
                        f"{len(result.get('comparison_matrix', []))} matrix entries, "
                        f"{len(result.get('swot', {}))} SWOTs, "
                        f"{len(result.get('strategic_recommendations', []))} recommendations")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed (model={used_model}): {e}; response head: {response_text[:500]}")
            return {
                "executive_overview": (
                    f"⚠️ Claude returned a response with model `{used_model}` but it was not valid JSON.\n\n"
                    f"**Parse error:** {str(e)[:200]}\n\n"
                    f"**Response preview (first 500 chars):**\n{response_text[:500]}"
                ),
                "market_positioning": {},
                "comparison_matrix": [],
                "swot": {},
                "market_gaps": [],
                "strategic_recommendations": [],
            }

    def _render_initial_report(
        self,
        business: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        analysis: Dict[str, Any],
    ) -> str:
        """Render comprehensive initial report HTML."""
        business_name = business.get("name", "Unknown")
        overview = analysis.get("executive_overview", "")
        positioning = analysis.get("market_positioning", {})
        comparison = analysis.get("comparison_matrix", [])
        swot_data = analysis.get("swot", {})
        gaps = analysis.get("market_gaps", [])
        recommendations = analysis.get("strategic_recommendations", [])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Initial Competitive Analysis - {business_name}</title>
    <style>
        body {{ font-family: -apple-system, Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 1100px; margin: 0 auto; padding: 20px; background: #fafafa; }}
        .header {{ background: linear-gradient(135deg, #1e40af 0%, #3730a3 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 30px; font-weight: 700; }}
        .header .badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; }}
        .header p {{ margin: 5px 0 0 0; opacity: 0.95; font-size: 16px; }}
        .section {{ margin-bottom: 35px; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .section h2 {{ color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 10px; margin: 0 0 20px 0; font-size: 22px; }}
        .section h3 {{ color: #374151; margin-top: 25px; font-size: 18px; }}
        .overview {{ font-size: 15px; line-height: 1.8; color: #374151; }}
        .positioning-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; }}
        .positioning-card {{ background: #f0f7ff; padding: 15px; border-radius: 8px; border-left: 4px solid #1e40af; }}
        .positioning-card .label {{ font-size: 12px; text-transform: uppercase; color: #6b7280; font-weight: 600; }}
        .positioning-card .value {{ font-size: 16px; color: #1f2937; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px; }}
        th, td {{ padding: 10px 8px; text-align: left; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
        th {{ background: #1e40af; color: white; font-weight: 600; font-size: 12px; text-transform: uppercase; }}
        tr:nth-child(even) {{ background: #f9fafb; }}
        .swot {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
        .swot-card {{ padding: 12px; border-radius: 6px; }}
        .swot-S {{ background: #ecfdf5; border-left: 3px solid #059669; }}
        .swot-W {{ background: #fef2f2; border-left: 3px solid #dc2626; }}
        .swot-O {{ background: #eff6ff; border-left: 3px solid #2563eb; }}
        .swot-T {{ background: #fef3c7; border-left: 3px solid #d97706; }}
        .swot-card h4 {{ margin: 0 0 8px 0; font-size: 13px; text-transform: uppercase; }}
        .swot-card ul {{ margin: 0; padding-left: 18px; font-size: 13px; }}
        .swot-card li {{ margin-bottom: 4px; }}
        .competitor-block {{ background: #f9fafb; padding: 18px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #1e40af; }}
        .competitor-block h3 {{ margin: 0 0 12px 0; color: #1e40af; }}
        .gap {{ background: #fef3c7; border-left: 4px solid #d97706; padding: 12px 15px; margin-bottom: 10px; border-radius: 4px; }}
        .recommendation {{ background: #ecfdf5; border-left: 4px solid #059669; padding: 15px; margin-bottom: 12px; border-radius: 6px; }}
        .recommendation .title {{ font-weight: 700; color: #065f46; font-size: 15px; margin-bottom: 6px; }}
        .recommendation .description {{ color: #374151; font-size: 14px; }}
        .recommendation .priority {{ display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; font-weight: 600; }}
        .priority-high {{ background: #dc2626; color: white; }}
        .priority-medium {{ background: #d97706; color: white; }}
        .priority-low {{ background: #6b7280; color: white; }}
        .timestamp {{ color: rgba(255,255,255,0.85); font-size: 12px; margin-top: 8px; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="badge">INITIAL ANALYSIS</span>
        <h1>Competitive Intelligence Deep-Dive</h1>
        <p>Business: <strong>{business_name}</strong> | Competitors analyzed: <strong>{len(competitors)}</strong></p>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>

    <div class="section">
        <h2>📊 Executive Overview</h2>
        <p class="overview">{overview.replace(chr(10), '</p><p class="overview">')}</p>
"""

        if positioning:
            html += """    </div>
    <div class="section">
        <h2>🎯 Market Positioning</h2>
        <div class="positioning-grid">
"""
            if positioning.get("market_size_signal"):
                html += f"""            <div class="positioning-card">
                <div class="label">Market Size Signal</div>
                <div class="value">{positioning.get('market_size_signal')}</div>
            </div>
"""
            if positioning.get("competitive_intensity"):
                html += f"""            <div class="positioning-card">
                <div class="label">Competitive Intensity</div>
                <div class="value">{positioning.get('competitive_intensity')}</div>
            </div>
"""
            html += """        </div>
"""
            battlegrounds = positioning.get("key_battlegrounds", [])
            if battlegrounds:
                html += "<h3>Key Battlegrounds</h3><ul>\n"
                for bg in battlegrounds:
                    html += f"<li>{bg}</li>\n"
                html += "</ul>\n"

        # Comparison Matrix
        if comparison:
            html += """    </div>
    <div class="section">
        <h2>📋 Competitive Comparison Matrix</h2>
        <table>
            <thead>
                <tr>
                    <th>Competitor</th>
                    <th>Value Proposition</th>
                    <th>Pricing Model</th>
                    <th>Target Market</th>
                    <th>Differentiators</th>
                    <th>Hiring Signal</th>
                </tr>
            </thead>
            <tbody>
"""
            for row in comparison:
                html += f"""                <tr>
                    <td><strong>{row.get('competitor', '')}</strong></td>
                    <td>{row.get('value_proposition', '')}</td>
                    <td>{row.get('pricing_model', '')}</td>
                    <td>{row.get('target_market', '')}</td>
                    <td>{row.get('differentiators', '')}</td>
                    <td>{row.get('hiring_signal', '')}</td>
                </tr>
"""
            html += """            </tbody>
        </table>
"""
            # Show key features as separate section per competitor
            html += "<h3>Key Features by Competitor</h3>\n"
            for row in comparison:
                features = row.get("key_features", [])
                if features:
                    html += f"""<div class="competitor-block">
<h3>{row.get('competitor', '')}</h3>
<ul>
"""
                    for feat in features:
                        html += f"<li>{feat}</li>\n"
                    html += "</ul></div>\n"

        # SWOT Analysis
        if swot_data:
            html += """    </div>
    <div class="section">
        <h2>⚖️ SWOT Analysis</h2>
"""
            for comp_name, swot in swot_data.items():
                html += f"""        <div class="competitor-block">
            <h3>{comp_name}</h3>
            <div class="swot">
                <div class="swot-card swot-S">
                    <h4>💪 Strengths</h4>
                    <ul>
"""
                for s in swot.get("strengths", []):
                    html += f"                        <li>{s}</li>\n"
                html += """                    </ul>
                </div>
                <div class="swot-card swot-W">
                    <h4>⚠️ Weaknesses</h4>
                    <ul>
"""
                for w in swot.get("weaknesses", []):
                    html += f"                        <li>{w}</li>\n"
                html += """                    </ul>
                </div>
                <div class="swot-card swot-O">
                    <h4>🚀 Opportunities</h4>
                    <ul>
"""
                for o in swot.get("opportunities", []):
                    html += f"                        <li>{o}</li>\n"
                html += """                    </ul>
                </div>
                <div class="swot-card swot-T">
                    <h4>⚡ Threats</h4>
                    <ul>
"""
                for t in swot.get("threats", []):
                    html += f"                        <li>{t}</li>\n"
                html += """                    </ul>
                </div>
            </div>
        </div>
"""

        # Market Gaps
        if gaps:
            html += """    </div>
    <div class="section">
        <h2>🎯 Market Gaps & Opportunities</h2>
        <p style="color: #6b7280; font-size: 14px;">Underserved segments where <strong>""" + business_name + """</strong> can win:</p>
"""
            for gap in gaps:
                html += f"""        <div class="gap">{gap}</div>
"""

        # Strategic Recommendations
        if recommendations:
            html += """    </div>
    <div class="section">
        <h2>🚀 Strategic Recommendations</h2>
"""
            for rec in recommendations:
                priority = rec.get("priority", "medium").lower()
                html += f"""        <div class="recommendation">
            <div><span class="priority priority-{priority}">{priority.upper()}</span></div>
            <div class="title" style="margin-top: 8px;">{rec.get('title', '')}</div>
            <div class="description">{rec.get('description', '')}</div>
"""
                if rec.get("rationale"):
                    html += f"""            <div style="margin-top: 8px; font-size: 13px; color: #6b7280;"><em>Rationale: {rec.get('rationale')}</em></div>
"""
                html += """        </div>
"""

        html += """    </div>

    <div style="margin-top: 30px; padding: 15px; text-align: center; color: #6b7280; font-size: 12px;">
        <p>This is your initial competitive baseline. From tomorrow, you'll receive daily updates on changes detected.</p>
    </div>

</body>
</html>
"""
        return html

    def _render_initial_summary(
        self,
        business: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        analysis: Dict[str, Any],
    ) -> str:
        """Render compact executive summary for initial report."""
        business_name = business.get("name", "Unknown")
        overview = analysis.get("executive_overview", "")
        recommendations = analysis.get("strategic_recommendations", [])[:5]
        gaps = analysis.get("market_gaps", [])[:3]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Initial Analysis Summary - {business_name}</title>
    <style>
        body {{ font-family: -apple-system, Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 800px; margin: 0 auto; padding: 20px; background: #fafafa; }}
        .header {{ background: linear-gradient(135deg, #1e40af 0%, #3730a3 100%); color: white; padding: 25px; border-radius: 10px; margin-bottom: 25px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 11px; margin-bottom: 8px; }}
        .section {{ margin-bottom: 25px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #1e40af; font-size: 18px; margin: 0 0 12px 0; }}
        .recommendation {{ background: #ecfdf5; border-left: 3px solid #059669; padding: 12px; margin-bottom: 10px; border-radius: 4px; }}
        .recommendation .title {{ font-weight: 600; color: #065f46; }}
        .recommendation .priority {{ display: inline-block; font-size: 10px; padding: 2px 6px; border-radius: 8px; margin-left: 8px; vertical-align: middle; }}
        .priority-high {{ background: #dc2626; color: white; }}
        .priority-medium {{ background: #d97706; color: white; }}
        .priority-low {{ background: #6b7280; color: white; }}
        .gap {{ background: #fef3c7; border-left: 3px solid #d97706; padding: 10px; margin-bottom: 8px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="badge">INITIAL ANALYSIS</span>
        <h1>📋 Executive Summary</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.95;">15-minute brief on your competitive landscape</p>
    </div>

    <div class="section">
        <h2>📊 Market Overview</h2>
        <p>{overview}</p>
    </div>
"""

        if gaps:
            html += """    <div class="section">
        <h2>🎯 Top Market Gaps</h2>
"""
            for gap in gaps:
                html += f"""        <div class="gap">{gap}</div>
"""
            html += """    </div>
"""

        if recommendations:
            html += """    <div class="section">
        <h2>🚀 Top Strategic Recommendations</h2>
"""
            for rec in recommendations:
                priority = rec.get("priority", "medium").lower()
                html += f"""        <div class="recommendation">
            <div class="title">{rec.get('title', '')}<span class="priority priority-{priority}">{priority.upper()}</span></div>
            <div style="margin-top: 6px; font-size: 14px;">{rec.get('description', '')}</div>
        </div>
"""
            html += """    </div>
"""

        html += """    <div style="margin-top: 25px; text-align: center; color: #6b7280; font-size: 12px;">
        <p>📩 See the full report below for SWOT analysis, comparison matrix, and detailed competitor profiles.</p>
    </div>
</body>
</html>
"""
        return html

    # =====================================================
    # CHANGE-TRACKING REPORT (SUBSEQUENT CRAWLS)
    # =====================================================

    def _generate_full_report(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> str:
        """Generate full detailed report HTML for change tracking."""
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
            <p class="no-changes">First crawl - baseline established</p>
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
                    if isinstance(source_changes, dict) and source_changes.get("status") == "no_changes":
                        continue
                    html += f"""            <div class="change-item">
                <strong>{source_type.upper()}:</strong><br/>
"""
                    # Special-case news so we render readable headlines + links
                    if source_type == "news" and isinstance(source_changes, dict) and source_changes.get("new_articles"):
                        for art in source_changes["new_articles"]:
                            title = art.get("title", "")
                            url = art.get("url", "")
                            source = art.get("source", "")
                            published = art.get("published", "")
                            meta_bits = [b for b in [source, published] if b]
                            meta = f" — <em>{' · '.join(meta_bits)}</em>" if meta_bits else ""
                            if url:
                                html += f'                • <a href="{url}">{title}</a>{meta}<br/>\n'
                            else:
                                html += f"                • {title}{meta}<br/>\n"
                    elif isinstance(source_changes, dict):
                        for key, value in source_changes.items():
                            if key != "status":
                                html += f"                {key}: {json.dumps(value)[:200]}...<br/>\n"
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
        """Generate 15-minute executive summary for change tracking."""
        bullet_points = self._extract_key_insights(competitors, diffs)
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
        .insight {{ background: #f0f7ff; padding: 12px; border-left: 3px solid #1e40af; margin-bottom: 10px; border-radius: 4px; }}
        .recommendation {{ background: #fef3c7; padding: 12px; border-left: 3px solid #d97706; margin-bottom: 10px; border-radius: 4px; }}
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
                    if "pricing" in changes:
                        pricing_changes = changes["pricing"]
                        if "pricing_changed" in pricing_changes:
                            bullets.append("Pricing updated")
                        if "tier_count_changed" in pricing_changes:
                            bullets.append("Pricing tier structure changed")
                    if "features" in changes:
                        feature_changes = changes["features"]
                        if "features_added" in feature_changes:
                            bullets.append(f"{len(feature_changes['features_added'])} new features added")
                        if "features_removed" in feature_changes:
                            bullets.append(f"{len(feature_changes['features_removed'])} features removed")
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
                    if "news" in changes:
                        news_changes = changes["news"]
                        if "new_articles" in news_changes:
                            article_count = news_changes.get("new_article_count", len(news_changes["new_articles"]))
                            # Surface the most recent headline for context
                            first = news_changes["new_articles"][0]
                            headline = first.get("title", "")[:80]
                            source = first.get("source", "")
                            bullets.append(
                                f"{article_count} new news mention(s) — e.g., \"{headline}\""
                                + (f" ({source})" if source else "")
                            )
                    if "linkedin" in changes:
                        li_changes = changes["linkedin"]
                        if "employee_count_changed" in li_changes:
                            ec = li_changes["employee_count_changed"]
                            bullets.append(
                                f"LinkedIn headcount signal: {ec.get('previous') or '—'} → {ec.get('current') or '—'}"
                            )
                        if "follower_count_changed" in li_changes:
                            fc = li_changes["follower_count_changed"]
                            bullets.append(
                                f"LinkedIn followers: {fc.get('previous') or '—'} → {fc.get('current') or '—'}"
                            )

            insights.append({
                "name": comp.get("name", "Unknown"),
                "bullets": bullets[:5] if bullets else ["No changes detected"],
            })
        return insights

    def _generate_recommendations(self, business_name: str, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use Claude to generate strategic recommendations for change tracking."""
        competitive_context = self._build_competitive_context(competitors, diffs)

        prompt = f"""You are a product strategy advisor. Based on the following competitive intelligence for {business_name}, provide:

1. A brief "What This Means" paragraph (2-3 sentences)
2. 2-3 specific, prioritized "Recommended Actions"

Competitive Context:
{competitive_context}

Respond as valid JSON only (no markdown):
{{
  "what_it_means": "Your insight here...",
  "actions": [
    {{"title": "Action 1", "description": "Why and what to do..."}}
  ]
}}
"""

        try:
            message = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return {
                "what_it_means": "Monitor competitors for strategic insights.",
                "actions": [{"title": "Continue Monitoring", "description": "Keep tracking competitor signals daily"}]
            }

    def _build_competitive_context(self, competitors: List[Dict[str, Any]], diffs: List[Dict[str, Any]]) -> str:
        """Build a text summary of competitive landscape."""
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
