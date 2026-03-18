# PROJECT_CONTEXT.md

### 🔗 Quick navigation
- **High-level index**: see `PROJECT_INDEX.md`
- [1) System Architecture & Tech Stack](#1-system-architecture--tech-stack)
- [2) Database Schema & Relationships](#2-database-schema--relationships)
- [3) Core Business Logic & The Game Engine](#3-core-business-logic--the-game-engine-critical)
- [4) Voting, Anti-Cheat & Security](#4-voting-anti-cheat--security)
- [5) Frontend Behavior & UX Notes](#5-frontend-behavior--ux-notes)
- [6) Operational Concerns](#6-operational-concerns)
- [7) Gotchas, Edge Cases & Invariants](#7-gotchas-edge-cases--invariants)

---

## 1) System Architecture & Tech Stack

### 1.1 Product Scope
- Multi-tenant Fantasy Football SaaS for 5-a-side leagues.
- Tenant isolation is league-scoped via slug paths: `/l/{slug}`.
- Admin session is league-bound JWT (`sub = league.slug`) stored in `access_token` cookie.
- User account session is a separate JWT (`sub = user.id`, `scope = "user"`) stored in `user_access_token` cookie (used by `/dashboard` and `/onboarding/*`).

### 1.2 Backend
- Framework: FastAPI.
- Dependency injection through `app/dependencies.py`.
- Router split:
  - `app/routers/public.py`: landing, create-league flow (with admin_email + slug autosuggest/availability + confirmation page), leaderboard, matches, cup, player profile, stats pages.
  - `app/routers/admin.py`: admin dashboard, match CRUD, season/cup actions, teams, transfers, imports/exports; all league operations go through league-scoped dependencies.
  - `app/routers/voting.py`: voting APIs (`status`, `live`, `closed-results`, `vote`, `open`, `close`).
  - `app/routers/auth.py`: login/logout (league admin PIN) + user account login (`POST /user/login`).
  - `app/routers/accounts.py`: user registration + email verification + password reset (`/forgot-password`, `/reset-password/{token}`) + multi-league `/dashboard`.
  - `app/routers/onboarding.py`: user-auth gated onboarding wizard (`/onboarding/*`) to create an owned league and add initial data.
  - `app/routers/superadmin.py`: platform-level admin dashboard (requires `SUPERADMIN_SECRET` and `X-Superadmin-Secret` header).
  - `app/routers/media.py`: match image upload/delete.
  - `app/routers/notifications.py`: web push subscription endpoints.

### 1.3 Frontend
- Server-rendered Jinja2 templates (`app/templates/**`).
- Vanilla JS modules (`app/static/js/**`).
- CSS design-token-based styling in `app/static/css/style.css` with RTL support and dark mode.
- Analytics slot in `app/templates/base.html` (`{% block analytics %}`) wired to GA4 (`G-81P7TKRS4V`) and disabled for admins via `is_admin` to avoid polluting product metrics.
- No Tailwind in this codebase (custom CSS only).

### 1.3.1 Structured Logging (Phase 6)
- The app emits searchable **structured event logs** via `app/core/logging.py` (`log_event(event, **fields)`).
- Used for high-signal operations like:
  - League creation
  - Match creation
  - Cup generation
  - Season end
- Never log secrets (passwords, JWTs, reset tokens).

### 1.4 Data Layer
- SQLAlchemy ORM models in `app/models/models.py`.
- Repositories in `app/repositories/db_repository.py` implementing interfaces from `app/repositories/interfaces.py`.
- Local dev default: SQLite (`sqlite:///./data/fantasy.db`).
- Production: PostgreSQL (Render/Supabase compatible URL handling in `app/database.py`).

### 1.5 Security & Platform
- JWT auth with `jti` claim and revocation table (`revoked_tokens`).
- CSRF double-submit cookie pattern (`app/core/csrf.py`).
- Rate limiting via `slowapi` (e.g. login and vote endpoints).
- Security headers middleware with CSP in `app/middleware/security_headers.py`.
- PWA basics: `manifest.json`, service worker (`/sw.js`), push notifications via VAPID + `pywebpush`.

### 1.5.1 Error Tracking (Sentry — Phase 6)
- Optional Sentry integration is initialized in `app/main.py` and is **disabled by default**.
- Enable by setting:
  - `SENTRY_DSN`
  - Optional: `SENTRY_ENVIRONMENT` (defaults to `ENV`)
  - Optional: `SENTRY_TRACES_SAMPLE_RATE` (defaults to `0.0`)
- Privacy: `send_default_pii=False` to avoid sending personal data by default.

### 1.6 Deployment
- Render blueprint in `render.yaml`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Optional Supabase Storage integration for persistent match media via env vars:
  - `SUPABASE_PROJECT_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`

### 1.7 Email Delivery & Provider Limits
- Outbound emails (e.g. account verification, future password reset) go through:
  - `app/services/email_service.py` → `EmailService` + provider abstraction.
  - DB-backed queue in `email_queue` table.
- A background worker in `app/main.py` periodically drains the queue using `process_email_queue_once`
  and enforces a configurable daily limit:
  - `email_daily_limit` setting in `core/config.py` (defaults to 300, aligned with Brevo Free plan).
- Daily usage is tracked in `email_daily_usage` table (UTC date + sent_count).
- Priority rules:
  - `transactional` > `system` > `notification` — higher priority emails are always sent first when
    approaching the daily limit so that verification/OTP flows are not blocked by match notifications.
- Current providers:
  - `LogEmailProvider` (default in development/tests): يكتب الإيميل في الـ logs فقط.
  - `BrevoEmailProvider` (عند ضبط `EMAIL_PROVIDER=brevo` + مفاتيح Brevo في `.env`): يرسل فعليًا عبر Brevo
    باستخدام endpoint `/v3/smtp/email`. أي features جديدة (OTP, reset, notifications) يجب أن تمر عبر
    نفس `EmailService` للاستفادة من الطابور وحد الإرسال اليومي.


## 2) Database Schema & Relationships

### 2.1 Core Models

#### League
- PK: `id`.
- Unique: `name`, `slug`.
- Season counters: `current_season_matches`, `season_number`.
- UI labels: `team_a_label`, `team_b_label`.
- Relations:
  - `players`, `matches`, `votes`, `cup_matchups`, `hall_of_fame_records`, `teams`, `transfers` (cascade delete).

#### Team
- PK: `id`, FK: `league_id -> leagues.id`.
- Team identity fields: `name`, `short_code`, `color`.
- Relations: `league`, `players`.

#### Player
- PK: `id`, FK: `league_id`, optional FK `team_id`.
- Seasonal aggregates: `total_*`.
- Historical aggregates: `all_time_*`.
- Season snapshot fields for undo: `last_season_*`.
- Cup flag: `is_active_in_cup`.
- Relations: `league`, `team`, `match_stats`.

#### Match
- PK: `id`, FK: `league_id`, optional FKs `team_a_id`, `team_b_id`.
- Scoreboard fields: `team_a_name`, `team_b_name`, `team_a_score`, `team_b_score`.
- Voting state: `voting_round` (0 not started, 1..3 active rounds, 4 closed).
- Allowed-voters whitelist: `allowed_voter_ids` (JSON text of player ids or null).
- Relations: `league`, `team_a`, `team_b`, `stats`, `votes`, `media`.

#### MatchStat
- PK: `id`, FK: `player_id`, `match_id`.
- Performance: `goals`, `assists`, `saves`, `goals_conceded`, `own_goals`.
- Flags: `is_winner`, `is_gk`, `clean_sheet`, `defensive_contribution`, `mvp`, `is_captain`.
- Scoring: `points_earned`, `bonus_points`, `voting_bonus_applied`.

#### Transfer
- PK: `id`, FK: `league_id`, `player_id`, optional `from_team_id`, required `to_team_id`.
- Immutable movement audit (`created_at`, optional `reason`).

#### CupMatchup (CupFixture equivalent)
- PK: `id`, FK: `league_id`, `player1_id`, optional `player2_id`, optional `winner_id`, optional `winner2_id`, optional `match_id`.
- Seasonal: `season_number`.
- Bracket metadata: `round_name`, `bracket_type` (`outfield` or `goalkeeper`), `is_active`, `is_revealed`.

#### HallOfFame
- Winner snapshot per ended season: `player_id`, `points_scored`, `month_year`, `season_matches_count`.
- Seasonal awards snapshot:
  - `top_scorer_id/top_scorer_goals`
  - `top_assister_id/top_assister_assists`
  - `top_gk_id/top_gk_saves`

### 2.2 Supporting Models
- `Vote`: per-round voting records (+ anti-cheat metadata `ip_address`, `device_fingerprint`).
- `AuditLog`: immutable operational audit trail.
- `RevokedToken`: JWT revocation list by `jti` and expiration.
- `MatchMedia`: uploaded media metadata; supports local or Supabase URL.
- `PushSubscription`: web push endpoints and keys.

### 2.3 Query/ORM Optimizations
- `MatchRepository.get_all_for_league` uses `joinedload(models.Match.stats).joinedload(models.MatchStat.player)` and team joins to avoid N+1 in match pages.
- `PlayerRepository.get_leaderboard` uses joinedloads for player team + match stats + stat.match.
- Startup migrations create performance indexes:
  - `idx_players_league_id`, `idx_matches_league_id`, `idx_match_stats_player_id`, `idx_match_stats_match_id`, `idx_votes_match_id`.


## 3) Core Business Logic & The Game Engine (CRITICAL)

### 3.1 Points System (Authoritative)
Source: `app/services/points.py`.

Scoring components (summed):
- Participation: `+2`.
- Goal:
  - GK: `+6` each.
  - Outfield: `+3` each.
- Assist:
  - GK: `+4` each.
  - Outfield: `+2` each.
- Result:
  - Win: `+2`.
  - Draw: `+1`.
  - Loss: `-1`.
- Clean sheet:
  - GK tiered:
    - `goals_conceded <= 2` => `+10`.
    - `3..6` => `+4`.
    - `>6` => `0`.
  - Outfield clean sheet flag => `+2`.
- Saves (GK): `(saves // 3) * 2`.
- GK concession penalty: `-(goals_conceded // 4)`.
- Own goals: `-own_goals` (i.e., `-1` per own goal).
- Defensive contribution: `+2` if `defensive_contribution=True` and not GK.

Additional additive bonus path:
- `bonus_points` can be passed on match creation/edit and is added to `points_earned`.
- Voting closure also writes `bonus_points` (3/2/1 by round winner) and increments `points_earned`.

### 3.2 Match Registration Engine
Source: `app/services/match_service.py` + `app/routers/admin.py`.

Pipeline:
1. Snapshot current ranks (`previous_rank`) before mutation.
2. Validate teams if league uses fixed team system.
3. Compute match score from stat lines (`sum(goals by team)`).
4. Normalize player names (Arabic normalization rules) and auto-create missing players.
5. Compute points via `calculate_player_points` + include `bonus_points`.
6. Persist `Match` + `MatchStat` rows in one transaction.
7. Update player season aggregates (`total_*`).
8. Auto-resolve cup fixtures for this match.

Constraints:
- Duplicate player in same submitted match is rejected (`400 لاعب مكرر في التشكيلة`).
- GK clean sheet can be auto-enabled for `goals_conceded <= 6`.

### 3.3 Automated Season Engine
Source: `admin.create_match`, `LeagueService.end_current_season`, `undo_end_season`.

Automatic lifecycle:
- `league.current_season_matches` increments per new match.
- At `>=4`, season auto-ends.
- HOF snapshot is written if top player has positive points.
- All player `total_*` moves to `all_time_*`, totals reset to zero.
- Snapshot fields `last_season_*` are populated for rollback support.
- `is_active_in_cup` reset for all players.
- Cup fixtures for ending season are deleted.
- League counters reset: `current_season_matches=0`, `season_number += 1`.

HOF award logic:
- Champion: leaderboard #1 by season points.
- Top scorer: max `total_goals`.
- Top assister: max `total_assists`.
- GK of month: max `total_saves` across players (not only default GK), if any saves > 0.

Undo season:
- Deletes latest HOF row.
- Restores player totals from `last_season_*`.
- Subtracts those values back from all-time aggregates.
- Restores `previous_rank` from snapshot.
- Clears snapshots.
- Rolls back league season counters.

Matches view season selector:
- The public matches page (`/l/{slug}/matches`) derives a lightweight per-match `season_number`
  from league counters (`season_number` and `current_season_matches`) and chronological match order.
- Users can pass an optional `?season=N` query parameter to filter matches to a single season, and
  the header season selector uses those computed seasons to avoid long scrolling in long-lived leagues.

### 3.4 Cup Engine (Clean Architecture)
Primary files:
- `app/use_cases/generate_cup.py` (`GenerateCupUseCase`)
- `app/domain/season_boundary.py`
- `app/domain/standings.py`
- `app/domain/cup_seeding.py`
- `app/services/cup_service.py`

Generation flow:
1. Determine target season and standings scope with `determine_cup_season_target`:
   - If season just reset (`current_season_matches == 0` and `season_number > 1`), use previous season standings (`last_season_points`).
   - Else use current season standings (`total_points`).
2. Delete existing cup fixtures for target season only.
3. Select top 10 players by scope points.
4. Mark `is_active_in_cup` only for selected players.
5. Split selected into GK bracket (`default_is_gk=True`) and outfield bracket.
6. Pair each bracket with team-collision minimization (`minimize_same_team_pairs`).
7. Assign round labels based on bracket size.
8. Odd count => bye fixture (`player2_id=None`, immediately `winner_id=player1_id`, inactive/revealed).

Resolution flow (`auto_resolve_cups`):
- Triggered after each match save/update.
- Only resolves fixtures where both cup players participated in same match.
- Winner is by match points (`points_earned`), then overall points tie-breaker, then deterministic fallback to `player1`.
- Loser deactivated (`is_active_in_cup=False`).
- Fixture marked inactive/revealed and linked to resolving match id.

Co-op final edge case:
- In final (`<=2 active players in bracket`) if both finalists played on same team side in that match, both are winners:
  - `winner_id` and `winner2_id` set.
  - No loser deactivation.

Bracket advancement:
- When no active fixtures remain in a bracket, winners of latest resolved round are paired into next round using same seeding helper.

### 3.5 Teams & Transfer Market
- Players can be assigned to fixed teams (`team_id`) but historical match rows remain immutable with `team` side stored in `MatchStat`.
- Transfers create `Transfer` records and mutate `Player.team_id` only.
- Deleting teams is guarded: blocked if any players or matches reference the team.
- Backward compatibility preserved for old matches without `team_a_id`/`team_b_id` (display still uses legacy `team_a_name`/`team_b_name`).

### 3.6 Voting Anti-Cheat System (3-layer)
Server-side (`VotingService.submit_vote`):
1. IP throttling by per-round cap (`MAX_VOTES_PER_IP = 2`).
2. Browser fingerprint uniqueness per match round (`device_fingerprint`).
3. Duplicate voter lock by `voter_id` + round.

Client-side:
- `leaderboard_voting.js` stores local marker `voted_{matchId}_{round}` in localStorage (UX deterrent + signal).

Additional vote integrity constraints:
- Voting only when round is active.
- Round number must match server current round.
- No self-vote.
- Voter and candidate must both be participants in match stats.
- Previous round winners excluded from later rounds.
- Optional admin whitelist (`allowed_voter_ids`) enforced.


## 4) Frontend Quirks & UI Workarounds

### 4.1 html2canvas Capture Workarounds
Files:
- `app/static/js/leaderboard.js`
- `app/static/js/matches.js`
- `app/static/js/player_profile.js`

Observed constraints:
- CSS variables + dark mode + transitions can cause missing/invisible content in snapshots.
- Scroll wrappers (`.table-responsive` with overflow) can clip table body in screenshots.

Current mitigation pattern in leaderboard/matches capture:
1. Temporarily disable transitions globally with injected style (`* { transition: none !important; }`).
2. Force desired theme mode during capture (dark-mode preservation behavior).
3. Force reflow (`offsetHeight`) before style sampling.
4. Temporarily set `.table-responsive` overflow to visible to avoid clipping.
5. Inline computed text/background colors on descendants before capture.
6. Capture with `html2canvas(..., { scale: 2, useCORS: true, windowWidth/Height = scroll size })`.
7. Restore all mutated styles/theme immediately after resolve/reject.

Player card export:
- Uses fixed off-screen render strategy and width cap (`Math.min(420, window.innerWidth)`).

Important note:
- Historic attempts with `onclone`/`foreignObjectRendering` had compatibility regressions; current code intentionally uses direct pre-capture style baking.

### 4.2 RTL/Typography & CSS Conventions
- Global `dir="rtl"` in `base.html`; text alignment defaults right.
- Primary font stack starts with Tajawal from Google Fonts.
- Theme tokens are centralized in `:root` and overridden by `.dark-mode` token map.
- Many templates still contain selective inline style attributes for contextual color tags and badges.

### 4.3 UI Animation Layer
- `animations.js` provides helpers (`FantasyMotion`) used by pages for stagger/modal/button effects.
- Defensive coding is required because UI logic checks `if (window.FantasyMotion)` before invoking.


## 5) Strict Rules for Future AI Agents

### 5.1 Do NOT Break Domain Rules
1. Do not change points formulas without updating `app/services/points.py` and tests (`tests/test_points.py`).
2. Do not alter cup pairing/resolution behavior without reviewing:
   - `app/use_cases/generate_cup.py`
   - `app/services/cup_service.py`
   - `app/domain/*`
   - `tests/test_cup.py`
3. Do not remove co-op final behavior (`winner2_id`) logic.
4. Do not change season auto-end threshold (4 matches) unless all admin/league flows are adjusted.
5. Do not mutate historical `MatchStat` semantics when implementing transfers.

### 5.2 Backward Compatibility Requirements
6. Always keep compatibility for legacy matches that do not have team foreign keys (`team_a_id/team_b_id` may be null).
7. Preserve both name-based and id-based team display fallback in templates/services.
8. When adding schema fields, append startup migration entry in `app/main.py`.
9. For PostgreSQL datatype fixes, handle `DEFAULT` drop/restore if casting legacy columns.

### 5.3 Security Non-Negotiables
10. Never bypass CSRF verification on state-changing routes.
11. Never trust frontend vote constraints; enforce all voting checks server-side.
12. Keep JWT revocation checks in admin authorization path.
13. Preserve CSP and security headers unless explicitly audited and replaced.
14. Never log secrets, tokens, raw passwords, or service-role keys.

### 5.4 Performance & Data Access
15. Avoid introducing N+1 queries in leaderboard/matches/player pages.
16. Reuse repository patterns and `joinedload` where list pages render nested relations.
17. Preserve league scoping on every query/mutation path.

### 5.5 Frontend Stability
18. Do not “simplify” html2canvas flows without validating dark mode + table body rendering on both leaderboard and matches.
19. Do not remove cache-busting query params from script/style includes when changing static assets.
20. Keep RTL layout assumptions intact (alignment, ordering, labels).

### 5.6 Change Management Checklist (Mandatory)
Before merging any non-trivial change:
1. Run test suite (`pytest`) and verify all pass.
2. Verify admin match create/edit/delete + leaderboard consistency.
3. Verify voting round open/close + anti-cheat behavior.
4. Verify cup generation and at least one auto-resolution path.
5. Verify screenshot sharing paths (leaderboard + match card) in both light/dark conditions.


## 6) Dependency Map (Execution Order Snapshot)

1. Request enters FastAPI app (`app/main.py`) with middleware stack.
2. Route resolves repositories/services through `app/dependencies.py`.
3. Services orchestrate repository calls and domain helpers.
4. SQLAlchemy models materialize response objects.
5. Jinja templates render HTML; JS modules enhance interactions post-render.
6. For writes, audit logger dependency records admin actions into `audit_log`.


## 7) Known Operational Caveats

### 7.1 Backups & Restore (Supabase-native strategy — Phase 6)
- **Goal:** full-database backups and point-in-time recovery (PITR) are handled by Supabase; the app keeps per-league JSON export as a lightweight fallback.

**Recommended setup (Supabase):**
- Enable Supabase **Backups** (and **PITR** if available on your plan) in the Supabase dashboard.
- Define an internal policy for:
  - Backup retention (e.g., 7/14/30 days)
  - Who can perform restores
  - When restores are allowed (maintenance windows)

**Restore runbook:**
- Single-league data issue: prefer per-league recovery via the existing league JSON export (`/admin/export/backup`) when possible.
- Full DB incident / bad migration / accidental destructive change: use Supabase restore/PITR.
  - Prefer restore to a separate instance/branch when possible, verify, then cut over app DB URL.

- Startup migrations are best-effort and skip existing columns by catching exceptions; failed migrations can silently leave legacy shape until explicitly fixed.
- CSS corruption in `style.css` can degrade whole UI to a plain/skeleton-like view; treat top token block as critical and syntactically sensitive.
- Voting whitelist (`allowed_voter_ids`) is stored as JSON text in `matches.allowed_voter_ids`; malformed legacy values are interpreted as no whitelist.
- Match media storage can run in dual mode (Supabase or local uploads). Code must handle both safely.
