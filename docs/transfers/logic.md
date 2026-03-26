# Transfers & fixed-team “market” logic

This app does **not** run a transfer window or bids. “Transfers” mean **admin-assigned moves** between registered teams inside one league, with an **audit trail** in the database.

---

## 1. Data model

- Table **`transfers`**: `league_id`, `player_id`, `from_team_id` (nullable), **`to_team_id` (nullable — `NULL` = released / free agent)**, optional `reason`, `created_at`.
- See `Transfer` in `app/models/models.py`.
- **`players.team_id`** is the current assignment; history is reconstructed from `transfers` (newest first via repository).

---

## 2. Who can transfer

- **League admin only**, via `POST /l/{slug}/admin/player/{player_id}/transfer` in `app/routers/admin.py`.
- Requires valid admin JWT, CSRF on the form, and target player belonging to the same league.

---

## 3. Behaviour

1. **Remove from team** (`to_team_id` empty, `0`, or `None`): if the player was on a team (`player.team_id` set), create a **`Transfer` row** with `from_team_id` = that team, **`to_team_id` = `NULL`**, optional `reason` (e.g. release), then set `player.team_id = None`. If the player was already without a team, no `Transfer` row is added. **Audit** still logs `transfer_player` with `to_team_id: null`. This keeps the profile **timeline** accurate (no “stuck on last club” while the player is a free agent).
2. **Move to another team**: validate `to_team` exists in the same league and differs from current team. Create a `Transfer` row with `from_team_id` = previous `player.team_id` (may be `NULL`), `to_team_id` = target, then set `player.team_id = to_team_id`.
3. **Historical match integrity**: transfers are **forward-looking only**. Updating `players.team_id` does **not** retroactively alter the player’s team affiliation in existing **`MatchStat`** (or other historical) rows; past match stats stay tied to the matches that were played.
4. **League deletion / season tooling**: bulk deletes for a league can clear `transfers` alongside other league data (see admin season/league cleanup paths in `admin.py`).

---

## 4. Where it appears in the UI

- Player profile (`read_player` in `app/routers/public.py`) loads `transfer_repo.get_all_for_player_for_league` and passes `transfers` to the template for a timeline-style list.

---

## 5. Not in scope

- No fees, deadlines, or player-initiated requests.
- Cross-league moves are impossible by design (FKs and checks are per `league_id`).
