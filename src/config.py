import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Claude API
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Resend
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# Email
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@competitive-tracker.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Competitive Intel")

# Crawler
CRAWL_TIMEOUT_SECONDS = int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30"))
CRAWL_DELAY_SECONDS = int(os.getenv("CRAWL_DELAY_SECONDS", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

def validate_config():
    """Validate that all required env vars are set."""
    required = ["SUPABASE_URL", "SUPABASE_KEY", "CLAUDE_API_KEY", "RESEND_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
