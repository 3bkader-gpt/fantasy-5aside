# Owner onboarding wizard logic

Guided flow for a **logged-in user** to create their first **owned** league (`owner_user_id` + `admin_email`). Router prefix: `/onboarding` in `app/routers/onboarding.py`.

---

## 1. Access control

- Every step uses **`get_current_user`** (personal account cookie).
- **`_require_owned_league`**: for steps after league creation, `league.owner_user_id` must equal `current_user.id` or the request is 403.

---

## 2. Steps

1. **`GET /onboarding/start`**: If the user already owns a non-deleted league → the system resumes smartly:
   - if the last league has no players yet → redirect to `/onboarding/players?league_id=<id>`
   - if it has players → redirect to `/dashboard`
   Else show intro and CSRF.
2. **`GET/POST /onboarding/league`**: Create `League` with name, URL-safe slug (regex `^[a-zA-Z0-9_-]+$`), hashed `admin_password`, `admin_email` = user email, `owner_user_id` = user id. Slug uniqueness enforced.
3. **`GET/POST /onboarding/teams?league_id=`**: Update `team_a_label` / `team_b_label` defaults.
4. **`GET/POST /onboarding/players?league_id=`**: Bulk-create players from textarea (newline or comma separated); dedupe by lowercase name; skip names that already exist in the league.
5. **`GET /onboarding/done`**: Summary with count of players created in the last step.

---

## 3. Comparison to public league creation

- **`POST /create-league`** (public) is removed: the public creation vector is closed to keep the system account-centric and prevent orphaned leagues.
- Onboarding is the **account-centric** path for SaaS-style “my leagues.”

---

## 4. CSRF

- All mutating steps verify the CSRF cookie + form token, same pattern as other form routes.
