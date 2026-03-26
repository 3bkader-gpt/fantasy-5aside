# User accounts logic

Email-based **personal accounts** are separate from league admin PIN auth. Routers: `app/routers/accounts.py`, `app/routers/auth.py` (`/user/login`). Services: `UserService`, `EmailService`.

---

## 1. Registration

- `GET/POST /register`: CSRF-protected form; `user_service.register_user` creates `User` with hashed password, verification token, `verification_token_expires_at` (now + TTL), `is_verified=False`.
- Verification email: link `{BASE_URL}/verify/{token}`. `BASE_URL` from env or request base URL.

---

## 2. Email verification

- **TTL:** `user_verify_token_ttl_hours` in `app/core/config.py` (default **24 hours**). Stored on `users.verification_token_expires_at`.
- `GET /verify/{token}`: `verify_user_by_token` succeeds only if token matches and (no expiry row **or** expiry &gt; now). Legacy rows with `verification_token_expires_at = NULL` still verify until you backfill. On success: `is_verified=True`, token and expiry cleared.
- Invalid or expired link: login template with error *Invalid or expired verification link* (same message for both cases).

---

## 3. Login policy (SaaS user)

- `POST /user/login`: After correct email/password, login is **refused** if `is_verified` is false. The user sees a verification-required message and a link to **Resend verification email** (`/resend-verification` with email pre-filled when available).
- League admin login (`POST /login` with league name + PIN) is unchanged and does not use `User.is_verified`.

---

## 4. Resend verification

- `GET/POST /resend-verification`: CSRF on POST; rate-limited like forgot-password (`5/minute`).
- **Anti-enumeration:** Always redirects to `/login?msg=verification_resent` with a generic message, whether the email exists or not.
- If an **active, unverified** user exists for that email: new token, new `verification_token_expires_at`, verification email sent (old link stops working).

---

## 5. Password reset

- `GET/POST /forgot-password`: rate-limited; generic success; `request_password_reset` creates a row in `password_reset_tokens` with **`expires_at` = now + 45 minutes** (UTC).
- `GET/POST /reset-password/{token}`: valid token shows form; POST updates password and marks token used.

---

## 6. Dashboard and league owner → admin JWT

- `GET /dashboard`: requires `user_access_token` (`get_current_user`). Lists leagues with `owner_user_id` = current user.
- Admin UI routes use **league admin JWT** in cookie `access_token` (`sub` = league slug). Owners used to hit `/l/{slug}/admin` directly without that cookie and got **401**.
- **`POST /enter-league-admin`**: CSRF + authenticated user; requires **`is_verified`**; loads league by slug; ensures `league.owner_user_id == current_user.id`; issues the same admin JWT as `POST /login` (PIN flow) and sets `access_token`, then redirects to `/l/{slug}/admin`. Rate limit `30/minute`.
- Dashboard **admin entry** uses a POST form to this endpoint (not a bare GET to `/l/.../admin`).

---

## 7. Token / session summary

| Mechanism              | Lifetime / notes                                      |
| ---------------------- | ----------------------------------------------------- |
| Email verification     | Configurable hours (default 24h), column on `users`   |
| Password reset token   | **45 minutes** (`UserService.request_password_reset`) |
| User JWT (`user_access_token`) / admin JWT (`access_token`) | See `docs/auth/logic.md` and `ACCESS_TOKEN_EXPIRE_MINUTES` in `app/core/security.py` (currently **7 days**). |

---

## 8. Security notes

- Password policy: `security.validate_password_strength` on register/reset.
- CSRF on state-changing account and assume-admin routes.
- Logout and cookie behaviour: `docs/auth/logic.md`.
