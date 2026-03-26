# User & Authentication Logic

This document describes how access control works: sessions, league admins vs personal accounts, and the main security layers.

---

## 1. Account types

There are two separate account concepts:

### League admin

- Full control **for one league**.
- Does **not** require an email “user account”; access is via **league slug** + **league admin password** (PIN).
- After signing in at `/l/{slug}/admin/login` with the league password, the token grants admin actions **only** for that league.

### Personal user accounts

- Optional accounts created with **email**.
- Used to link players, transfers, notifications, and similar features.
- A normal user **cannot** open the league admin area unless they also know the **league admin password** for that slug.

---

## 2. Security mechanisms

### Password hashing

- Passwords are hashed with **PBKDF2-SHA256** before storage.
- Legacy plaintext league admin passwords are auto-migrated to hash format during startup.
- On signup, passwords must meet policy: minimum **12** characters, at least one digit, one uppercase, one lowercase, and one special character.

### Sessions & JWT

- Auth uses **JSON Web Tokens (JWT)** stored in **cookies**.
- The app now uses a dual-token model:
  - short-lived access tokens (~2 hours)
  - long-lived refresh tokens (~14 days) with rotation
- **Revocation:** on logout, both access and refresh token JTIs are written to a database blocklist so stolen cookies cannot be replayed.

---

## 3. Route protection

- Admin routes are guarded by the `get_current_admin_league` dependency, which ensures:
  1. A valid, non-expired token is present.
  2. The token is **not** on the revocation list.
  3. The token is bound to immutable `league_id` and must match the target league.

---

## 4. Hardening & observability

### CSRF

- A per-session CSRF value is issued and stored in the `CSRF-TOKEN` cookie.
- State-changing requests (**POST**, **DELETE**, **PUT**) must send that token in a header or form field.

### Audit log

- Sensitive admin actions (e.g. match entry, season end, settings changes) are written to **`audit_log`** for traceability.

### MVP voting abuse

- Voting uses **device fingerprint** and **IP** limits to reduce ballot stuffing; see `docs/match/logic.md` for detail.

---

## 5. Multi-tenant & operational edge cases

### Cookie separation (no admin/user collision on login)

League admin and personal sessions use **different cookie names**, so signing in as one does **not** overwrite the other’s JWT in the same browser:

| Cookie | Purpose | Read by |
|--------|---------|---------|
| `access_token` | League admin access JWT (`sub` = slug, `league_id`, `scope: admin`) | `get_current_admin_league`, `_get_token_payload` in `app/dependencies.py` |
| `refresh_token` | League admin refresh JWT | `/refresh` rotation in `app/routers/auth.py` |
| `user_access_token` | Personal user access JWT (`sub` = user id, `scope: user`) | `get_current_user`, `_get_user_token_payload` in `app/dependencies.py` |
| `user_refresh_token` | Personal user refresh JWT | `/refresh` rotation in `app/routers/auth.py` |

Both are set from `app/routers/auth.py` after the respective login flows.

**Logout behavior:** `GET /logout` revokes all present auth cookies (`access_token`, `refresh_token`, `user_access_token`, `user_refresh_token`) then clears them from the browser.

### Admin PIN / password rotation

**Current behavior:** Updating the league admin password (e.g. via league settings / repository update to `leagues.admin_password`) **does not** invalidate JWTs already issued for that league. Those tokens remain valid until they **expire** (7 days) or the holder **logs out** and the JTI is blocklisted.

There is no `admin_password_changed_at` (or similar) on `League`, and `get_current_admin_league` does not compare token issue time to a password-rotation timestamp.

**Possible hardening (not implemented):** Add `admin_password_changed_at` on `leagues`, set it whenever the admin password changes; include an `iat` claim in JWTs (`create_access_token` in `app/core/security.py` currently sets `sub`, `jti`, and `exp` only—`iat` would need to be added explicitly); reject admin tokens where `iat` is older than `admin_password_changed_at`. Bulk-revoking all active admin tokens for a league without that pattern would require tracking every issued JTI per league, which is heavier.

### Revoked-token table cleanup

Rows in `revoked_tokens` are actively cleaned using startup maintenance (`cleanup_expired_tokens`) so expired JTIs do not grow unbounded.
