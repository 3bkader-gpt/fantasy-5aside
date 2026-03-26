# Deployment & environment logic

How the app chooses a database, which env vars matter in production, and how Render is wired.

---

## 1. Database URL resolution

- **`app/core/config.py`** (`Settings`): reads `.env` via Pydantic settings. Important fields:
  - `database_url` — default local SQLite `sqlite:///./data/fantasy.db`
  - `supabase_url` — optional; if set, preferred over `database_url` for runtime **unless** `use_sqlite` is true
  - `use_sqlite` — force SQLite even when `DATABASE_URL` points at Postgres (local dev)
  - `testing` + `test_database_url` — pytest / test runs
- **`effective_database_url`** is what `app/database.py` uses to build the SQLAlchemy engine.
- **`app/database.py`**: normalizes `postgres://` → `postgresql://`, enables `check_same_thread` for SQLite, pooling for Postgres.

---

## 2. Render.com (`render.yaml`)

- Single **web** service: `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`.
- Declared env vars (values set in dashboard, `sync: false`): `DATABASE_URL`, `SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CORS_ORIGINS`, `ENV`, `SECRET_KEY`.
- Add in the dashboard anything else the app needs (see below); not every variable is listed in `render.yaml`.

**Why `--proxy-headers` matters (Render SSL termination):**
- Render terminates HTTPS at the edge, then forwards requests to your app over HTTP with `X-Forwarded-*` headers.
- Without `--proxy-headers`, the app may see the scheme as `http`, which can impact:
  - generated links when `BASE_URL` is not set (fallback uses `request.base_url`)
  - behavior that depends on “is this HTTPS?” (secure cookies are only accepted by browsers over HTTPS)

---

## 3. Other production-relevant settings

| Concern | Settings / notes |
|--------|-------------------|
| JWT & cookies | `SECRET_KEY`; `ENV=production` enables `secure` cookies in `auth` routes |
| CORS | `CORS_ORIGINS` comma-separated list; parsed in `settings.cors_origins_list` |
| Match media | `SUPABASE_PROJECT_URL` + `SUPABASE_SERVICE_ROLE_KEY` — uploads go to Supabase Storage bucket `match-media`; without them, files go to local `uploads/` |
| Email | `EMAIL_PROVIDER`, Brevo keys, `EMAIL_DAILY_LIMIT` — see `docs/email/logic.md` |
| Push | VAPID keys + subject — see `docs/notifications/logic.md` |
| Superadmin | `SUPERADMIN_SECRET` — header `X-Superadmin-Secret` |
| Sentry | `SENTRY_DSN`, optional trace sample rate |
| User emails | `BASE_URL` used when building verification/reset links in `accounts` router. Recommended: set it explicitly to your public **HTTPS** URL (Render/custom domain). If unset, the app falls back to `request.base_url`, which depends on correct proxy header handling. |

Pydantic loads these from environment variables (typically UPPER_SNAKE_CASE aliases of field names — check `BaseSettings` behaviour for exact names).

---

## 4. Local run

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default: SQLite under `./data/fantasy.db` if no overriding env.

---

## 5. Schema / migrations

- **`app/main.py` lifespan**: lightweight “ensure tables / columns exist” logic for SQLite-oriented evolution; production Postgres still relies on compatible schema — treat major changes as deliberate migrations.
- **Important**: for production PostgreSQL, the manual `ALTER TABLE` approach in `app/main.py` is a temporary workaround. **Integrating Alembic is required** before further schema evolution (especially type changes / non-trivial migrations) to avoid locks and downtime.

---

## 6. Scaling note (future)

- Running Uvicorn directly is fine for small plans, but it is single-process.
- For higher traffic, use Gunicorn as a process manager to run multiple Uvicorn workers (example):

```bash
gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers 2 --threads 2
```
