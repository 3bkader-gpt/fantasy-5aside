# 🚀 SaaS Transformation Plan — Fantasy 5-a-Side

## Current State — What We Already Have

> **Note:** The architecture is already close to SaaS. The work required is adding the **business layer and guardrails**, not rebuilding from scratch.

| Already Done ✅ | Still Missing ❌ |
|----------------|-----------------|
| Multi-tenant DB (`league_id` on every table) | Email / User accounts |
| Self-signup (`/create-league`) | Plan limits & Billing |
| Per-league JWT auth | Super-admin dashboard |
| Slug-based routing `/l/{slug}` | Proper marketing landing page |

---

## Phase 1 — Harden Multi-Tenancy

**Goal:** Confirm zero cross-league data leakage before opening to the public.

**Checklist:**
- [ ] Audit every query in `db_repository.py` — ensure all are filtered by `league_id`
- [ ] Audit all admin routes — ensure edit/delete operations cannot touch other leagues
- [ ] Improve the `create-league` form:
  - Add `Admin Email` (required, for future account linking)
  - Auto-suggest the slug from the league name
  - Real-time slug availability check (AJAX)
- [ ] Add a Confirmation page after league creation (shows `/l/{slug}` link + next steps)

**Files to change:**

| File | Change |
|------|--------|
| `app/repositories/db_repository.py` | Review + hardening |
| `app/templates/landing.html` | Improved create-league form |
| `app/routers/public.py` | Confirmation redirect |

---

## Phase 2 — User Accounts & Authentication

**Goal:** Every league has a real owner with email + password, independent of the admin PIN.

### DB Changes

**New table: `users`**
```sql
id, email (unique), hashed_password, role (owner/superadmin), created_at
```

**Modify `leagues` table:**
```python
owner_user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
owner_email        = Column(String, nullable=True, index=True)   # interim field
is_verified        = Column(Boolean, default=False)
verification_token = Column(String, nullable=True)
```

### New Auth Flow
```
POST /auth/register  → create User + send verification email
POST /auth/login     → return JWT token (replaces password-only login)
GET  /dashboard      → show all leagues owned by this user
GET  /verify/{token} → mark is_verified = True
```

> **Warning:** Keep the current `admin_password` as a backward-compatible PIN. Do not remove it suddenly — migrate gradually.

### New Files

| File | Purpose |
|------|---------|
| `app/models/user_model.py` | User ORM model |
| `app/routers/accounts.py` | register / login / dashboard routes |
| `app/services/email_service.py` | Verification emails via Resend API |
| `app/templates/dashboard.html` | Multi-league dashboard |
| `app/templates/auth/register.html` | Registration page |

---

## Phase 3 — Plans & Usage Limits

**Goal:** Define Freemium model with enforced limits — even before real billing is live.

### Pricing Tiers

| Feature | Free | Pro (~€5/mo) | Unlimited (~€15/mo) |
|---------|:----:|:------------:|:-------------------:|
| Leagues | 1 | ∞ | ∞ |
| Players per league | 15 | 30 | ∞ |
| Matches per month | 20 | ∞ | ∞ |
| Saved seasons | 3 | 12 | ∞ |
| CSV Export | ❌ | ✅ | ✅ |
| Custom Branding | ❌ | ❌ | ✅ |
| Priority Support | ❌ | ✅ | ✅ |

### Technical Changes

**New file: `app/services/plan_limits.py`**
```python
PLAN_LIMITS = {
    "free":      {"max_leagues": 1, "max_players": 15, "max_matches_per_month": 20},
    "pro":       {"max_leagues": 999, "max_players": 30, "max_matches_per_month": 999},
    "unlimited": {"max_leagues": 999, "max_players": 999, "max_matches_per_month": 999},
}

def check_can_add_player(user, league) -> bool: ...
def check_can_create_league(user) -> bool: ...
```

**Modify `users` model:**
```python
plan            = Column(String(20), default="free")  # free / pro / unlimited
plan_expires_at = Column(DateTime, nullable=True)
```

**Modify admin routes:**
- Check limits before adding a player or starting a new match
- Show a banner: *"You've used 80% of your monthly limit — Upgrade to Pro"*

