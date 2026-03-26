# 🏆 League & Season Logic

This document details the business logic for managing leagues, seasons, the Hall of Fame (HOF), and how they interact with the cup in the Fantasy 5-a-Side SaaS.

---

## 1. Multi-Tenancy & Isolation

The system is designed as a multi-tenant SaaS where each league is an independent entity.

- **Data Partitioning**: Every database table (except for global `users`) contains a `league_id` column. All repository queries must include a filter for `league_id` to prevent data leakage between leagues.
- **Identity**: A league is identified by a unique `slug` (used in URLs: `/l/{slug}`) and managed via a unique `id`.
- **Authentication**: Each league has its own `admin_password` (PIN) for administrative actions, separate from the league owner's account credentials.

---

## 2. Season Lifecycle

Seasons are the primary containers for competitive progress.

### A. Tracking Progress

- **Match Count**: `league.current_season_matches` increments when matches are registered (and is used for guards and cup-related logic).
- **Admin reconciliation**: On each **admin dashboard** load, the counter is synced to the **derived** value:  
  `max(0, count(Match for league) − sum(HallOfFame.season_matches_count for league))`.  
  So a manually edited counter that disagrees with actual `Match` / HOF rows is overwritten. Any tooling or tests that set `current_season_matches` without matching rows should expect this sync.
- **Season Number**: `league.season_number` identifies the chronological index of the season.
- **Season-bound matches**: Every `Match` record stores `season_number` to allow filtering match history by season (e.g. `/matches?season=2`).

### B. Ending a Season (`end_current_season`)

Ending a season performs the following in order:

1. **Guard**: If `(league.current_season_matches or 0) < 1`, the operation is rejected (HTTP 400) so an empty “season” cannot overwrite `last_season_*` snapshots or skew all-time stats.
2. **Cup finalization**: If a `CupService` is configured on the league service, `finalize_incomplete_cup(league_id)` runs so pending brackets can be resolved administratively and **outfield / goalkeeper** cup winners are determined before snapshots are taken.
3. **Award calculation** (leaderboard at end of season):
   - **Winner** (`HallOfFame.player_id`): Player with the most `total_points` (existing ordering from `get_leaderboard`).
   - **Top scorer / assister / goalkeeper**: Highest primary stat (`total_goals`, `total_assists`, `total_saves`); ties break on **higher** `total_points`, then **fewer** `total_matches`, then stable `player.id`.
4. **Hall of Fame entry**: A new `HallOfFame` record stores the monthly/season label, the league winner, seasonal award IDs and counts, and optionally:
   - `cup_outfield_winner_id` — winner of the outfield cup bracket for that season’s cup run.
   - `cup_gk_winner_id` — winner of the goalkeeper bracket (if applicable).  
   These may be `NULL` if there was no cup or no winner could be derived.
5. **Per-player stats transition**:
   - **Snapshot**: Current `total_*` stats are copied to `last_season_*` on each `Player` (enables **Undo**).
   - **Aggregation**: Current `total_*` stats are added to `all_time_*` totals.
   - **Reset**: `total_*` fields and `is_active_in_cup` are cleared.
6. **Cup data in DB**: `CupMatchup` rows for the ended season **stay** in the database, keyed by `season_number`.  
   - **No** `delete_all_for_league` runs on season end.  
   - **Public cup views** (`query_cup_for_display`, leaderboard “next cup” helper) use **only** the league’s **current** `season_number`. There is **no** fallback to the previous season: if the new season has no cup yet, the UI shows an empty state. Historical brackets remain queryable in the DB by `season_number` (e.g. analytics or future UI).

### C. Undo Season End (`undo_end_season`)

Allows administrators to revert the **latest** season closure:

- Deletes the latest HOF record.
- Restores each player’s `total_*` from `last_season_*` and subtracts the snapshot from `all_time_*`.
- Restores `league.season_number` and `league.current_season_matches` (from the saved `season_matches_count` on the HOF row, with a fallback when needed).

**Cup rows**: Undo does **not** delete or recreate `CupMatchup` rows. Brackets that existed for the reverted season remain in the database for that `season_number`; only the UI “current season” lens changes when `season_number` is decremented.

#### Architectural limitation: single-level undo (read this before changing undo logic)

`Player` stores **one** rolling snapshot only: `last_season_*`. There is **no** chain of “season −1, season −2, …” on the player row.

**Implication:** Undo is only well-defined as **one step back from the most recent `end_current_season`**. After a successful undo, those `last_season_*` fields are cleared. If an admin (or bug) calls `undo_end_season` again while an **older** HOF row still exists, the code would otherwise restore `total_*` from **zeroed** `last_season_*`, corrupt `all_time_*` rollbacks, and destroy data.

**Mitigations in code:** `undo_end_season` refuses to run when no player has any non-zero `last_season_*` snapshot (HTTP 400 with an Arabic explanation), which blocks the dangerous “double undo” path described above.

**Product / future work:** True multi-season undo would require either stacked snapshots per player, or deriving prior season state from immutable history (e.g. HOF rows + match replay)—out of scope for the current schema.

---

## 3. Hall of Fame (HOF) Logic

The HOF is the permanent record per league for a completed season/month.

- **Award eligibility**: Only players with `total_points > 0` are eligible for the main HOF winner path so inactive leagues do not get empty winner records (seasonal side awards still follow their own stat rules).
- **Snapshots**: HOF rows store IDs and counts for top scorer, assister, goalkeeper, and optionally cup outfield / GK winners at the moment the season ended.
- **Consistency**: `fix_latest_hof_awards` recomputes **seasonal** scorer / assister / GK fields from each player’s `last_season_*` snapshot using the **same** tie-break hierarchy as `end_current_season`. It does **not** re-run cup finalization or change `cup_*` winner columns by default (adjust manually or extend the tool if needed).

---

## 4. Edge Cases & Safeguards

- **Tie-breaking**: Seasonal awards (scorer, assister, keeper) use: primary stat → higher `total_points` → fewer `total_matches` → `player.id`. The same order applies when reading `last_season_*` in `fix_latest_hof_awards`.
- **Empty seasons**: Ending a season requires `current_season_matches >= 1` after any admin sync; otherwise HTTP 400 and no HOF or stat transitions.
- **Cup display**: Only the **current** `league.season_number` is used for cup list / “active” matchup queries—no automatic display of last season’s bracket once the season counter advances.
- **Match baseline**: Manual match recording and HOF history drive the reconciled `current_season_matches`; the cup subsystem may also use league match counts per season for deadlines (e.g. auto-forfeit after N league matches since a round opened—see cup service / `implementation_plan`).
- **Undo depth**: Only one undo per completed `end_current_season` is architecturally sound; see **§2.C — single-level undo** and the runtime guard on empty `last_season_*`.
