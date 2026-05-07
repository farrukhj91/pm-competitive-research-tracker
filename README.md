# Competitive Research Tracker

Automated competitor intelligence system. Crawls competitor websites daily, diffs changes, and emails you AI-powered insights every morning.

## Features

- **Automatic Competitor Identification**: Use Claude API to find 5-10 direct competitors from business description
- **Multi-Source Web Crawling**: Extracts pricing, features, jobs, blog posts, and more
- **Change Detection**: Diffs crawl results to highlight what changed since yesterday
- **AI-Powered Reports**: HTML emails with full detailed report + 15-min executive summary
- **Smart Recommendations**: Claude analyzes signals and suggests product/positioning actions
- **Daily Automation**: Runs at 8:00 AM PKT via GitHub Actions
- **CLI Management**: Add businesses, trigger crawls, view reports from terminal

## Tech Stack

- **Python**: Core crawler, diff engine, report generation
- **Supabase**: PostgreSQL database (free tier)
- **Claude API**: Competitor identification + AI recommendations
- **Resend**: Transactional emails (free tier)
- **GitHub Actions**: Scheduler (runs daily at 3 AM UTC = 8 AM PKT)
- **Playwright + BeautifulSoup**: Web scraping
- **Click + Rich**: CLI interface

## Architecture

```
User → CLI (add-business)
  ↓
Claude identifies competitors
  ↓
Supabase stores business & competitors
  ↓
GitHub Actions scheduler (daily 3 AM UTC)
  ↓
Crawler (pricing, features, homepage, jobs, blog)
  ↓
Diff Engine (compares with previous crawl)
  ↓
Report Generator (AI analysis + recommendations)
  ↓
Resend Email → User inbox
```

## Setup Instructions

### Step 1: Create Accounts & Get API Keys

