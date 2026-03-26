# Match media uploads logic

Admin-only images attached to a **match** for galleries or records. Router: `app/routers/media.py`.

---

## 1. Endpoints

| Method | Path | Auth |
|--------|------|------|
| POST | `/l/{slug}/match/{match_id}/media` | League admin (`get_current_admin_league`) |
| DELETE | `/l/{slug}/media/{media_id}` | League admin |

---

## 2. Limits & validation

- Up to **5 files** per request.
- Types: **JPEG, PNG, WebP** only; max **5 MB** per file.

---

## 3. Storage backends

1. **Supabase Storage** (preferred in production): when `SUPABASE_PROJECT_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set, files go to bucket **`match-media`** under `{league_id}/{match_id}/{uuid}.ext`. `MatchMedia.file_url` stores the public URL; `filename` holds the storage path for deletion.
2. **Local disk (dev only)**: if Supabase is not configured (or in development), files are written under **`uploads/`** with a UUID filename; `MatchMedia.file_url` is set to **`/media/{filename}`** (served via the app's StaticFiles mount).

**Production note:** if Supabase is configured but upload fails in production, the request fails fast (`503 Service Unavailable`) and no local-disk fallback is used.

---

## 4. Data model

- **`MatchMedia`**: `league_id`, `match_id`, `filename`, `original_name`, `mime_type`, `size_bytes`, `uploaded_at`, optional `file_url`.
- `original_name` is sanitized at upload time (path separators, control chars, and HTML-special characters are stripped) before persistence.

---

## 5. Deletion

- Supabase-backed media is removed using Supabase `remove` on `filename` (storage path like `{league_id}/{match_id}/{uuid}.ext`).
- Local media is removed by deleting `uploads/{filename}` (when present), then deleting the DB row.
- Bulk deletion (cascade cleanup): when an entire match is deleted or a league backup is imported, all associated media filenames are collected before the database wipe. A BackgroundTask then asynchronously batch-deletes these files from Supabase (or local disk) to prevent orphaned storage and runaway costs.
