# Project Index - 5-a-Side Fantasy Football SaaS

### Quick navigation
- Domain logic index: [`docs/README.md`](../README.md)
- High-level architecture context: [`docs/project/context.md`](context.md)
- SaaS roadmap: [`docs/project/saas_plan.md`](saas_plan.md)

---

## Project Overview

**Type**: Multi-tenant Fantasy Football SaaS for local 5-a-side leagues.

**Stack**:
- Backend: FastAPI + Python
- Data: SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod)
- Frontend: Jinja2 templates + Vanilla JS + CSS
- Auth: Cookie-based JWT sessions (admin + user scopes)

---

## Project Structure

```text
fantasy/
├── app/
│   ├── main.py
│   ├── dependencies.py
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── routers/
│   ├── templates/
│   └── static/
├── docs/
├── tests/
├── requirements.txt
├── requirements-dev.txt
└── mkdocs.yml
```

---

## Database Schema (Core Entities)

- `League`: tenant container, season counters, settings.
- `User`: account identity, verification state.
- `Player`: seasonal + all-time stats, cup status.
- `Match`: scoreline, season membership, voting state.
- `MatchStat`: per-player per-match stats and points.
- `Vote`: anti-cheat metadata and voting rounds.
- `CupMatchup`: bracket fixtures and winners.
- `HallOfFame`: season winners and award snapshots.
- `MatchMedia`: media metadata for local/cloud assets.
- `PushSubscription`: web-push endpoint and keys.
- `EmailQueue` / `EmailDailyUsage`: queue and rate-limit tracking.

---

## Core Features

- Automated points calculation using strategy-based logic.
- Cup generation and progressive auto-resolution.
- Multi-round anti-cheat voting.
- Season end/undo flows with HOF snapshots.
- User accounts, onboarding, and owned-league dashboard.
- Email queue with transactional fast path.
- Web push notifications via background delivery.
- Media uploads with cloud-first fail-fast behavior.

---

## Architectural Patterns

### Repository pattern
- Interfaces in `app/repositories/interfaces.py`
- Implementations in `app/repositories/db_repository.py`

### Service layer
- Business logic isolated in `app/services/*.py`
- Routers delegate orchestration to services

### Strategy pattern
- Points calculation uses role-based scoring strategies

### Dependency injection
- All major services and repositories resolved via `app/dependencies.py`

---

## API Routes

### Public routes (`app/routers/public.py`)
- `GET /`
- `GET /api/slug-available`
- `GET /l/{slug}`
- `GET /l/{slug}/matches`
- `GET /l/{slug}/cup`
- `GET /l/{slug}/player/{id}`
- `GET /l/{slug}/hall-of-fame`
- `GET /l/{slug}/stats`
- `GET /l/{slug}/created`

### Auth and accounts (`app/routers/auth.py`, `app/routers/accounts.py`)
- `GET/POST /login`
- `POST /user/login`
- `GET /logout`
- `GET/POST /register`
- `GET /verify/{token}`
- `GET/POST /forgot-password`
- `GET/POST /reset-password/{token}`
- `GET/POST /resend-verification`
- `GET /dashboard`
- `POST /enter-league-admin`

### Onboarding (`app/routers/onboarding.py`)
- `GET /onboarding/start`
- `GET/POST /onboarding/league`
- `GET/POST /onboarding/teams`
- `GET/POST /onboarding/players`
- `GET /onboarding/done`

### Admin (`app/routers/admin.py`)
- Match create/edit/delete
- Cup generation
- Season end/undo
- Player and team management
- Backup export/import

### Voting (`app/routers/voting.py`)
- Status/live/results
- Submit vote
- Open/close rounds (admin)

### Superadmin (`app/routers/superadmin.py`)
- Platform dashboard
- League deletion flows

---

## Security

- Password hashing and token signing in `app/core/security.py`
- JWT revocation checks via `app/core/revocation.py`
- CSRF protection on mutating routes
- Secure cookie behavior in production
- Anti-cheat protections on voting endpoints

---

## Observability

- Structured event logging for high-signal actions
- Optional Sentry integration through environment flags
- GA4 analytics slot in base template (non-admin traffic)

---

## Test Coverage Map

- `tests/test_points.py`
- `tests/test_match_service.py`
- `tests/test_league_service.py`
- `tests/test_cup.py`
- `tests/test_accounts_api.py`
- `tests/test_api_admin.py`
- `tests/test_api_public.py`
- `tests/test_notification_service.py`
- `tests/test_media_storage.py`
- `tests/test_email_queue_limits.py`

---

## Frontend Notes

- Mobile-first layout and dark mode support
- Share/screenshot flows use `html2canvas` with defensive style handling
- Match and player pages rely on JS modules under `app/static/js/`

---

## Deployment

### Local
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Render (production)
- Requires PostgreSQL
- Start command:
  - `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
- Configure required environment variables (`DATABASE_URL`, `SECRET_KEY`, `BASE_URL`, etc.)

---

## Workflow

Recommended loop:
1. Plan
2. Implement
3. Verify (tests/build)
4. Sync documentation
5. Commit/push

---

## Important Notes

- Name normalization handles Arabic character variants in match ingestion.
- Startup schema sync is pragmatic but not a replacement for full migration tooling.
- Cup edge cases (single participant, timeout/forfeit, co-op outcomes) are explicitly supported.
- Billing and subscription automation remain roadmap items.

---

## Development Tips

### Add a new feature
1. Update models/schemas
2. Add repository methods
3. Add service logic
4. Add routes
5. Add tests
6. Update docs

### Adjust scoring
- Modify `app/services/points.py`
- Recompute affected totals
- Re-run related tests

### Add a new badge
- Update `app/services/achievements.py`
- Ensure required history is available
- Validate leaderboard query performance

---

**Last updated**: March 2026  
**Version**: 3.1  
**Status**: In production  
