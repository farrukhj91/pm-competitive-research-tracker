# CLAUDE.md — Competitive Research Tracker

> This file is auto-loaded at the start of every Claude Code session. Update it whenever decisions change.

## Project Overview

**What it is:** Automated competitor intelligence system for **Lead Pursuits** (GovCon market). Crawls competitor websites daily, diffs changes, and emails AI-powered insights every morning at **8:00 AM PKT (3:00 AM UTC)**.

**Owner:** Farrukh Jamal (`farrukh.jamal91@gmail.com`)

**Status:** Phase 1 MVP **DEPLOYED & WORKING** as of 2026-05-09. Emails are arriving successfully.

## Business Context: Lead Pursuits

Lead Pursuits aggregates government/procurement opportunities and bids from sources like sam.gov, agency websites, and third-party portals (PlanetBids, etc.) into a unified platform. Features:
- Vectorized data of agencies, vendors, and live opportunities
- AI chat interface (e.g., "Show me solar panel installation opportunities in Riverside") via a capture agent
- Pursuits calendar for vendors to track opportunities
- One-click proposal builder agent based on the Shipley proposal process

**Market:** GovCon / Government Contracting Intelligence + AI Proposal Automation

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Database | Supabase PostgreSQL (free tier) |
| Scheduler | GitHub Actions (cron daily 3 AM UTC) |
| Crawler | requests + BeautifulSoup + feedparser (Playwright installed but not yet used heavily) |
| AI | Claude API (model: `claude-opus-4-7`) |
| Email | Resend (free tier, 100 emails/day) |
| CLI | Click + Rich (currently unusable on user's network — see below) |

## Critical Environment Info

| Item | Value |
|------|-------|
| Local repo path | `D:\Claude Projects - 2026\my-tracker` |
| GitHub repo | `github.com/farrukhj91/pm-competitive-research-tracker` |
| Supabase URL | `https://hisatqlrtjxrjdozvtmz.supabase.co` |
| Supabase Project ID | `hisatqlrtjxrjdozvtmz` |
| Sender email | `onboarding@resend.dev` (Resend sandbox) |
| Recipient email | `farrukh.jamal91@gmail.com` (must match Resend signup) |
| First business name | "Lead Pursuits" |
| First business ID | `dab1adda-161b-45f7-8d75-00675073b737` |

## Critical Decisions (DO NOT FORGET)

1. **Network restrictions on user's laptop**: The user's company laptop blocks Supabase/Claude API/Resend connections. **Python cannot be run locally.** All development happens by editing files locally → committing → pushing → triggering workflow on GitHub Actions.

2. **Use LEGACY anon key**, not the new publishable key (`sb_publishable_...`). The Python supabase==2.0.2 library only works with the JWT-format legacy `anon public` key (starts with `eyJhbGc...`). Get it from Supabase → Settings → API Keys → "Legacy anon, service_role API keys" tab.

3. **RLS is DISABLED** on all tables. The user's anon key needs read/write access without policies. If new tables are created, run:
   ```sql
   ALTER TABLE <table_name> DISABLE ROW LEVEL SECURITY;
   ```

4. **GitHub Actions secrets** (5 secrets, all set):
   - `SUPABASE_URL`, `SUPABASE_KEY` (legacy anon), `CLAUDE_API_KEY`, `RESEND_API_KEY`, `SENDER_EMAIL`

5. **Resend sandbox limitation**: `onboarding@resend.dev` only delivers to the email used to sign up at Resend. To send to other emails, the user must verify a domain in Resend.

6. **GitHub Actions versions**: Use `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`. v3 is deprecated.

7. **Don't include `postgrest-py` in requirements.txt** — it's bundled with `supabase`, and pinning fails.

## Architecture

```
GitHub Actions (3 AM UTC daily)
  ↓ runs: python -m src.scheduler --all
  ↓
src/scheduler.py (orchestrator)
  ↓
  ├─ src/db.py (Supabase client)
  ├─ src/crawler.py (homepage → discover nav links → crawl pricing/features/blog/jobs)
  ├─ src/diff.py (compare crawls, generate structured diffs)
  ├─ src/report_generator.py (HTML email reports)
  │   ├─ FIRST CRAWL → comprehensive analysis (SWOT, comparison matrix, recommendations) via Claude
  │   └─ SUBSEQUENT → change-tracking report
  └─ src/email_sender.py (Resend API)
```

## Database Schema (Supabase)

| Table | Purpose |
|-------|---------|
| `businesses` | User's business(es) being tracked |
| `competitors` | Competitors per business |
| `crawl_results` | Raw crawl data (sources JSONB) per competitor |
| `crawl_diffs` | Structured changes between crawls |
| `reports` | Generated HTML reports (full + summary) |

## File Map

| File | What It Does |
|------|--------------|
| `src/config.py` | Loads env vars from .env |
| `src/db.py` | Supabase client + CRUD operations |
| `src/competitors.py` | Claude-based competitor identification (used by CLI only, not GitHub Actions) |
| `src/crawler.py` | Multi-source crawler with smart nav link discovery |
| `src/diff.py` | Compares crawl results, generates structured diffs |
| `src/report_generator.py` | Generates HTML reports — has TWO modes: initial deep-dive (SWOT etc.) vs change tracking |
| `src/email_sender.py` | Sends HTML emails via Resend API |
| `src/scheduler.py` | Orchestrator — main entry point for GitHub Actions |
| `src/cli.py` | Click-based CLI (currently unusable due to network restrictions) |
| `.github/workflows/daily_crawl.yml` | GitHub Actions schedule + workflow |
| `main.py` | CLI entry point |
| `requirements.txt` | Python dependencies |

## How To Make Changes (User's Workflow)

Since user can't run Python locally, all changes go through GitHub Actions:

```powershell
cd "D:\Claude Projects - 2026\my-tracker"
# Edit files locally (or have Claude edit them)
git add <files>
git commit -m "..."
git push
# Then go to GitHub → Actions → "Daily Competitive Research Crawl" → "Run workflow"
```

To reset crawl data (force comprehensive initial analysis on next run):
```sql
DELETE FROM crawl_diffs;
DELETE FROM reports;
DELETE FROM crawl_results;
```

## Current Competitors (Lead Pursuits)

1. GovWin IQ (Deltek) — `https://iq.govwin.com`
2. HigherGov — `https://www.highergov.com`
3. GovTribe — `https://govtribe.com`
4. Bloomberg Government — `https://about.bgov.com` (returns 403 — blocked)
5. BidNet Direct — `https://www.bidnetdirect.com`
6. GovDirections — `https://www.govdirections.com`
7. Responsive (formerly RFPIO) — `https://www.responsive.io`
8. Loopio — `https://www.loopio.com`

## Crawler Behavior

- **Strategy:** Fetch homepage → parse nav links → discover real URLs for pricing/features/blog/jobs → fall back to URL guessing if discovery fails
- **Respects:** Polite 2-sec delays between requests; retries 3x with exponential backoff (skips 404s immediately)
- **What it captures per competitor:** homepage messaging, pricing tiers, features list, blog posts (RSS preferred), job listings
- **Known limitations:**
  - Some sites block bots (Bloomberg Government returns 403)
  - JavaScript-heavy SPAs may return empty HTML (Playwright is installed but not yet integrated)
  - News crawling is a placeholder (no API integrated)
  - LinkedIn and review sites (G2, Capterra) not yet implemented

## Report Generator Logic

**First crawl detection:** If ALL diffs have `is_first_crawl: true`, generate comprehensive initial analysis.

**Initial report includes:**
- Executive overview (market narrative)
- Market positioning (size signals, competitive intensity, key battlegrounds)
- Comparison matrix (value prop, pricing, target market, differentiators, hiring signals)
- SWOT analysis per competitor
- Market gaps for Lead Pursuits to capture
- 5-7 strategic recommendations with priority + rationale

**Change-tracking report:**
- Competitor overview table
- Change log per competitor
- Executive summary with key insights
- "What This Means" + 2-3 recommended actions

## Roadmap

**See `ROADMAP.md` for detailed feature specs.** Quick summary of active priorities:

- **#1** — Better crawling (Playwright + News API + LinkedIn)
- **#2** — Web Dashboard (Next.js + Vercel + Supabase Auth)
- **#3** — Multi-business support with onboarding workflow

Lower priority (Phase 3+): smarter analysis (#4), custom domain & monetization (#5), Slack notifications (#6).

Minor known gaps:
- Email only reaches Resend signup address until custom domain is verified
- G2/Capterra/Trustpilot/Crunchbase not yet integrated
- Diff engine is text-based (not semantic) — see #4 for upgrade plan

## Cost (Monthly)

| Service | Free Tier | Actual Cost |
|---------|-----------|-------------|
| Supabase | 500MB | $0 |
| Claude API | Pay-as-you-go | ~$1-3 |
| Resend | 100/day | $0 |
| GitHub Actions | 2000 min/mo | $0 |
| **Total** | | **~$1-3/month** |

## Quick Reference: Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Invalid API key` (Supabase) | Use LEGACY anon key from "Legacy" tab |
| `getaddrinfo failed` locally | User's company firewall — must use GitHub Actions |
| `Running crawls for 0 businesses` | RLS is enabled — run `DISABLE ROW LEVEL SECURITY` SQL |
| Empty analysis / fallback text | Claude API credits depleted — top up at console.anthropic.com |
| Crawler 404 spam | Check if competitor URL is correct; some sites genuinely don't have `/pricing` etc. |
| Email not received | Resend sandbox only sends to signup email; verify a domain to expand |
| GitHub Actions deprecation warning | Update `actions/*` to latest major version |

## How To Hand Off To A Fresh Claude Session

1. User starts new session in `D:\Claude Projects - 2026\my-tracker`
2. This CLAUDE.md auto-loads
3. User says what they want to work on (e.g., "Add LinkedIn tracking")
4. Claude has full context — no need to re-explain anything

---

**Last updated:** 2026-05-11 (current session)
