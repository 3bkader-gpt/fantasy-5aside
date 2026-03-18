# 🚀 SaaS Transformation Plan — Fantasy 5-a-Side

## Current State — What We Already Have

> **Note:** The architecture is already close to SaaS. The work required is adding the **business layer and guardrails**, not rebuilding from scratch.

| Already Done ✅ | Still Missing ❌ |
|----------------|-----------------|
| Multi-tenant DB (`league_id` on every table) | Email / User accounts |
| Self-signup (`/create-league`) | Plan limits & Billing |
| Per-league JWT auth | Super-admin dashboard |
| Slug-based routing `/l/{slug}` | Proper marketing landing page |
| CSRF protection (double-submit cookie) | Demo league (`/l/demo`) |
| Rate limiting (`slowapi`) | Paid subscriptions + webhooks |
| Security headers + CSP middleware | Multi-league dashboard (per user) |
| JWT revocation (`jti` + `revoked_tokens`) | Usage-limit enforcement (Free/Pro) |
| Exports: CSV stats + JSON backup per league | Email verification + password reset |
| PWA basics (manifest + `/sw.js`) | Sentry / centralized monitoring |
| Match media upload/delete endpoints | Scheduled DB backups / restore story |
| Web push subscription endpoints | |

### Overall SaaS Progress

- [x] Core multi-tenant fantasy engine (current repo)
- [x] Phase 1 – Harden multi-tenancy (league-scoped repos + admin flows + create-league UX)
- [ ] 🟡 Phase 2 – User accounts & email-based auth
- [ ] ❌ Phase 3 – Plans & usage limits (Free / Pro / Unlimited)
- [ ] ❌ Phase 4 – Billing & subscriptions (Stripe / others)
- [ ] 🟡 Phase 5 – Multi-league dashboard & onboarding
- [ ] 🟡 Phase 6 – Security, monitoring & ops hardening (good baseline exists; monitoring/ops still missing)
- [ ] 🟡 Phase 7 – Marketing site, branding & demo league (landing exists; proper marketing + demo missing)

---

## Phase 1 — Harden Multi-Tenancy

**Goal:** Confirm zero cross-league data leakage before opening to the public.

**Checklist:**
- [x] Audit every query in `db_repository.py` — league-scoped helpers added where needed
- [x] Audit all admin/voting/media routes — destructive operations now use league-scoped lookups
- [x] Improve the `create-league` form:
  - ✅ Capture `admin_email` (optional for now, stored on `leagues.admin_email`)
  - ✅ Auto-suggest the slug from the league name on the client
  - ✅ Real-time slug availability check via `/api/slug-available`
- [x] Add a confirmation page after league creation (`/l/{slug}/created` with share link + next steps)

**Files to change:**

| File | Change |
|------|--------|
| `app/repositories/db_repository.py` | Review + hardening |
| `app/templates/landing.html` | Improved create-league form |
| `app/routers/public.py` | Confirmation redirect |

---

## Phase 2 — User Accounts & Authentication

**Goal:** Every league has a real owner with email + password, independent of the admin PIN.

**Status:** 🟡 Partially implemented (user accounts, email verification, dashboard skeleton, and parallel auth flow are in place; linking flows and plan-based limits remain).

### DB Changes

**New table: `users` (implemented)**
```sql
id, email (unique), hashed_password, role (owner/superadmin), is_active, is_verified, verification_token, created_at, updated_at
```

**Modify `leagues` table (implemented):**
```python
owner_user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
is_verified        = Column(Boolean, default=False)
verification_token = Column(String, nullable=True)
```

### New Auth Flow (current status)
```
GET  /register        → show registration form
POST /register        → create User + send verification email
POST /user/login      → authenticate user account, set user_access_token cookie
GET  /forgot-password → show password reset request form
POST /forgot-password → enqueue reset email (generic response to avoid enumeration)
GET  /reset-password/{token}  → show reset form (valid token only)
POST /reset-password/{token}  → set new password (one-time token)
GET  /dashboard       → list leagues owned by current user (owner_user_id)
GET  /verify/{token}  → mark user.is_verified = True and clear token

GET  /login           → shared page for league-admin PIN login + account login
POST /login           → existing league admin PIN login (unchanged)
GET  /logout          → clears both access_token (league admin) and user_access_token (user)
```

> **Warning:** Keep the current `admin_password` as a backward-compatible PIN. Do not remove it suddenly — migrate gradually.

### Implementation Checklist
- [x] `users` table + ORM model (`app/models/user_model.py`)
- [x] Email verification flow (`/register` + `/verify/{token}` + `User.is_verified`)
- [x] Password reset flow (`/forgot-password` + `/reset-password/{token}` + one-time DB token table)
- [x] Register/login routes + templates (`app/routers/accounts.py`, `auth.py`, `auth/login.html`, `auth/register.html`)
- [x] `/dashboard` for owned leagues (basic listing; richer stats & onboarding kept for Phase 5)
- [ ] Migration strategy for existing leagues (link by `admin_email`, then backfill `owner_user_id`)

### New Files

