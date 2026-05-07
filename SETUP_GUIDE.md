# Competitive Research Tracker — Complete Setup Guide

This guide walks you through setting up the Competitive Research Tracker from scratch.

## Overview

The system tracks competitor websites daily and emails you AI-powered insights every morning at 8:00 AM PKT. Everything runs automatically on GitHub Actions—no server to manage.

**Cost**: ~$1-3/month (free tiers only)

**Time to set up**: ~30-45 minutes

---

## Phase 1: Create Required Accounts (15 minutes)

### 1.1 Supabase (Database)

Supabase provides PostgreSQL with a generous free tier (500MB storage).

**Steps:**
1. Go to [supabase.com](https://supabase.com)
2. Sign up with email/GitHub
3. Create a new project:
   - **Name**: `competitive-tracker`
   - **Password**: Generate a strong password (save it)
   - **Region**: Choose closest to you
   - **Pricing Plan**: Free
4. Wait for project to deploy (2-3 minutes)
5. Go to **Settings > API** (left sidebar)
6. Copy and save:
   - **Project URL** → `SUPABASE_URL`
   - **Anon key** → `SUPABASE_KEY`

✅ **Now you have**: `SUPABASE_URL`, `SUPABASE_KEY`

---

### 1.2 Claude API (Competitor Identification)

Claude identifies 5-10 competitors automatically using web search.

**Steps:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up with email
3. Go to **API Keys** (left sidebar)
4. Click **Create Key**
5. Name it "competitive-tracker"
6. Copy the full key (starts with `sk-ant-`) → `CLAUDE_API_KEY`

⚠️ **Do not share this key publicly**

✅ **Now you have**: `CLAUDE_API_KEY`

---

### 1.3 Resend (Email)

Resend sends beautiful HTML emails. Free tier: 100 emails/day (plenty for 1-2 businesses).

**Steps:**
1. Go to [resend.com](https://resend.com)
2. Sign up with email
3. Go to **API Keys** (left sidebar)
4. Click **Create API Key**
5. Copy the key (starts with `re_`) → `RESEND_API_KEY`
6. Go to **Domains** section
7. Either:
   - **Option A (Sandbox)**: Use Resend's sandbox domain (emails sent to test@resend.dev work immediately)
   - **Option B (Custom Domain)**: Add your own domain (requires DNS verification)
8. Copy the sending email address → `SENDER_EMAIL`
   - Sandbox example: `onboarding@resend.dev`
   - Custom example: `noreply@yourdomain.com`

✅ **Now you have**: `RESEND_API_KEY`, `SENDER_EMAIL`

---

### 1.4 GitHub (Scheduler & Deployment)

GitHub Actions runs the crawler daily at 3 AM UTC (8 AM PKT).

**Steps:**
1. Go to [github.com](https://github.com)
2. Sign up / log in
3. Create a new repository:
   - **Name**: `competitive-tracker`
   - **Visibility**: Public or Private
   - **Initialize with**: No (we'll push code)
4. Click **Create repository**
5. Copy the repo URL for cloning

✅ **Now you have**: GitHub repo ready

---

## Phase 2: Local Setup (10 minutes)

### 2.1 Clone & Install

```bash
# Clone the repo (replace with your repo URL)
git clone https://github.com/YOUR_USERNAME/competitive-tracker.git
cd competitive-tracker

# Create Python virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for JavaScript rendering)
playwright install chromium
```

### 2.2 Create `.env` File

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env` with your text editor and fill in:

```env
# From Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1...

# From Claude API
CLAUDE_API_KEY=sk-ant-...

# From Resend
RESEND_API_KEY=re_...
SENDER_EMAIL=onboarding@resend.dev  # or your domain

# Defaults (leave as-is for now)
SENDER_NAME=Competitive Intel
CRAWL_TIMEOUT_SECONDS=30
CRAWL_DELAY_SECONDS=2
MAX_RETRIES=3
RETENTION_DAYS=90
LOG_LEVEL=INFO
```

### 2.3 Initialize Database

Run the database migrations:

```bash
python -c "
from src.db import db
from src.config import validate_config

validate_config()
print('✓ Config validated')

db.run_migrations()
print('✓ Database initialized')
"
```

Or manually run SQL in Supabase dashboard:
1. Go to [supabase.com](https://supabase.com)
2. Open your project
3. Go to **SQL Editor** (left sidebar)
4. Click **New Query**
5. Copy-paste the SQL from README.md's "Step 3" section
6. Click **Run**

✅ **Now your database is ready**

---

## Phase 3: Test Locally (10 minutes)

### 3.1 Add Your First Business

```bash
python main.py add-business
```

You'll be prompted:
```
Business name: Acme Corp
Business URL [optional]: https://acme.com
Your email: your-email@example.com
```

The system will then:
1. Call Claude API to identify 5-10 competitors
2. Display them for your review
3. Ask for confirmation to save

Example output:
```
🔍 Identifying competitors...

============================================================
IDENTIFIED COMPETITORS
============================================================

1. Slack
   URL: https://slack.com
   Category: SaaS Communication Platform
   Confidence: 98%

2. Microsoft Teams
   URL: https://microsoft.com/teams
   Category: Enterprise Communication
   Confidence: 96%

[... 6 more ...]

============================================================

Save these competitors? [y/N]: y
✓ Saved 8 competitors

Run first crawl now? [y/N]: y
🚀 Starting crawl...
```

### 3.2 Wait for First Report

The crawl takes 2-3 minutes. You should receive an email at your inbox with:
- **Full Report**: Detailed competitor analysis
- **Executive Summary**: 3-5 key insights per competitor + recommendations

✅ **If you got the email, local setup works!**

### 3.3 Try CLI Commands

```bash
# List businesses
python main.py list-businesses

# View competitors for a business
python main.py show-competitors <BUSINESS_ID>

# View past reports
python main.py view-reports <BUSINESS_ID>

# Manually trigger a crawl
python main.py crawl-now <BUSINESS_ID>
```

---

## Phase 4: Deploy to GitHub (10 minutes)

Now your system runs automatically every day at 8:00 AM PKT.

### 4.1 Add GitHub Secrets

GitHub Actions needs your API keys to run. Add them to your repo:

1. Go to your GitHub repo
2. Click **Settings** (top right)
3. Go to **Secrets and variables > Actions** (left sidebar)
4. Click **New repository secret**
5. Add these 5 secrets one by one:

| Secret Name | Value | From |
|------------|-------|------|
| `SUPABASE_URL` | `https://your-project.supabase.co` | Supabase Settings > API |
| `SUPABASE_KEY` | Your anon key | Supabase Settings > API |
| `CLAUDE_API_KEY` | `sk-ant-...` | Claude console.anthropic.com |
| `RESEND_API_KEY` | `re_...` | Resend resend.com |
| `SENDER_EMAIL` | `onboarding@resend.dev` | Resend (or your domain) |

⚠️ **These secrets are encrypted. GitHub will not show them again.**

### 4.2 Push Code to GitHub

```bash
# Add all files
git add .

# Commit (already done, but show the flow)
git commit -m "Setup: Ready for deployment"

# Push to GitHub
git push -u origin main
```

### 4.3 Verify Workflow

1. Go to your GitHub repo
2. Click **Actions** (top tabs)
3. You should see **"Daily Competitive Research Crawl"** workflow
4. Click it to see details

**To test immediately** (instead of waiting until tomorrow 3 AM UTC):
1. Click **Daily Competitive Research Crawl**
2. Click **Run workflow** button
3. Check **Show logs** to watch it execute

The workflow will:
- Set up Python environment
- Install dependencies
- Download Playwright browser
- Run crawler for all businesses
- Email reports
- Cleanup old data

Expected time: 5-10 minutes for first run

### 4.4 Verify First Scheduled Run

The workflow is set to run daily at **3:00 AM UTC** (8:00 AM PKT).

To verify it ran:
1. Check your email inbox for "[Competitive Intel] Daily Report"
2. Go to GitHub repo > **Actions** to see execution history
3. Reports are also stored in Supabase (database)

---

## Monitoring & Maintenance

### Daily Checks (optional)

Check email inbox for daily reports. If you don't receive one:
1. Go to GitHub > **Actions** > **Daily Competitive Research Crawl**
2. Look for failed runs
3. Click failed run to see error logs

### Weekly Checks (optional)

```bash
# List all businesses and their status
python main.py list-businesses

# Manually trigger crawl if needed
python main.py crawl-now <BUSINESS_ID>

# View database size in Supabase
# Settings > Usage > Check Database Bytes
```

### Monthly Actions (optional)

1. **Add new businesses**:
   ```bash
   python main.py add-business
   ```

2. **Remove inactive competitors**:
   - Log into Supabase
   - Go to **competitors** table
   - Set `is_active = false` for companies you no longer care about

3. **Adjust retention period**:
   - Edit `.env`: `RETENTION_DAYS=180` (if you want longer history)
   - Push changes to GitHub

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"

**Fix**: Make sure you're in the project root directory:
```bash
cd competitive-tracker
python main.py add-business
```

### "Missing required environment variables"

**Fix**: Check `.env` file has all keys:
```bash
cat .env
```

Ensure these are set:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `CLAUDE_API_KEY`
- `RESEND_API_KEY`
- `SENDER_EMAIL`

### "Failed to connect to Supabase"

**Fix**: Verify connection string:
1. Go to Supabase project
2. Settings > API
3. Copy exact URL and key
4. Update `.env`

### "No email received"

**Checks**:
1. Confirm email in business record: `python main.py list-businesses`
2. Check Resend sending email is verified (Resend dashboard > Domains)
3. Check spam folder
4. If using sandbox domain, only `test@resend.dev` receives emails initially
5. View GitHub Actions logs for errors: Repo > Actions > click run > Logs

### "Competitors not identified (empty list)"

**Fixes**:
1. Claude API rate limit? Try again in 5 minutes
2. Check `CLAUDE_API_KEY` is valid and not revoked
3. Try with more specific business description (not just name)

### GitHub Actions not running

**Checks**:
1. Workflow file exists: `.github/workflows/daily_crawl.yml`
2. Schedule is correct: Cron syntax `0 3 * * *` = 3 AM UTC daily
3. Secrets are set in repo (Settings > Secrets and variables)
4. Manually trigger to test: Actions > "Run workflow" button

---

## What's Next?

### ✅ You've completed Phase 1 (MVP)
- [x] Competitor identification
- [x] Daily crawling
- [x] Email reports with AI insights
- [x] Automated scheduling

### 🚀 Phase 2 (Future): Web Dashboard
- React web UI for business management
- Visual competitor comparison
- Report history viewer
- Manual trigger controls

### 💡 Ideas to Extend
- Add G2/Trustpilot rating tracking
- Add Crunchbase funding tracking
- Add LinkedIn headcount trends
- Add Slack webhook notifications
- Add SMS alerts for major changes

---

## Support & Documentation

- **README.md**: Full feature documentation
- **GitHub Issues**: Report bugs or request features
- **Environment Variables**: See `.env.example` for all options
- **CLI Help**: `python main.py --help`

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python main.py add-business` | Add new company to track |
| `python main.py list-businesses` | Show all companies |
| `python main.py show-competitors <ID>` | View competitors for business |
| `python main.py add-competitor <ID> --name "..." --url "..."` | Add competitor manually |
| `python main.py crawl-now <ID>` | Trigger crawl immediately |
| `python main.py view-reports <ID>` | View past reports |

| Dashboard | Purpose |
|-----------|---------|
| Supabase | View raw database, troubleshoot |
| GitHub Actions | View scheduled run history, logs |
| Your Email | Receive daily reports |

| Service | Free Tier | Cost/Month |
|---------|-----------|-----------|
| Supabase | 500MB storage | $0 |
| Claude API | Pay-as-you-go | ~$1-3 |
| Resend | 100 emails/day | $0 |
| GitHub Actions | 2000 min/month | $0 |
| **Total** | | ~$1-3 |

---

**You're all set! Your competitive research tracker will email you daily insights every morning.** 🚀
