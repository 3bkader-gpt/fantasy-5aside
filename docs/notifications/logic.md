# Web Push notifications logic

Browser **Web Push** (VAPID) is used to nudge subscribers when certain admin actions happen. Delivery is **best-effort**; failures must not break core flows.

---

## 1. Storage

- Model **`PushSubscription`** (see `app/models/models.py`): per `league_id`, unique `endpoint`, keys `p256dh` / `auth`, optional `player_id`.
- `NotificationService` in `app/services/notification_service.py` implements subscribe (upsert by endpoint), unsubscribe (delete by endpoint), and `notify_league`.

---

## 2. API (`app/routers/notifications.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/notifications/public-key` | Client reads VAPID public key for subscription |
| GET | `/api/notifications/vapid-status` | Debug: whether keys are configured/valid |
| POST | `/api/notifications/subscribe` | Body includes `league_slug`, endpoint, keys, optional `player_id` |
| POST | `/api/notifications/unsubscribe` | Remove subscription by `endpoint` |

---

## 3. Configuration (`app/core/config.py`)

- Env-backed settings: `vapid_public_key`, `vapid_private_key`, `vapid_subject` (e.g. `mailto:…`).
- Keys are stored as base64url strings. Whitespace/newlines/paste artifacts are normalized in code.
- If keys are missing/empty, `notify_league` returns immediately without sending (subscribe/unsubscribe still work for DB consistency).
- Operational note: copy/paste errors in base64url padding can break `pywebpush`. Use the debug endpoint `GET /api/notifications/vapid-status` to quickly verify configuration/validity.

---

## 4. When notifications are sent

- **`open_voting`** (`app/routers/voting.py`): after admin opens voting for a match — title/body in Arabic, deep link toward league voting UI.
- **`end_season`** (`app/routers/admin.py`): after season ends — message about Hall of Fame update.

Both call sites dispatch `notify_league` via FastAPI `BackgroundTasks` (with a fresh DB session) so the HTTP response is immediate and the UI doesn't block. Errors are isolated per subscriber inside the background loop.

---

## 5. Runtime behaviour

- Uses `pywebpush` when available; on `WebPushException` (e.g. expired endpoint), the subscription row is deleted.
- Payload is JSON: `title`, `body`, `url` for the service worker / client to display and navigate.
