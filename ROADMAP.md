# ROADMAP — Competitive Research Tracker

> Detailed specs for upcoming features. Phase 1 MVP (daily crawler + email reports) is **deployed and working**. This document describes what comes next.

**Priority order:** 1 → 2 → 3 → (then 4, 5, 6 as separate phases)

---

## Core Principles (read before working on any feature)

These principles govern the system's design. Any code or doc change that contradicts them is a bug.

1. **Multi-tenant by design.** The system supports many users, each tracking one or more businesses. There is no canonical user, no canonical business, and no canonical competitor list. The current Lead Pursuits setup in Supabase is **seed data for development**, not a fixture.

2. **Competitors are discovered dynamically per business — never hardcoded.**
   - User inputs business name + URL + description.
   - Claude performs deep research and returns 8–12 candidate competitors with confidence scores and overlap reasoning.
   - User selects which ones to track (default: top N pre-checked, but user can add/remove).
   - Selected competitors are written to the Supabase `competitors` table for that business.
   - From there, the daily crawler operates on whatever rows exist for each business.
   - **No code path, no doc, no test fixture, and no example should assume a specific competitor by name.** The full onboarding flow is specified in `#3` below.

3. **Per-business isolation.** A user's businesses, competitors, crawl data, and reports belong only to them. When auth/RLS lands (`#3`), policies must enforce this at the DB level.

4. **Crawler and analysis logic must be competitor-agnostic.** Detection heuristics (e.g., the JS-heavy fallback in `#1A`) operate on HTML structure, not on domain allowlists. AI analysis prompts reference competitors by variable, not by name.

5. **Documentation discipline.** When an example competitor is needed for clarity, frame it as *"e.g., for one of the current Lead Pursuits competitors"* or use a placeholder like `{competitor_name}` — never as a canonical case.

---

## Phase 2 — Priority Features (Active)

### #1 — Better Crawling (Playwright + News API + LinkedIn)

**Goal:** Capture more reliable, richer competitor data so AI analysis quality improves.

#### 1A. Playwright for JS-heavy sites
**Problem:** Modern SPAs (any JavaScript-heavy site) render content client-side. The default `requests + BeautifulSoup` approach gets empty/incomplete HTML on these sites. This problem is competitor-agnostic — it depends on the site's tech stack, not on which business is being tracked.

**Solution:**
- Add Playwright (already installed) to render JS before parsing
- Detect when a page is JS-heavy:
  - Body text is suspiciously short (< 200 chars)
  - Many `<script>` tags relative to content
  - Falls back to Playwright if static fetch returns thin content
