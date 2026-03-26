# Player Stats, Badges & Analytics

This document explains how player statistics, achievements (badges), and analytics are derived for profiles and leaderboards.

---

## 1. Achievements (badges)

Badges are evaluated **on demand** from match history. They are **not** stored as separate rows; recomputing on read keeps them consistent with the underlying data.

### Badges: evaluation cost and leaderboard loading

Badge rules run **in memory** over each player’s `MatchStat` list (and some use denormalized `Player` counters). On the public **leaderboard**, players are loaded with **eager-loaded** `match_stats` and each row’s `match` (`joinedload` in `PlayerRepository.get_leaderboard`), so badge evaluation does **not** cause an **N+1** burst of per-player history queries. If you add heavier per-screen work for many players (e.g. full analytics charts for dozens of rows at once), keep the same idea: **bulk load** or explicit `joinedload` / batch queries—do not lazy-load history per row in a loop.

### Available badges

- **Sniper:** **6+ goals** in a **single** match.
- **The Rocket:** **5+ goals** in each of **3 consecutive logged appearances** (three consecutive `MatchStat` rows for that player by match date). Skipped league fixtures do **not** appear in the sequence—“consecutive” is **not** “every scheduled league match.”
- **The Wall:** **3+ clean sheets** in the player’s career (per app rules).
- **Playmaker:** **15+ assists** career total.
- **Clown:** at least **one own goal** in career stats.

---

## 2. Analytics service

`AnalyticsService` turns raw match rows into streaks, form, and charts.

**Appearances vs league calendar:** Streaks, The Rocket, form strings, and the points-by-match chart all use the player’s **`MatchStat` history** (matches they actually played in), ordered by match date. There are no placeholder rows for games they missed, so an absence does not “reset” a streak in the sense of a zero row—it simply **omits** that match from the sequence.

### Streaks

For each player, the service tracks **max** and **current** streaks for:

- **Goals:** consecutive matches with at least one goal.
- **Wins:** consecutive matches where the player’s team won.
- **Clean sheets:** consecutive matches with no goals conceded (or within GK clean-sheet rules).
- **Unbeaten:** consecutive matches without a loss (wins and draws).

### Form

The last **five appearances** (last five `MatchStat` rows by match date) are shown as **W / D / L**, newest first.

### Points-by-match chart

- Each point is one **appearance**: the points that player earned in that match.
- **Colour rules** (per match, comparing that player’s points to **all `MatchStat` rows in the same match**: `max` / `min` of `points_earned` in that fixture):
  - **Green:** this player’s points equal **`max`** **and** `points_earned > 0`.
  - **Red:** this player’s points equal **`min`** **and** there is **more than one** stat line in the match (`len(match.stats) > 1`).
  - **Grey:** otherwise (strictly between min and max, or edge cases below).

**Tie / edge behaviour:**

- **Everyone ties with the same positive points** (e.g. whole team on draw points): `max == min > 0` → **everyone is green** (not grey).
- **Everyone ties at zero** with multiple players in the match: **everyone is red** (minimum branch, more than one stat line in the match).
- **Only one player** in the match (a single stat row): red is never chosen (length condition fails); non-zero points → **green**, zero → **grey**.

Do **not** assume “`max == min` always means grey”; the implementation uses the branches above.

---

## 3. Head-to-head

Two players can be compared side by side:

- **Shared matches:** all matches both appeared in (same team or opponents).
- **Totals:** points, goals, assists, points-per-match.
- **Radar chart:** relative strengths (goals, assists, saves, defence-style signals, scoring rate).

---

## 4. League records

League-wide highlights for the current season (where implemented):

- **Highest-scoring match:** most total goals.
- **“Most exciting” match:** tight high-scoring games (smallest margin with high total goals—per product definition in code).
- **Single-match points record:** best individual performance in one game.
- **Top contributors:** strong G+A or points-per-match rates.

---

## 5. Stats sync

- `total_*` fields update when matches are saved or closed.
- When a **season ends**, totals roll into `all_time_*` and season counters reset (see `docs/league/logic.md`).
- **Recompute Totals** can rebuild everything from match rows if counters drift.
