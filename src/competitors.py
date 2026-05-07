import json
import logging
from typing import List, Dict, Any, Optional

from anthropic import Anthropic
from src.config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)
client = Anthropic(api_key=CLAUDE_API_KEY)

def identify_competitors(business_name: str, business_url: Optional[str] = None, business_description: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Use Claude API to identify 5-10 direct competitors for a business.
    Returns list of competitors with name, url, and confidence score.
    """
    context = f"Business: {business_name}"
    if business_url:
        context += f"\nWebsite: {business_url}"
    if business_description:
        context += f"\nDescription: {business_description}"

    prompt = f"""You are a competitive analysis expert. Based on the business information provided, identify 5-10 direct competitors.

{context}

Please provide ONLY a valid JSON array (no markdown, no extra text) with the following structure:
[
  {{"name": "Competitor Name", "url": "https://competitor.com", "category": "Brief category", "confidence": 0.95}},
  ...
]

Rules:
- Name: Full company name
- URL: Primary website URL (must be valid, no placeholders)
- Category: Brief category or positioning (e.g., "SaaS Project Management", "Freemium Cloud Storage")
- Confidence: 0.0-1.0 score for how directly competitive they are
- Sort by confidence descending
- Only include direct competitors, not adjacent markets
- Ensure all URLs are real, currently active companies
"""

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text.strip()

    # Parse JSON from response
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        competitors = json.loads(response_text)
        logger.info(f"Identified {len(competitors)} competitors for {business_name}")
        return competitors
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse competitor JSON: {e}\nResponse: {response_text}")
        return []

def format_competitors_for_review(competitors: List[Dict[str, Any]]) -> str:
    """Format competitors for CLI review/confirmation."""
    output = "\n" + "=" * 60 + "\n"
    output += "IDENTIFIED COMPETITORS\n"
    output += "=" * 60 + "\n\n"

    for idx, comp in enumerate(competitors, 1):
        confidence = comp.get("confidence", 0) * 100
        output += f"{idx}. {comp.get('name', 'Unknown')}\n"
        output += f"   URL: {comp.get('url', 'N/A')}\n"
        output += f"   Category: {comp.get('category', 'N/A')}\n"
        output += f"   Confidence: {confidence:.0f}%\n\n"

    output += "=" * 60 + "\n"
    return output
