# Superadmin logic

Operational **cross-league** tools protected by a **shared secret** (not end-user JWT). Router: `app/routers/superadmin.py`, prefix `/superadmin`.

---

## 1. Authentication

- **`require_superadmin`** accepts one of the following:
  - Optional `x-superadmin-secret` header (for scripts, curl, Postman).
  - **HTTP Basic** (for browser UX): `username` must be fixed to `superadmin`, and `password` must be `settings.superadmin_secret` (`SUPERADMIN_SECRET` / pydantic field `superadmin_secret`).
- Comparisons are done with a timing-safe approach using SHA-256 + `secrets.compare_digest`.
- If the secret is **unset** or authentication fails → **401**. For Basic, the server returns `WWW-Authenticate: Basic` to trigger the browser popup.

---

## 2. Capabilities

- **`GET /superadmin/`**: Lists all leagues with aggregated player and match counts.
- **`GET /superadmin/league/{id}/delete`**: Confirmation page.
- **`POST /superadmin/league/{id}/delete`**: Requires form field `confirm` exactly **`delete`** (case-insensitive), then performs a **soft delete**:
  - sets `leagues.deleted_at = now()`
  - hides the league from normal repository queries
  - does not cascade-delete related rows
  - requires a valid CSRF token from the confirmation page

---

## 3. Security notes

- Treat the secret like a root password: rotate if leaked, use only over HTTPS in production.
- This is **separate** from league admin PIN and from `users.role` — there is no end-user role check here, only the shared secret auth.
- Destructive POST actions are CSRF-protected even when Basic Auth is used.

---

## 4. Relation to product roadmap

- Complements “owner” accounts; intended for platform operators, not league members.