#### Supabase (Database)
1. Go to [supabase.com](https://supabase.com)
2. Sign up (free tier includes 500MB storage, enough for 90 days of crawl data)
3. Create a new project
4. Go to **Settings > API** and copy:
   - `SUPABASE_URL`
   - `anon` key → `SUPABASE_KEY`
5. Go to **SQL Editor** and run the schema migrations (see below)

#### Claude API (Competitor Identification & Recommendations)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / log in
3. Create an API key
4. Copy the key → `CLAUDE_API_KEY`

#### Resend (Email)
1. Go to [resend.com](https://resend.com)
2. Sign up (free tier: 100 emails/day)
3. Go to **API Keys** and create one → `RESEND_API_KEY`
4. In **Sending Domain**, add or verify a domain (or use Resend's sandbox)
5. Copy your sending email → `SENDER_EMAIL`

#### GitHub (Scheduler)
1. Create a public or private GitHub repo
2. Go to **Settings > Secrets and variables > Actions**
3. Add secrets (see Environment Variables section below)

### Step 2: Set Up Local Development

```bash
# Clone repo
git clone <your-repo>
cd competitive-tracker

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy .env.example and fill in your API keys
cp .env.example .env
# Edit .env with your API keys
```

### Step 3: Initialize Database

Create a `.env` file with your Supabase credentials, then run migrations:

```bash
python -c "
from src.db import db
from src.config import validate_config

validate_config()
db.run_migrations()
print('✓ Database initialized')
"
```

Or manually run these SQL migrations in Supabase SQL Editor:

```sql
-- Businesses
CREATE TABLE IF NOT EXISTS businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  url VARCHAR(2048),
  description TEXT,
  user_email VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Competitors
CREATE TABLE IF NOT EXISTS competitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  url VARCHAR(2048),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT now()
);

-- Crawl Results
CREATE TABLE IF NOT EXISTS crawl_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
  crawl_timestamp TIMESTAMP NOT NULL,
  sources JSONB NOT NULL,
  status VARCHAR(50),
  error_message TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Crawl Diffs
CREATE TABLE IF NOT EXISTS crawl_diffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
  previous_crawl_id UUID REFERENCES crawl_results(id),
  current_crawl_id UUID REFERENCES crawl_results(id),
  changes JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

-- Reports
CREATE TABLE IF NOT EXISTS reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
  report_date DATE,
  full_report_html TEXT,
  summary_html TEXT,
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_competitors_business_id ON competitors(business_id);
CREATE INDEX IF NOT EXISTS idx_crawl_results_competitor_id ON crawl_results(competitor_id);
CREATE INDEX IF NOT EXISTS idx_crawl_diffs_competitor_id ON crawl_diffs(competitor_id);
CREATE INDEX IF NOT EXISTS idx_reports_business_id ON reports(business_id);
```

### Step 4: Add Your First Business

```bash
python -m src.cli add-business
```

You'll be prompted to:
1. Enter business name
2. Enter business URL (or description)
3. Enter your email for daily reports
4. Review identified competitors (AI-powered)
5. Confirm and save

Example:
```
Business name: Acme SaaS
Business URL: https://acme.com
Your email: you@example.com

🔍 Identified competitors...
[Displays 5-10 competitors with confidence scores]
Save these competitors? [Y/n]: y
✓ Saved 8 competitors

Run first crawl now? [Y/n]: y
```

### Step 5: Trigger First Crawl

```bash
# View your business ID
python -m src.cli list-businesses

# Manual crawl
python -m src.cli crawl-now <BUSINESS_ID>
```

This will:
1. Crawl all competitors (pricing, features, blog, jobs, etc.)
2. Store results in database
3. Generate full report + executive summary
4. Send email to your inbox

You should receive the report within a minute.

### Step 6: Deploy to GitHub Actions

1. Commit your code to GitHub:
```bash
git add .
git commit -m "Initial commit: competitive research tracker"
git push origin main
```

2. In GitHub, go to **Settings > Secrets and variables > Actions**

3. Add these secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `CLAUDE_API_KEY`
   - `RESEND_API_KEY`
   - `SENDER_EMAIL` (e.g., noreply@yourdomain.com)

4. Go to **Actions** tab and verify the workflow:
   - You should see **"Daily Competitive Research Crawl"** workflow
   - It's scheduled to run every day at **3:00 AM UTC** (8:00 AM PKT)
   - You can manually trigger it with **"Run workflow"**

5. Test it: Click **"Run workflow"** to test immediately

6. Wait for the first scheduled run tomorrow at 3 AM UTC (or trigger manually)

## CLI Commands

```bash
# Add a new business
python -m src.cli add-business

# List all businesses
python -m src.cli list-businesses

# Show competitors for a business
python -m src.cli show-competitors <BUSINESS_ID>

# Add competitor manually
python -m src.cli add-competitor <BUSINESS_ID> --name "Competitor" --url "https://..."

# Trigger manual crawl
python -m src.cli crawl-now <BUSINESS_ID>

# View past reports
python -m src.cli view-reports <BUSINESS_ID>
```

## What Gets Crawled (Per Competitor)

Each day, the system crawls (where publicly accessible):

- **Pricing page**: Tiers, prices, limits, feature inclusions
- **Features/Product page**: Feature list, positioning changes
- **Homepage**: Taglines, messaging, CTA changes
- **Blog/Changelog**: New posts, announcements
- **Jobs/Careers page**: Open positions, headcount signals
- **News**: Recent mentions (placeholder for free API)

If a page requires login or is behind a paywall, it's flagged as "login blocked" and skipped gracefully.

## Email Report Structure

### Section 1: Full Report
- **Competitor Overview**: Table of all competitors × status
- **Change Log**: Detailed per-competitor changes since yesterday
- "No changes detected" notation if nothing changed

### Section 2: Executive Summary (15 min read)
- **Key Changes**: 3-5 bullets per competitor
- **What This Means**: 1-2 paragraph on collective signals
- **Recommended Actions**: 2-3 specific suggestions from Claude

## Data Retention & Cleanup

- **Crawl history**: Kept for 90 days (configurable via `RETENTION_DAYS`)
- **Reports**: Kept indefinitely
- **Automatic cleanup**: Runs weekly via scheduler (old crawl results deleted)

To adjust retention, edit `.env`:
```
RETENTION_DAYS=180  # Keep 6 months instead of 90 days
```

## Environment Variables

Create a `.env` file in the project root:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1...

# Claude API
CLAUDE_API_KEY=sk-ant-...

# Resend Email
RESEND_API_KEY=re_...

# Email config
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Competitive Intel

# Crawler config
CRAWL_TIMEOUT_SECONDS=30
CRAWL_DELAY_SECONDS=2
MAX_RETRIES=3
RETENTION_DAYS=90

# Logging
LOG_LEVEL=INFO
```

## Cost Estimate (Monthly, Free Tier)

| Service | Free Tier | Cost | Notes |
|---------|-----------|------|-------|
| Supabase | 500MB storage | $0 | Enough for 90 days |
| Claude API | Pay-as-you-go | ~$1-3 | ~500 API calls/month |
| Resend | 100 emails/day | $0 | Enough for 1-2 businesses |
| GitHub Actions | 2000 min/month | $0 | ~1 min/day crawl |
| **Total** | - | **~$1-3/month** | - |

## Troubleshooting

### "Missing required environment variables"
- Make sure `.env` file exists and has all required keys
- Run `python -c "from src.config import validate_config; validate_config()"`

### "Resend API key not configured"
- Check `RESEND_API_KEY` in `.env`
- Verify domain is verified in Resend dashboard

### "No competitors identified"
- Check `CLAUDE_API_KEY` is valid
- Try with more specific business description
- Claude API may have rate limits (free tier)

### GitHub Actions workflow not running
- Go to **Actions** tab in GitHub repo
- Check for workflow run history
- If no runs, manually trigger: **"Run workflow" button**
- Verify secrets are set in repo settings

### Email not received
- Check spam folder
- Verify recipient email in business record
- Check GitHub Actions logs for errors

### Crawler timeouts
- Increase `CRAWL_TIMEOUT_SECONDS` in `.env` (default 30)
- Some sites may be slow to load

## Phase 2: Web Dashboard (Future)

Once MVP is stable, Phase 2 will add:

- React web UI for dashboard (hosted on Vercel/Netlify)
- CRUD interface: add/edit/remove businesses and competitors
- View past reports with filtering and search
- Manual crawl trigger from web UI
- Pause/resume daily updates per business
- Crawl history timeline and diffs

## Development Tips

### Running with Logging

```bash
LOG_LEVEL=DEBUG python -m src.cli add-business
```

### Testing Crawler Standalone

```python
from src.crawler import crawler

sources = crawler.crawl_competitor(
    "Slack",
    "https://slack.com"
)
print(sources)
```

### Testing Report Generation

```python
from src.report_generator import report_generator

report = report_generator.generate_report(
    business_name="Acme",
    competitors=[{"id": "1", "name": "Slack", "url": "https://slack.com"}],
    diffs=[{"competitor_id": "1", "changes": {"pricing": {"tiers": 3}}}]
)
print(report["summary"][:200])
```

## Contributing

This is a personal project—feel free to fork and extend!

**Ideas for extensions:**
- Add LinkedIn headcount API integration
- Add Crunchbase funding tracking
- Add G2/Trustpilot sentiment analysis
- Add Slack webhook notifications
- Add web dashboard (Phase 2)
- Support for private competitor sites (auth)

## License

MIT

## Support

For issues, check the logs:

```bash
# View logs from last scheduler run
python -m src.scheduler --all  # Runs manually with verbose output

# Check GitHub Actions logs
# Go to repo > Actions > click failed run
```

---

**Next Steps:**
1. Set up accounts (Supabase, Claude API, Resend)
2. Clone this repo and set up `.env`
3. Run `python -m src.cli add-business` to test
4. Deploy to GitHub Actions
5. Receive daily reports at 8:00 AM PKT!
