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

### #2 — Web Dashboard & SaaS Foundation (React UI + Pricing)

**Goal:** Replace SQL-based management with a production SaaS web app. Support free signups + paid tiers, laying groundwork for Slack notifications (#6) and API integrations (#5).

#### Business Model & Pricing

**Cost Analysis (per active business per month):**
- Supabase database: $0.05 (shared storage/API)
- Claude API for initial analysis: $0.50 (one-time per business)
- Claude API for daily diffs: $0.15 (daily crawl with lightweight analysis)
- Resend email: $0.00 (free tier 100/day)
- GitHub Actions: $0.00 (free tier includes 2000 min/month; 10 min/crawl = 300 min/month)
- Vercel: $0.00 (free tier, generous bandwidth)
- **Total cost per active business:** ~$0.70/month (highly favorable unit economics)

**Recommended Tier Structure:**

| Tier | Price | Businesses | Key Features | Target Users |
|------|-------|-----------|--------------|--------------|
| **Free** | $0 | 1 | Daily crawls, email reports, manual triggers | Solo users, evaluators |
| **Pro** | $29.99/mo | Unlimited | ☝️ + Slack notifications, webhooks, API, priority crawls | SMB competitive analysts |
| **Enterprise** | Custom | Unlimited | ☝️ + SSO, team seats, SLA, dedicated support | Large orgs, agencies |

**Rationale:**
- Free tier acquires users and validates product-market fit
- Pro at $29.99 is **40% cheaper than Semrush competitive intelligence** ($99/mo) and **25% cheaper than Kompyte** ($39/mo) — strong positioning
- Unit economics are favorable even at $29.99 (30x cost coverage after infrastructure)
- Slack notifications + webhooks are Pro features; this justifies the price point
- Enterprise tier opens door to high-revenue customers (agencies, large enterprises willing to pay $100-500/mo)

**Billing & Auth:**
- Use Stripe for subscriptions (integration in Phase 3.5)
- Supabase Auth handles user registration + password reset
- Each user has their own account and businesses

#### Tech Stack

- **Framework:** Next.js 14 (App Router) — single deployment for frontend + API routes
- **Hosting:** Vercel (free tier sufficient for MVP, auto-scales)
- **Auth:** Supabase Auth (email magic link + password) — free, no extra cost
- **Database:** Existing Supabase (no new instance needed)
- **Styling:** Tailwind CSS + shadcn/ui (professional, consistent UI)
- **Notifications:** SendGrid (email templates) + Slack SDK (scheduled for #6)
- **Payments:** Stripe (Phase 3.5)

#### Repo Structure

Create a SEPARATE repo `competitive-tracker-web` (Next.js full-stack app):
```
competitive-tracker-web/
├── app/                           # Next.js App Router
│   ├── (auth)/                    # Auth pages (layout group)
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── confirm/page.tsx       # Email confirmation
│   ├── (dashboard)/               # Protected dashboard routes (layout group)
│   │   ├── dashboard/page.tsx     # Businesses list
│   │   ├── businesses/[id]/page.tsx    # Single business view
│   │   ├── businesses/[id]/competitors/page.tsx
│   │   ├── businesses/[id]/reports/[reportId]/page.tsx
│   │   ├── settings/page.tsx      # User settings + billing
│   │   └── layout.tsx             # Dashboard layout with sidebar
│   ├── api/                       # API routes
│   │   ├── auth/
│   │   │   ├── signup/route.ts
│   │   │   ├── login/route.ts
│   │   │   └── logout/route.ts
│   │   ├── businesses/
│   │   │   ├── route.ts           # GET (list), POST (create)
│   │   │   └── [id]/
│   │   │       ├── route.ts       # GET (single)
│   │   │       ├── crawl/route.ts # POST (trigger GitHub Actions)
│   │   │       ├── crawl-status/route.ts # GET (polling for progress)
│   │   │       └── research/route.ts # POST (Claude competitor research, #3)
│   │   ├── competitors/route.ts   # POST (add/edit/remove)
│   │   └── reports/[id]/route.ts  # GET (fetch HTML)
│   ├── page.tsx                   # Landing page (public)
│   └── layout.tsx                 # Root layout
├── components/
│   ├── auth/
│   │   ├── SignupForm.tsx
│   │   └── LoginForm.tsx
│   ├── dashboard/
│   │   ├── BusinessCard.tsx
│   │   ├── CompetitorRow.tsx
│   │   ├── ReportViewer.tsx       # HTML sanitizer + renderer
│   │   ├── ReportTimeline.tsx
│   │   ├── CrawlProgressModal.tsx # Live polling with progress bar
│   │   └── BusinessSelector.tsx
│   ├── modals/
│   │   ├── AddCompetitorModal.tsx
│   │   ├── EditCompetitorModal.tsx
│   │   └── ConfirmDeleteModal.tsx
│   └── common/
│       ├── LoadingState.tsx
│       ├── EmptyState.tsx
│       └── Nav.tsx
├── lib/
│   ├── supabase.ts               # Supabase client initialization
│   ├── auth.ts                   # Auth helpers
│   ├── api.ts                    # API request utilities
│   └── github.ts                 # GitHub Actions trigger
├── middleware.ts                  # Auth middleware (protect /dashboard)
├── .env.local                     # Environment variables
└── package.json
```

**Existing Python repo structure (no changes needed):**
```
pm-competitive-research-tracker/
├── src/
│   ├── crawler.py
│   ├── scheduler.py               # UPDATE: accept --business-id parameter
│   ├── report_generator.py
│   ├── diff.py
│   ├── email_sender.py
│   └── ...
├── .github/workflows/
│   └── daily_crawl.yml            # UPDATE: accept inputs.business_id
└── ...
```

#### Database Schema Changes

Add to Supabase (enables multi-user support):

```sql
-- Add user tracking to businesses (auth.users.id from Supabase Auth)
ALTER TABLE businesses 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add pricing tier tracking
ALTER TABLE businesses 
ADD COLUMN IF NOT EXISTS tier VARCHAR(50) DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise'));

-- Track subscription info
CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  stripe_subscription_id VARCHAR(255),
  tier VARCHAR(50) NOT NULL,
  status VARCHAR(50) NOT NULL, -- 'active', 'canceled', 'past_due'
  current_period_start TIMESTAMP,
  current_period_end TIMESTAMP,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Track email/Slack notification settings per business
ALTER TABLE businesses 
ADD COLUMN IF NOT EXISTS notifications_email BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS notifications_slack BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS slack_webhook_url VARCHAR(2048);

-- Note: Don't enable RLS yet — Phase 3 adds auth enforcement
-- For Phase 2: RLS stays disabled; filter queries by user_id in API routes
```

#### Pages & Features

**Authentication Pages** (new user flow):
- `/login` — Email + password
- `/signup` — Register + email verification
- `/confirm?email=...&token=...` — Verify email link

**Dashboard Pages** (authenticated users only):
- `/dashboard` — Businesses list (cards showing competitor count, last report date)
  - Empty state: "Add your first business" CTA
  - "+ Add Business" button
- `/businesses/[id]` — Single business view
  - Tabs: Overview | Competitors | Reports | Settings
  - Overview: Recent report summary, key metrics, "Trigger Manual Crawl" button
  - Competitors: Table with pause/resume/remove actions
  - Reports: Timeline of past reports with links
  - Settings: Email notifications, Slack connection (Pro only), pause business
- `/businesses/[id]/competitors` — Competitor management page
  - Full table view, "+ Add Competitor" button (modal)
- `/businesses/[id]/reports/[reportId]` — Full report viewer
  - Renders stored HTML (sanitized)
  - Downloadable as PDF (future enhancement)
- `/settings` — User account
  - Email + password management
  - Billing info (Pro/Enterprise users)
  - Connected integrations (Slack, webhooks)
  - Delete account option

**Landing Page** (`/`):
- Hero section: "Track your competitors in real time"
- Feature list: Crawls 8-12 competitors daily, AI insights, Slack notifications
- Pricing table (public)
- Social proof: "Used by X teams" (placeholder for now)
- CTA: "Get Started Free"

#### Components

**Reusable UI Components:**
1. `BusinessCard.tsx` — Summary card (name, # competitors, last report date, "View" button)
2. `CompetitorRow.tsx` — Table row (name, URL, LinkedIn URL, status, pause/resume/remove/edit buttons)
3. `ReportViewer.tsx` — Renders `full_report_html` with XSS sanitization (use `DOMPurify`)
4. `ReportTimeline.tsx` — List of past reports sorted by date DESC, with links
5. `CrawlProgressModal.tsx` — Modal showing live crawl progress (polls `/api/businesses/[id]/crawl-status` every 2-3 sec, shows progress bar + current competitor)
6. `AddCompetitorModal.tsx` — Form to manually add competitor (name, URL, LinkedIn URL)
7. `EditCompetitorModal.tsx` — Edit competitor details
8. `ConfirmDeleteModal.tsx` — Generic confirmation dialog
9. `BusinessSelector.tsx` — Dropdown in header to switch between user's businesses
10. `LoadingState.tsx` — Skeleton loaders (Tailwind + shadcn Skeleton)
11. `EmptyState.tsx` — Reusable empty state with CTA

#### API Routes (Next.js + TypeScript)

**Auth Routes:**
- `POST /api/auth/signup` — Create user + Supabase auth account
  - Body: `{ email, password }`
  - Return: `{ user: { id, email }, session_token }`
- `POST /api/auth/login` — Sign in
  - Body: `{ email, password }`
  - Return: session token
- `POST /api/auth/logout` — Sign out (clear cookie/session)

**Business Routes:**
- `GET /api/businesses` — List user's businesses
  - Query: `?limit=10&offset=0` (pagination)
  - Return: `[{ id, name, url, tier, competitor_count, last_report_date }, ...]`
  - Auth: Required (filters by `user_id`)
- `POST /api/businesses` — Create new business
  - Body: `{ name, url, description, tier: 'free' | 'pro' | 'enterprise' }`
  - Validation: Free tier can only have 1 business; Pro can have unlimited
  - Return: `{ id, name, url, tier, created_at }`
  - Auth: Required
- `GET /api/businesses/[id]` — Get single business + competitors + last report
  - Return: `{ business: {...}, competitors: [...], last_report: {...} }`
  - Auth: Required
- `POST /api/businesses/[id]/crawl` — Trigger manual crawl via GitHub Actions
  - Calls: `POST https://api.github.com/repos/farrukhj91/pm-competitive-research-tracker/actions/workflows/daily_crawl.yml/dispatches`
  - Headers: `Authorization: Bearer <GITHUB_PAT>`, `Accept: application/vnd.github+json`
  - Body: `{ ref: "main", inputs: { business_id: id } }`
  - Return: `{ status: "queued", message: "Crawl started for 8 competitors..." }`
  - Auth: Required
- `GET /api/businesses/[id]/crawl-status` — Poll crawl progress
  - Return: 
    ```json
    {
      "status": "queued" | "crawling" | "completed" | "failed",
      "started_at": "2026-05-14T10:00:00Z",
      "completed_at": null,
      "crawled_competitors": 3,
      "total_competitors": 8,
      "message": "Crawling TechCorp (3/8)...",
      "progress_percent": 37.5
    }
    ```
  - Implementation: Query `crawl_results` table for this business, count status="success"
  - Auth: Required

**Competitor Routes:**
- `POST /api/competitors` — Add/edit/remove competitor
  - Body: `{ business_id, action: "add" | "edit" | "remove", name?, url?, linkedin_url? }`
  - Return: `{ success: true, competitor: {...} }`
  - Auth: Required

**Report Routes:**
- `GET /api/reports/[id]` — Fetch report HTML
  - Return: `{ id, report_date, summary_html, full_report_html }`
  - Auth: Required
- `GET /api/reports?business_id=...&limit=10` — List reports for business
  - Return: `[{ id, report_date, ... }, ...]` (for timeline view)
  - Auth: Required

**Placeholder for Phase 3:**
- `POST /api/businesses/[id]/research` — Kick off Claude competitor discovery
  - (Not implemented in Phase 2; stub with 501 Not Implemented)

#### Crawl Triggering & Progress Polling

**Why GitHub Actions?**
- Free (2000 min/month = 200 daily crawls @ 10 min each)
- Reliable, proven, decoupled from dashboard
- Easy to monitor and debug
- Can scale to multi-tenant without cost

**Workflow:**
1. User clicks "Trigger Manual Crawl" in dashboard
2. Frontend calls `POST /api/businesses/[id]/crawl`
3. API calls GitHub workflow_dispatch with `business_id` parameter
4. Python scheduler runs: `python -m src.scheduler --business-id <id>`
5. Frontend polls `GET /api/businesses/[id]/crawl-status` every 2-3 sec
6. Progress modal shows: "Crawling TechCorp (3/8)..." + progress bar
7. When complete: "✅ Crawl finished. 3 new changes detected in pricing."

**Python Scheduler Updates:**
- `scheduler.py` must accept `--business-id` parameter
- Usage: `python -m src.scheduler --business-id dab1adda-...` crawls only that business
- Existing `--all` remains unchanged (for scheduled daily runs)

**GitHub Actions Workflow Update:**
```yaml
on:
  workflow_dispatch:
    inputs:
      business_id:
        description: 'Optional business ID to crawl (leave empty for all)'
        required: false
        type: string

jobs:
  crawl:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        ...
      - name: Run crawl
        run: |
          if [ -z "${{ github.event.inputs.business_id }}" ]; then
            python -m src.scheduler --all
          else
            python -m src.scheduler --business-id ${{ github.event.inputs.business_id }}
          fi
```

#### Acceptance Criteria

1. ✅ User can sign up with email, verify email, log in
2. ✅ Free tier limited to 1 business; Pro/Enterprise show unlimited
3. ✅ Dashboard shows list of user's businesses with card summaries
4. ✅ Single business view shows competitors, recent report, settings
5. ✅ User can manually add competitors (with name, URL, optional LinkedIn URL)
6. ✅ User can pause/resume/remove competitors
7. ✅ User can view past reports (rendered HTML, XSS-safe)
8. ✅ User can trigger manual crawl, see live progress with polling
9. ✅ All pages mobile-responsive (Tailwind + shadcn/ui)
10. ✅ Deployed live on Vercel at public URL
11. ✅ Email notifications work for free/pro tiers
12. ✅ Pro tier can connect Slack webhook (Phase 2 scaffolding; Phase 3.5 full integration)

#### Implementation Timeline

**Phase 2 Detailed (14-18 hours across 2-3 sessions):**

1. **Session 1: Scaffolding & Auth (5-6 hours)**
   - Initialize Next.js 14 repo (`competitive-tracker-web`)
   - Set up Supabase Auth (email + password)
   - Build signup/login/logout pages + middleware
   - Set up environment variables
   - Create landing page with pricing table
   - Initial GitHub commit + Vercel deployment

2. **Session 2: Dashboard Pages & Components (6-8 hours)**
   - Build business list page + BusinessCard component
   - Build single business view (tabs: Overview | Competitors | Reports | Settings)
   - Build competitor management page + CompetitorRow component
   - Build report viewer page + ReportViewer component (HTML sanitization)
   - Create all modals (AddCompetitorModal, ConfirmDeleteModal, etc.)
   - Build CrawlProgressModal with polling logic
   - Responsive design (mobile + desktop)

3. **Session 3: API Routes & Integration (4-6 hours)**
   - Implement all API routes (auth, businesses, competitors, reports, crawl-status)
   - Implement GitHub Actions workflow_dispatch integration
   - Add crawl progress polling + status tracking
   - Database schema migration (add user_id, tier, subscriptions table)
   - Update Python scheduler to accept --business-id
   - End-to-end testing on Vercel
   - Polish + deploy

**Estimated total:** 14-18 hours (but can flex based on complexity discovered during implementation)

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
