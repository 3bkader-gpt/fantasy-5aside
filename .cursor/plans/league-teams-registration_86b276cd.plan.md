---
name: league-teams-registration
overview: Add a proper Teams system so each league defines its teams once at the start, and all players and matches reuse those teams instead of retyping names.
todos:
  - id: models-teams
    content: Add Team model and associations + team_id fields on Player and Match, with manual migrations for new columns
    status: pending
  - id: team-repo
    content: Create TeamRepository and interface, and wire it via dependencies
    status: pending
  - id: admin-teams-ui
    content: Add admin UI and routes to create/update/delete league teams
    status: pending
  - id: players-link-teams
    content: Update player add/edit flow to attach players to teams via team_id
    status: pending
  - id: matches-use-teams
    content: Update match creation flow (schemas + service + admin UI/JS) to use selected teams instead of free-text names
    status: pending
  - id: legacy-migration
    content: Design and run data migration to map existing A/B teams and players to new Team records — should be drafted alongside models-teams, not deferred to the end
    status: pending
  - id: ui-display-teams
    content: Show team badges/names in leaderboard, player profile, and matches views when team_id is present
    status: pending
  - id: tests-validation
    content: Add/update tests for team repository, admin flows, and match registration with teams
    status: pending
  - id: transfers-model-service
    content: Add Transfer model and service to move a player between teams within a league while recording history
    status: pending
  - id: transfers-admin-ui
    content: Add admin/player UI to trigger transfers (select new team, optional reason) and display transfer history on player profile
    status: pending
  - id: transfers-tests
    content: Add tests to ensure transfers update player.team_id correctly without mutating past MatchStats, and are constrained to teams within the same league
    status: pending
isProject: false
---

### Goal

Introduce a proper Teams system per league, plus a simple transfer market:

- At the start of the league, the admin registers all participating teams once.
- Players belong to registered teams (not just A/B).
- Match creation uses those teams via dropdowns, not free‑text names.
- Players can transfer between teams inside the same league, with a recorded history of transfers.

---

### 1. Data model design (Models & DB)

- Add a new `Team` model in `[app/models/models.py](app/models/models.py)`:
  - Fields:
    - `id` (PK)
    - `league_id` (FK to `League`)
    - `name` (team name, unique within the league)
    - `short_code` (optional, 2–4 chars, e.g. “HR”, “IT”)
    - `color` (optional hex string, e.g. `#3498db`)
  - Relationship:
    - `league = relationship("League", back_populates="teams")`
- Update `League` model:
  - Add `teams = relationship("Team", back_populates="league", cascade="all, delete")`.
  - Keep `team_a_label` / `team_b_label` temporarily as legacy for existing leagues.
- Update `Player` model:
  - Add `team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)`.
  - Relationship: `team = relationship("Team")`.
  - Keep legacy string field `team` (A/B) for a transition period.
- Update `Match` model:
  - Add `team_a_id`, `team_b_id` (FK to `Team.id`, nullable=True) while keeping `team_a_name` / `team_b_name` as display text.
- Manual migrations in `[app/main.py](app/main.py)`:
  - Add `ALTER TABLE` entries for:
    - `players.team_id`, `matches.team_a_id`, `matches.team_b_id`.
  - The `teams` table itself will be created via `Base.metadata.create_all`.

---

### 2. Repository layer

- Add `ITeamRepository` interface in `[app/repositories/interfaces.py](app/repositories/interfaces.py)`:
  - Methods: `get_all_for_league(league_id)`, `get_by_id`, `get_by_name`, `create`, `save`, `delete`.
- Implement `TeamRepository` in `[app/repositories/db_repository.py](app/repositories/db_repository.py)`:
  - Standard CRUD with filtering by `league_id`.
- Update `[app/dependencies.py](app/dependencies.py)`:
  - Add `get_team_repository` that returns a `TeamRepository` instance.

---

### 3. Team management from the admin dashboard

