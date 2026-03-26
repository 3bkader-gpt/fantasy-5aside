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
- On signup, passwords must meet policy: minimum **8** characters, at least one digit, one uppercase, one lowercase.

### Sessions & JWT

- Auth uses **JSON Web Tokens (JWT)** stored in **cookies**.
- **Lifetime:** **7 days** from login.
- **Revocation:** on logout, the token **JTI** is written to a **database blocklist** so the token cannot be reused even if its expiry has not passed.

---

## 3. Route protection

- Admin routes are guarded by the `get_current_admin_league` dependency, which ensures:
  1. A valid, non-expired token is present.
  2. The token is **not** on the revocation list.
  3. The token’s **slug** matches the league in the URL (no cross-league admin access).

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
| `access_token` | League admin JWT (`sub` = league slug) | `get_current_admin_league`, `_get_token_payload` in `app/dependencies.py` |
| `user_access_token` | Personal user JWT (`sub` = user id, `scope: user`) | `get_current_user`, `_get_user_token_payload` in `app/dependencies.py` |

Both are set from `app/routers/auth.py` after the respective login flows.

**Logout behavior:** `GET /logout` (same router) revokes the **admin** token’s JTI when present, then calls `delete_cookie` on **both** `access_token` and `user_access_token`. So an admin logout also clears a concurrent personal session. There is no separate “admin-only” or “user-only” logout endpoint today; if partial logout is needed later, split endpoints would be required.

### Admin PIN / password rotation

**Current behavior:** Updating the league admin password (e.g. via league settings / repository update to `leagues.admin_password`) **does not** invalidate JWTs already issued for that league. Those tokens remain valid until they **expire** (7 days) or the holder **logs out** and the JTI is blocklisted.

There is no `admin_password_changed_at` (or similar) on `League`, and `get_current_admin_league` does not compare token issue time to a password-rotation timestamp.

**Possible hardening (not implemented):** Add `admin_password_changed_at` on `leagues`, set it whenever the admin password changes; include an `iat` claim in JWTs (`create_access_token` in `app/core/security.py` currently sets `sub`, `jti`, and `exp` only—`iat` would need to be added explicitly); reject admin tokens where `iat` is older than `admin_password_changed_at`. Bulk-revoking all active admin tokens for a league without that pattern would require tracking every issued JTI per league, which is heavier.

### Revoked-token table growth (blocklist)

Rows in `revoked_tokens` store `jti` and `expires_at`. **`is_revoked`** in `app/core/revocation.py` only treats a row as active if `expires_at > now()`, so once the original token’s lifetime has passed, the row no longer affects authorization—but the row **remains** in the database.

There is **no** scheduled cleanup job in this repository. For long-running deployments, run a periodic job (cron, worker, or external maintenance) such as:

`DELETE FROM revoked_tokens WHERE expires_at < now()`

to keep the table size bounded and lookups cheap as logout volume grows.