---

## Phase 4 — Billing & Subscriptions

### Payment Gateway Options

| Provider | Pros | Best For |
|----------|------|---------|
| **Stripe** | Most popular, flexible, great docs | Global, scalable |
| **Paddle** | Auto-handles VAT/taxes | SaaS-first |
| **Paymob** | Egyptian cards + Vodafone Cash | Arabic market |

**Recommendation:** Start with **Stripe** (widely recognized, easy to demo). Add Paymob later for the Arab market.

### New Files

| File | Purpose |
|------|---------|
| `app/routers/billing.py` | `/billing/upgrade`, `/billing/webhook`, `/billing/portal` |
| `app/templates/billing.html` | Pricing page + Upgrade CTA |

### Webhook Logic
```
payment_succeeded   → update plan + plan_expires_at
subscription_ended  → downgrade to "free"
```

---

## Phase 5 — Multi-League Dashboard & Onboarding

### `/dashboard` Page (post-login)
- Cards for each league: name, slug, player count, last match date
- "Create New League" button
- Current plan badge + upgrade prompt

### Onboarding Wizard (first-time users)
```
Step 1 → League name + slug
Step 2 → Team names + colors (Team A / Team B)
Step 3 → Bulk-add players (comma-separated names)
Step 4 → Done! Share your league link
```

### Files

| File | Purpose |
|------|---------|
| `app/templates/dashboard.html` | User dashboard |
| `app/templates/onboarding.html` | Setup wizard |
| `app/routers/accounts.py` | Dashboard routes |

---

## Phase 6 — Security, Monitoring & Ops

### Rate Limiting (`slowapi` middleware)
| Endpoint | Limit |
|----------|-------|
| `POST /create-league` | 3 leagues / IP / day |
| Public APIs | 60 req / min |
| Voting API | Already protected (fingerprint) |

### Logging & Monitoring
- Improve structured logging for: league creation, match recording, cup resolution
- Integrate **Sentry** (free hobby tier) for error tracking

### Backups
- JSON export per league — already exists as a feature
- Add Supabase scheduled backups for the full database

### Super-Admin Dashboard
- Protected by `SUPERADMIN_SECRET` env variable
- Shows: all leagues, owners, plans, activity stats
- Actions: suspend / delete any league

---

## Phase 7 — Marketing & Branding

### New Landing Page
- **Hero:** *"Create your 5-a-side Fantasy League in 2 minutes"*
- **Features section:** highlight the 14 features already built
- **Screenshots** from the live league
- **Demo League:** `/l/demo` — read-only pre-seeded league
- **Pricing table:** Free / Pro / Unlimited

### Demo Mode
- Pre-seeded data in `/l/demo`
- "Try Demo" button on the landing page

### Branding
- Logo + consistent color palette
- Short tagline: e.g. *"Fantasy Football, your way."*
- OG meta tags for social sharing

---

## Phase 8 — Prioritized Execution Roadmap

```
1️⃣  Harden multi-tenancy      → Phase 1  (query audit + isolation)
2️⃣  User accounts + login     → Phase 2  (User model + JWT + email)
3️⃣  Multi-league dashboard    → Phase 5  (Dashboard + Onboarding)
4️⃣  Free/Pro limits logic     → Phase 3  (without real billing first)
5️⃣  Stripe integration        → Phase 4  (Billing + Webhooks)
6️⃣  Landing page + Demo       → Phase 7  (Marketing)
7️⃣  Observability + Ops       → Phase 6  (Rate limiting + Sentry)
```

---

## Additional Tech Stack

| Tool | Purpose | Cost |
|------|---------|------|
| **Resend** | Email service | Free up to 3K/month |
| **Stripe** | Billing | % of revenue |
| **slowapi** | Rate limiting | Free (FastAPI middleware) |
| **Sentry** | Error tracking | Free (hobby tier) |
| **Supabase** | Database (already in use) | Already paid |

---

> **Important:** Start with **Phase 1 + Phase 2 only**, deploy, and get real user feedback before building billing. This saves weeks of work on features that might need to change.

> **Tip:** Keep the current `admin_password` as a backward-compatible PIN while gradually rolling out User accounts on top of it.