- Extend admin routes in `[app/routers/admin.py](app/routers/admin.py)`:
  - In `admin_dashboard`, add to context:
    - `teams = team_repo.get_all_for_league(league.id)`.
  - New endpoints:
    - `POST /l/{slug}/admin/team/add` to add a team (`name`, `short_code`, `color`).
    - `POST /l/{slug}/admin/team/{team_id}/update` to edit name/color.
    - `DELETE /l/{slug}/admin/team/{team_id}` to delete a team (with guard: cannot delete if it has players or is used in matches).
- Update admin dashboard template `[app/templates/admin/dashboard.html](app/templates/admin/dashboard.html)`:
  - New section near “League Settings” titled “Teams in this League”.
  - Simple teams table:
    - Columns: name, code, color, player count, edit/delete actions.
  - Form to add a new team (name required, code/color optional).
    - Use `<input type="color">` for the color field so the admin gets a native color picker instead of typing hex values manually.
  - If there are no teams yet, show a short notice like “No teams registered yet”.

---

### 4. Attach players to teams

- Update `add_player` route in `[app/routers/admin.py](app/routers/admin.py)`:
  - Instead of only `team: str = Form(...)`, add `team_id: int = Form(...)`.
  - Logic:
    - When creating a new player: set `player.team_id = team_id`.
    - Optionally keep `player.team` (A/B) in sync for older logic, or leave it empty for new leagues.
- Update admin template “fixed players” section in `[app/templates/admin/dashboard.html](app/templates/admin/dashboard.html)`:
  - Use a teams dropdown when assigning a player’s team:
    - If there are no teams: show a warning like “You must register teams before adding players”.
- **Required** for UI: update `PlayerRepository.get_leaderboard`:
  - Add `joinedload(Player.team)` — this is **mandatory** once team badges are shown in the leaderboard to avoid N+1 queries. Do not leave it as optional.

---

### 5. Use teams in match creation

- Backend:
  - Extend `MatchCreate` schema in `[app/schemas/schemas.py](app/schemas/schemas.py)`:
    - Add `team_a_id: Optional[int]`, `team_b_id: Optional[int]`.
  - In `MatchService.register_match`:
    - If `team_a_id` and `team_b_id` are provided:
      - Fetch the `Team` entities from the repo.
      - Set `db_match.team_a_id/team_b_id` and copy `team_a_name/team_b_name` from `Team.name`.
    - If not provided (old leagues / backups): fall back to existing free‑text behavior.
    - **Validation**: if the league has registered teams (i.e. has adopted the new system), reject match creation if fewer than 2 teams exist in the league. Return a clear error like "You must register at least 2 teams before creating a match".
- Frontend (admin dashboard HTML/JS):
  - In `[app/templates/admin/dashboard.html](app/templates/admin/dashboard.html)` and `[app/static/js/admin_dashboard.js](app/static/js/admin_dashboard.js)`:
    - Add dropdowns to choose Team A and Team B from `teams`.
    - When saving the match, include `team_a_id`, `team_b_id` in the JSON payload (in addition to the display names if needed).
  - Optional later: when a team is selected, auto-fill the player rows for that side with the team’s registered players.

---

### 6. Backwards compatibility & data migration

- Existing player data:
  - A one‑off migration script (manual or Supabase SQL) can:
    - Create two default `Team` records per existing league based on `team_a_label` / `team_b_label`.
    - Assign `player.team_id` based on legacy `Player.team` value ('A' or 'B').
- Existing match data:
  - Leave as‑is: old matches continue to rely on `team_a_name` / `team_b_name`.
  - `team_a_id` / `team_b_id` remain `NULL` for historical matches.
- Code should always handle the “no team_id” case gracefully:
  - If `team_id` is missing, fall back to existing labels/names.

---

### 7. Public UI updates (optional but recommended)

