# Email queue & providers logic

Transactional email (verification, password reset) is **enqueued** first, then **fastpathed immediately** via `BackgroundTasks` from the `accounts` routes. 
Non-transactional backlog (e.g. `system`, `notification`) is processed periodically by the lifespan worker.

---

## 1. Models

- **`EmailQueue`**:
  - `email_type`, `priority`, `status` (`pending` / `processing` / `sent` / `failed` / `cancelled`)
  - scheduling timestamps: `scheduled_at`, `sent_at`
  - claim/in-flight tracking: `processing_started_at` (set when a worker atomically claims a row)
  - delivery bookkeeping: `retries_count`, `provider`
- **`EmailDailyUsage`**:
  - `sent_count`: finalized emails sent today (used for the daily cap)
  - `reserved_count`: emails reserved/claimed today but not yet finalized (prevents over-send across workers)

---

## 2. `EmailService` (`app/services/email_service.py`)

- **`enqueue_email`**: inserts a pending row; priority derived from `email_type` (`transactional` > `system` > `notification`).
- **`send_verification_email` / `send_password_reset_email`**: thin wrappers used by `accounts` routes — they only enqueue.
- **`get_provider_from_settings`**:
  - returns `BrevoEmailProvider` when configured
  - in `settings.testing`, always returns `LogEmailProvider` to avoid real network calls during tests

---

## 3. Background processing

- **`process_email_queue_once(db, provider=None, email_type=None, batch_limit=None)`**: one run with three phases.

  - **Phase 1: claim transaction (short DB txn)**
    - Ensure today's `EmailDailyUsage` row exists.
    - Compute remaining quota as:
      - `remaining = daily_limit - (sent_count + reserved_count)`
    - Select pending queue rows ordered by priority / schedule.
    - On PostgreSQL: atomically claim with `SELECT ... FOR UPDATE SKIP LOCKED`.
    - Mark claimed rows `status="processing"` and set `processing_started_at`.
    - Increment `EmailDailyUsage.reserved_count` by the number of claimed rows.
    - Commit so other workers can observe the claim.

  - **Phase 2: send phase (no DB locks held)**
    - Send each claimed email via the provider.
    - Do not keep a DB transaction open while calling the external provider.

  - **Phase 3: finalize transaction (short DB txn)**
    - Lock today's `EmailDailyUsage` row (Postgres) and:
      - decrement `reserved_count` by claimed count
      - increment `sent_count` by the number of successfully sent emails
    - For each claimed email:
      - `sent`: set `status="sent"`, `sent_at`, `provider`, clear `processing_started_at`
      - `failed` (after 3 retries): set `status="failed"`, clear `processing_started_at`
      - otherwise: return to `status="pending"` and clear `processing_started_at`

- **Transactional fastpath (`accounts` routes)**:
  - After enqueueing verification/reset emails, routes call `_process_transactional_email_fastpath(...)`.
  - In production, this is executed by FastAPI `BackgroundTasks` using `process_email_queue_once(..., email_type="transactional")`.
  - The periodic worker intentionally does not process `transactional` emails.

- **`app/main.py` lifespan**:
  - runs every 30 seconds
  - processes backlog in two passes: `email_type in ("system", "notification")`

---

## 4. Configuration (`app/core/config.py`)

- `email_provider`, `email_daily_limit`, `brevo_api_key`, `brevo_sender_email`, `brevo_sender_name`, `brevo_api_base_url`.

---

## 5. Operational note

- Until Brevo (or another provider) is configured, transactional emails are still fastpathed, but delivery will fall back to the configured provider behavior (typically `LogEmailProvider` in tests).
- SQLite is only intended for local/dev and unit tests; the claim locking semantics are designed for PostgreSQL and are skipped/limited in concurrency tests.