- Use `chromium` headless, with realistic viewport and user-agent
- Wait for network idle before scraping
- Performance: only use Playwright when static fails (it's slower)

**Files to change:**
- `src/crawler.py` — add `_render_with_playwright()` method
- `requirements.txt` — already has playwright
- `.github/workflows/daily_crawl.yml` — already installs chromium

**Acceptance:**
- Any JS-heavy competitor site (for any business) now returns features/pricing content
- No more empty `"features": []` in crawl_results when the source HTML is server-rendered thin
- Crawl time per competitor doesn't exceed 60 seconds
- Detection logic is generic — driven by HTML heuristics, not by hardcoded domain lists

---

#### 1B. News API Integration
**Problem:** Currently, news crawling is a placeholder. We need real news mentions per competitor.

**Solution:**
- Use **NewsAPI.org** free tier (100 requests/day) OR **Google News RSS** (free, no key)
- For each competitor name, search for mentions in the last 24 hours
- Capture: headline, source, publication date, URL, snippet
- Store in `crawl_results.sources.news.articles[]`

**Choice:** Start with Google News RSS (no key, no rate limit concerns):
```
https://news.google.com/rss/search?q={competitor_name}&hl=en-US&gl=US&ceid=US:en
```

**Files to change:**
- `src/crawler.py` — implement real `_crawl_news()` method using feedparser
- `src/diff.py` — add news diff logic (new articles since last crawl)
- `src/report_generator.py` — include news in reports

**Acceptance:**
- Each competitor crawl includes 3-5 recent news articles (where available)
- Daily reports show new news mentions in the "Raw Highlights" section
- Major announcements (funding, acquisitions, leadership changes) get flagged

---

#### 1C. LinkedIn Company Data
**Problem:** Headcount/hiring signals are weak without LinkedIn data.

**Solution:** This is the hardest source because LinkedIn aggressively blocks scrapers. Options:
1. **Google search** for `site:linkedin.com/company/{name}` — extract employee count snippet from search results (free, fragile)
2. **Proxycurl API** — paid but reliable ($10 for 1000 lookups)
3. **Manual entry** — let user manually input LinkedIn URL + estimated headcount, refresh quarterly

**Recommended:** Start with option 1 (Google search scrape), document the failure case. If unreliable, prompt user to add LinkedIn URLs manually.

**Files to change:**
- `src/crawler.py` — add `_crawl_linkedin()` method
- Schema: add `linkedin_url` column to `competitors` table (nullable)

**Acceptance:**
- LinkedIn employee count captured for at least 60% of competitors
- Failures gracefully marked as `"status": "blocked"` (not crashes)

---

### #2 — Web Dashboard (React UI)

**Goal:** Replace SQL-based business management with a real web app. Foundation for the multi-business workflow (#3).

#### Tech Stack
- **Framework:** Next.js 14 (App Router) — combines frontend + API routes
- **Hosting:** Vercel (free tier, generous limits)
- **Auth:** Supabase Auth (email magic link)
- **Database:** Existing Supabase project
- **Styling:** Tailwind CSS + shadcn/ui components

#### Why Next.js?
- Single deployment (frontend + API in one repo/host)
- Vercel free tier is generous (100GB bandwidth/month)
- Easy to add custom domain later (#5)
- Server Components reduce client bundle
- API routes can trigger GitHub Actions workflows via dispatch

#### Repo Structure
Create a SEPARATE repo `competitive-tracker-web` (Next.js app) that talks to the existing Python crawler's Supabase DB. This keeps concerns clean:
- `pm-competitive-research-tracker` (existing) — Python crawler, scheduler
- `competitive-tracker-web` (new) — Next.js dashboard

#### Pages
- `/` — Landing/login (Supabase Auth)
- `/dashboard` — list of businesses being tracked
- `/dashboard/businesses/new` — onboarding wizard (#3)
- `/dashboard/businesses/[id]` — single business view: competitors list, recent reports, settings
- `/dashboard/businesses/[id]/reports/[reportId]` — view a specific report
- `/dashboard/businesses/[id]/competitors` — manage competitors (add/edit/remove/pause)
- `/dashboard/settings` — user settings, email preferences

#### Components
- BusinessCard
- CompetitorRow (with pause/edit/remove)
- ReportViewer (renders stored HTML)
- ReportTimeline (history)
- AddCompetitorModal
- ConfirmDeleteModal

#### API Routes (Next.js)
- `POST /api/businesses` — create new business
- `GET /api/businesses` — list user's businesses
- `POST /api/businesses/[id]/research` — kick off competitor research (calls Claude API)
- `POST /api/businesses/[id]/crawl` — trigger immediate crawl via GitHub workflow_dispatch API
- `POST /api/competitors` — add/edit/remove
- `GET /api/reports/[id]` — fetch report HTML

#### Triggering Crawls From the Dashboard
The crawler stays in GitHub Actions (free, reliable). Dashboard triggers manual runs via GitHub's `workflow_dispatch` REST API. Requires:
- Personal Access Token (PAT) stored as env var in Vercel
- API call: `POST https://api.github.com/repos/farrukhj91/pm-competitive-research-tracker/actions/workflows/daily_crawl.yml/dispatches`

#### Acceptance
- User can sign in with email magic link
- User can add a new business (triggers #3 workflow)
- User can see all competitors, pause/resume/remove them
- User can view past reports (stored HTML rendered inline)
- User can trigger a manual crawl from the UI
- Deployed to `competitive-tracker.vercel.app` (or similar)

---

### #3 — Multi-business support with onboarding workflow

**Goal:** Let users add multiple businesses, each with their own competitor tracking. The onboarding workflow is the killer feature — a guided experience that delivers a strong initial analysis.

#### User Flow

```
[Click "+ Add Business to Track"]
   ↓
Step 1: Tell us about your business
   - Business name
   - Website URL (optional)
   - Description (free text — what you do, who you serve)
   - Industry/category (dropdown)
   - [Continue]
   ↓
Step 2: Finding competitors... (loading state)
   - Claude API runs deep research
   - Returns list of 8-12 competitors with:
     - Name
     - URL
     - 2-3 sentence description of what they do
     - Why they're a competitor (positioning overlap)
     - Confidence score
   ↓
Step 3: Select your competitors
   - Checkboxes per competitor (default: top 8 checked)
   - User can deselect or add custom ones manually
   - [Start Analysis]
   ↓
Step 4: Performing deep analysis... (loading state, 3-5 minutes)
   - System crawls selected competitors
   - Generates comprehensive initial report (existing logic from Phase 1)
   - Sends email
   - Redirects to dashboard with the report visible
   ↓
[Dashboard shows new business with first report]
```

#### Components

**Step 1 form** — standard React form with validation

**Step 2: "Deep Research" Claude prompt**
This is the heart of the feature. The prompt should be sophisticated:
```
You are a senior strategy consultant at a top-tier firm. A client has just shared their business with you. Your job is to identify their most relevant competitors.

Business: {name}
URL: {url}
Description: {description}
Industry: {industry}

Use web search and your knowledge to identify 8-12 direct and adjacent competitors. For each, provide:
- Full company name
- Primary URL
- 2-3 sentence description of what they do
- Positioning overlap with the client (i.e., why they compete)
- Confidence score (0.0 to 1.0) — how directly they compete

Return ONLY valid JSON:
[
  {
    "name": "...",
    "url": "https://...",
    "description": "...",
    "overlap_reason": "...",
    "confidence": 0.95
  },
  ...
]

Sort by confidence descending. Include 6-8 direct competitors (high confidence) plus 2-4 adjacent ones (medium confidence) the client might not have considered.
```

**Step 4: Trigger crawl**
- Insert business + competitors into Supabase
- Call GitHub Actions workflow_dispatch with `business_id` parameter
- Poll Supabase for crawl_results status
- Show progress: "Crawling {competitor_name} (2/8)..."
- When done, show summary card + link to full report

#### Backend Changes

**Schema additions:**
```sql
ALTER TABLE businesses ADD COLUMN industry VARCHAR(255);
ALTER TABLE businesses ADD COLUMN user_id UUID REFERENCES auth.users(id);
ALTER TABLE businesses ADD COLUMN is_paused BOOLEAN DEFAULT false;

ALTER TABLE competitors ADD COLUMN description TEXT;
ALTER TABLE competitors ADD COLUMN overlap_reason TEXT;
ALTER TABLE competitors ADD COLUMN confidence_score NUMERIC(3,2);
ALTER TABLE competitors ADD COLUMN linkedin_url VARCHAR(2048);

-- Re-enable RLS now that we have auth
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors ENABLE ROW LEVEL SECURITY;
-- Add policies: users can only see their own businesses

CREATE POLICY "Users see own businesses" ON businesses
  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own competitors" ON competitors
  FOR ALL USING (business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid()));
-- (Similar policies for crawl_results, crawl_diffs, reports)
```

**Scheduler changes:**
- `src/scheduler.py` — accept optional `--business-id` parameter to crawl just one business
- Skip paused businesses (`is_paused = true`)

**New API endpoint:**
- `POST /api/businesses/[id]/research` — calls Claude for competitor research, returns list
- `POST /api/businesses/[id]/competitors/batch` — bulk insert selected competitors

#### Acceptance
- User can complete the full onboarding flow in under 10 minutes
- The "deep research" step returns 8-12 relevant competitors with good descriptions
- The initial analysis report matches the quality of the current Phase 1 output
- User can manage multiple businesses simultaneously
- Each business gets its own daily report
- RLS ensures users can only see their own data

---

## Implementation Order

**Suggested sequence:**

1. **#1A (Playwright)** — quick win, improves all downstream analysis. ~2-3 hours.
2. **#1B (News API)** — easy, free, high impact. ~1-2 hours.
3. **#1C (LinkedIn)** — try Google search approach, document limitations. ~2 hours.
4. **#2 — Web Dashboard scaffolding** — create Next.js repo, set up Supabase Auth, basic routing. ~4-6 hours.
5. **#2 — Dashboard pages** — businesses list, single business view, report viewer. ~6-8 hours.
6. **#3 — Onboarding workflow** — Step 1-4 wizard, deep research prompt, workflow_dispatch integration. ~8-10 hours.
7. **Schema migration** — add columns, enable RLS, write policies. ~2-3 hours.
8. **Polish + deploy** — Vercel deployment, custom domain stub, testing. ~2-3 hours.

**Total estimate:** ~25-35 hours of focused work

---

## Phase 3 — Future (Lower priority for now)

### #4 — Smarter Analysis
- **Sentiment tracking** of homepage messaging, blog content, reviews (positive/negative/neutral)
- **Positioning shifts** — detect when a competitor's tagline/messaging fundamentally changes
- **Pricing trend analysis** — track price changes over time, visualize trends
- **Feature velocity** — measure how often each competitor ships new features
- **Implementation:** Add `analysis` table for time-series metrics; use Claude for sentiment/positioning analysis on each crawl

### #5 — Custom Domain & Scaling
- Acquire domain (e.g., `farrukhj.com`)
- Configure DNS for Vercel deployment
- Set up custom branded sender email (e.g., `intel@farrukhj.com` via Resend with verified domain)
- Consider whitelabel option for paid users
- **Path to monetization:**
  - Free tier: 1 business, 5 competitors
  - Pro tier ($X/mo): unlimited businesses + competitors, daily reports, Slack notifications
  - Enterprise: custom domain, team access, API

### #6 — Slack Notifications
- Slack app + OAuth
- User connects Slack workspace per business
- Choose channel for notifications
- Send key changes to channel (e.g., "🚨 {competitor_name} raised prices 20%")
- Configurable thresholds (what counts as "important")
- Optional: full daily summary message
- **Files:** `src/slack_sender.py`, `.env` add `SLACK_BOT_TOKEN`

---

## Open Questions

- **Auth model:** Should Supabase Auth handle this, or do we want a custom solution? Recommend Supabase Auth for speed.
- **GitHub PAT for workflow_dispatch:** Where to store it securely? Vercel env var is fine for solo use; for multi-tenant, need per-user tokens or a single service account.
- **Crawl-on-demand vs scheduled:** Should the dashboard crawl trigger run in GitHub Actions (slower, free) or as a Vercel serverless function (faster, but 10-second timeout)? For onboarding, the GitHub Actions delay (~3-5 min) is fine if we show a good loading state.
- **Free tier limits:**
  - Vercel: 100GB bandwidth — plenty for solo use
  - Supabase: 500MB DB, 2GB egress — enough for 10-20 businesses
  - GitHub Actions: 2000 min/month free — at 10 min per crawl, that's 200 crawls/month (~6/day) — fine

---

## Notes For Future Sessions

- **#1A-C are mostly Python changes** — work in this repo
- **#2 and #3 require a new repo** (`competitive-tracker-web`) for the Next.js app
- **Schema changes for #3** affect the Python crawler — coordinate carefully
- **Phase 1 deployment is stable** — don't break the daily reports while building Phase 2

---

**Last updated:** 2026-05-11