- In `[app/templates/leaderboard.html](app/templates/leaderboard.html)` and `[app/templates/player.html](app/templates/player.html)`:
  - Show team name or a small colored badge next to the player name when `team_id` is present.
- In `[app/templates/matches.html](app/templates/matches.html)`:
  - If `team_a_id` / `team_b_id` are present, show `Team.name`; otherwise fallback to the text fields.

---

### 8. Transfer market (player transfers between teams)

- New `Transfer` model in `[app/models/models.py](app/models/models.py)`:
  - Fields:
    - `id`, `league_id`, `player_id`
    - `from_team_id` (nullable if the player had no previous team)
    - `to_team_id` (must be a team in the same league)
    - `created_at` (timestamp of the transfer)
    - `reason` (optional short text field)
  - Relationships to `League`, `Player`, and `Team` (for from/to).
- Transfer service:
  - Function such as `transfer_player(player_id, to_team_id, reason=None)`:
    - Ensures `to_team_id` belongs to the same `league_id` as the player.
    - Rejects transfers where `to_team_id` equals the current team.
    - Creates a `Transfer` record and updates `player.team_id` to `to_team_id`.
    - Does not modify any existing `MatchStat`; old matches stay linked to the old team.
- **Transfer permissions (must decide before implementation)**:
  - **Admin-only (recommended)**: only the league admin can initiate a transfer. Simpler auth model, less risk of abuse.
  - **Player-requested**: the player submits a transfer request, admin approves. Requires a `status` field on `Transfer` (pending / approved / rejected) and additional UI.
  - 👉 Default to **admin-only** unless the product explicitly requires player-initiated transfers, to avoid auth/permission complexity.
- Admin UI:
  - In admin dashboard:
    - Add a button "Transfer player to another team".
    - Show a form with:
      - Dropdown of available league teams (excluding the current team).
      - Optional reason text box.
  - In `[app/templates/player.html](app/templates/player.html)`:
    - Add a "Transfer history" table listing: date, from team → to team, reason (if present).

---

### 10. Implementation notes & improvements

1. **Migration timing**: `legacy-migration` must be drafted **alongside** `models-teams` (step 1), not left to the end. Deferring it creates data debt and risks schema drift.
2. **Color picker in admin form**: use `<input type="color">` for the team color field in the admin dashboard. Avoids typo-prone free-text hex input.
3. **Transfer permissions**: default to **admin-only** transfers. Do not expose transfer UI to players unless explicitly required — it introduces auth complexity (role checks, request/approval workflow, `Transfer.status` field).
4. **Match creation validation**: if a league has adopted the new teams system (i.e. has ≥1 registered team), block match creation when fewer than 2 teams are available. Show a clear error in both backend (422) and frontend UI.
5. **Leaderboard N+1**: `joinedload(Player.team)` in `PlayerRepository.get_leaderboard` is **required** — not optional — as soon as team badges appear in the leaderboard view.

---

### 9. Verification & tests

- Unit & integration tests:
  - Add tests in `[tests/test_repos.py](tests/test_repos.py)` for `TeamRepository`.
  - Add tests in `[tests/test_api_admin.py](tests/test_api_admin.py)` for the flow:
    - Create league teams.
    - Add players linked to teams.
    - Create a match using those teams.
  - Update any tests that rely on old match ordering or the legacy `team` field only.
- Transfer tests:
  - Ensure that calling the transfer service:
    - Creates a correct `Transfer` row (from_team_id/to_team_id).
    - Updates `player.team_id` to the new team only.
    - Does not modify historical `MatchStats` that reference the old team.
  - Verify that transferring a player to a team from another league is rejected.
- Manual QA:
  - Create a new league → register teams → add players per team → create a match using the teams → verify dropdowns and that data flows correctly to leaderboard and matches views.
  - Transfer a player from one team to another:
    - Confirm the new team appears correctly in admin/leaderboard UI.
    - Confirm old matches still show the player under the previous team, while future matches use the new team.