| File | Purpose |
|------|---------|
| `app/models/user_model.py` | User ORM model |
| `app/routers/accounts.py` | register / login / dashboard routes |
| `app/services/email_service.py` | EmailService + queue-based email delivery with daily limit (Brevo/log providers) |
| `app/templates/dashboard.html` | Multi-league dashboard |
| `app/templates/auth/register.html` | Registration page |

---

## Phase 3 — Plans & Usage Limits

**Goal:** Define Freemium model with enforced limits — even before real billing is live.

**Status:** ❌ Not implemented yet (no user accounts/plans model in production).

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
- ❌ Check limits before adding a player or starting a new match
- ❌ Show a banner: *"You've used 80% of your monthly limit — Upgrade to Pro"*

---

## Phase 4 — Billing & Subscriptions

**Status:** ❌ Not implemented yet.

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

### Implementation Checklist
- ❌ Provider selection + account setup (Stripe first)
- ❌ Checkout/upgrade flow
- ❌ Customer billing portal
- ❌ Webhook signature verification + idempotency
- ❌ Plan state updates + downgrades

---

## Phase 5 — Multi-League Dashboard & Onboarding

**Status:** 🟡 Implemented (dashboard cards + onboarding wizard; no persistence flags yet).

### `/dashboard` Page (post-login)
- ✅ Cards for each league: name, slug, player count, last match date + admin/league links
- ✅ "Create New League" button + "Start onboarding" CTA
- 🟡 Current plan badge placeholder (static "Free" label; upgrades in Phase 3/4)

### Onboarding Wizard (first-time users)
```
Step 1 → League name + slug
Step 2 → Team names (Team A / Team B)
Step 3 → Bulk-add players (comma-separated names)
Step 4 → Done! Share your league link
```

### Implementation Checklist
- ✅ User-auth gated dashboard (uses user_access_token + get_current_user)
- ✅ Onboarding wizard flow (league → teams → players → done)
- 🟡 Persistence/state: uses `league_id` query params + ownership checks (no `User.onboarding_completed` yet)

### Files

| File | Purpose |
|------|---------|
| `app/templates/dashboard.html` | User dashboard |
| `app/templates/onboarding/*.html` | Setup wizard steps |
| `app/routers/accounts.py` | Dashboard route (cards + stats) |
| `app/routers/onboarding.py` | Onboarding routes |

---

## Phase 6 — Security, Monitoring & Ops

**Status:** 🟡 Partially done (strong baseline security; monitoring/ops hardening still missing).

### Production Baseline (Already in place)
- ✅ CSRF protection (double-submit cookie)
- ✅ Rate limiting via `slowapi` (login/vote + middleware)
- ✅ Security headers + CSP middleware
- ✅ JWT revocation (`jti` + `revoked_tokens`)
- ✅ Audit log service (operational trail)
- ✅ League backup export (`/admin/export/backup`) + CSV stats export
- ✅ PWA basics (manifest + `/sw.js`)
- ✅ Match media endpoints + optional Supabase storage integration
- ✅ Web push subscription endpoints (VAPID)

### Rate Limiting (`slowapi` middleware)
| Endpoint | Limit |
|----------|-------|
| `POST /create-league` | 3 leagues / IP / day |
| Public APIs | 60 req / min |
| Voting API | Already protected (fingerprint) |

### Logging & Monitoring
- 🟡 Improve structured logging for: league creation, match recording, cup resolution (AuditLog exists; structured app logs still missing)
- ❌ Integrate **Sentry** (free hobby tier) for error tracking

### Backups
- ✅ JSON export per league — already exists (`/admin/export/backup`)
- ❌ Add scheduled backups for the full database (Render/Supabase)

### Super-Admin Dashboard
- ❌ Protected by `SUPERADMIN_SECRET` env variable
- ❌ Shows: all leagues, owners, plans, activity stats
- ❌ Actions: suspend / delete any league

---

## Phase 7 — Marketing & Branding

**Status:** 🟡 Partially done (basic landing exists; marketing/demo/branding not complete).

### New Landing Page
- 🟡 Landing page exists, but needs marketing polish:
  - **Hero:** *"Create your 5-a-side Fantasy League in 2 minutes"*
  - **Features section:** highlight the key features already built
  - **Screenshots** from the live league
  - **Pricing table:** Free / Pro / Unlimited

### Demo Mode
- ❌ Pre-seeded data in `/l/demo`
- ❌ "Try Demo" button on the landing page

### Branding
- ❌ Logo + consistent color palette
- ❌ Short tagline: e.g. *"Fantasy Football, your way."*
- ❌ OG meta tags for social sharing

---

## Phase 8 — Prioritized Execution Roadmap

```
1️⃣  Harden multi-tenancy      → Phase 1  (query audit + isolation)
2️⃣  User accounts + login     → Phase 2  (User model + JWT + email)
3️⃣  Multi-league dashboard    → Phase 5  (Dashboard + Onboarding)
4️⃣  Free/Pro limits logic     → Phase 3  (without real billing first)
5️⃣  Stripe integration        → Phase 4  (Billing + Webhooks)
6️⃣  Landing page + Demo       → Phase 7  (Marketing)
7️⃣  Observability + Ops       → Phase 6  (Sentry + backups + structured logging)
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
