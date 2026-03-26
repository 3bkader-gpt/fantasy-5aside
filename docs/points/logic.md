# Points calculation logic

Fantasy points per **`MatchStat`** are computed by composing **strategy classes** (Strategy pattern). Primary code: `app/services/points.py`; orchestration happens inside **`MatchService`** when saving match stats.

**Numeric source of truth:** this file + `points.py`. Do not duplicate scoring weights elsewhere unless they link back here.

---

## 1. `PointsContext`

Input dataclass: `goals`, `assists`, `is_winner`, `is_draw`, `is_gk`, `clean_sheet`, `saves`, `goals_conceded`, `own_goals`, optional `defensive_contribution`.

Production match flows build equivalent context from each stat row and the match result (not necessarily via `calculate_player_points(MatchCreate)`).

---

## 2. Strategies (order matters)

The calculator runs **all** registered strategies and **sums** results. All arithmetic uses **integers** (no fractional points from strategies).

| Strategy | Rule (exact) |
|----------|----------------|
| `ParticipationPoints` | +2 for being listed in the match |
| `GoalPoints` | +3 per goal (outfield), +6 per goal (GK) |
| `AssistPoints` | +2 per assist (outfield), +4 per assist (GK) |
| `WinPoints` | Win +2, draw +1, loss −1 |
| `CleanSheetPoints` | See **§2.1** |
| `SavePoints` | GK only: **`(saves // 3) * 2`** — integer division (floor toward zero for non‑negative saves); remainder saves earn **0**. Example: 5 saves → +2. |
| `GoalsConcededPenalty` | GK only: **`-(goals_conceded // 4)`** |
| `OwnGoalPenalty` | −1 per own goal |
| `DefensiveContributionPoints` | +2 when `defensive_contribution` and **not** GK |

### 2.1 Clean sheet (`CleanSheetPoints`)

Applies only when `clean_sheet` is true on the context.

- **Outfield:** +2.
- **Goalkeeper:** banded by `goals_conceded` on that line:
  - `<= 2` → +10
  - `<= 6` → +4
  - otherwise → +0

### 2.2 Test helper: `calculate_player_points(MatchCreate)`

Unit tests use `PointsCalculator.calculate_player_points`. For **goalkeepers only**, if `clean_sheet` is not set on the payload, the helper may set `clean_sheet` to true when `goals_conceded <= 6` (see `points.py`). That is **test/API-shape convenience**; persisted `MatchStat` rows use the flags the admin saved—align admin UI with the same rules to avoid surprises.

---

## 3. Negative points and season totals

- There is **no** `max(0, …)` on the **strategy sum**. Base points for a match can be **negative** (e.g. heavy loss, conceded bands, own goals). See `tests/test_points.py` (`test_strategy_sum_can_be_negative`).
- **`MatchService`** stores `points_earned = base_points + bonus_points` and updates `player.total_points` (and `all_time_*` when applicable) with **`+= full_points`** **without** clamping to zero. So a player’s **season aggregate can go negative** if poor performances add up.
- **Revert on match edit/delete:** when subtracting a prior stat from totals, the code uses `max(0, player.total_points - stat.points_earned)` (and similar for other counters). That only prevents **revert arithmetic** from driving totals below zero in that step; it does **not** impose a global “floor at zero” on normal `+=` updates.

---

## 4. Stored total and bonuses

`MatchService` sets `points_earned = base_points + bonus_points`, where `base_points` comes from the strategy calculator and **`bonus_points`** from the request (e.g. MVP voting). **`is_captain`** on `MatchStat` is display/legacy only—it is **not** multiplied in `points.py`; reintroduce multipliers explicitly if product requires them.

---

## 5. Changing the rules

- Add a class implementing `PointsStrategy` and register it on the **`PointsCalculator`** instance used by match flows (and mirror any labels in `get_points_breakdown` if UI uses it).
- Run **`tests/test_points.py`** after changes.

---

## 6. Related docs

- Match lifecycle, voting, MVP bonuses: `docs/match/logic.md`, `docs/league/logic.md`.
- No separate DB table for “points rules”; behaviour is code-defined.
