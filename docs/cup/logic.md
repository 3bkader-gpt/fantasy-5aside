# Cup Logic

This document describes how the cup system works: business rules, resolution behaviour, and edge cases implemented for stability.

---

## 1. Overview

The cup is a **seasonal knockout** tournament driven by player performance. There are two brackets: **goalkeeper** and **outfield**, unless there are not enough goalkeepers in the qualifying pool.

---

## 2. Generation & Seeding

### Who qualifies? Activity filter

The **top 10** players by season points are considered, but only if they are **active in that season**:

- A player is excluded if they have no `MatchStat` linked to a `Match` for the target cup season (same notion as `determine_cup_season_target` / standings scope).
- If fewer than **2** eligible players remain after filtering, no cup is created for that run and cup flags are cleared for everyone.

### Brackets and goalkeeper scarcity

- If **two or more goalkeepers** appear in the top 10, **goalkeeper** and **outfield** brackets are kept separate.
- If there are **fewer than two** goalkeepers (zero or one) in the top 10, **everyone** is placed in a single **outfield** bracket so the draw is never empty.

### Odd player counts (bye)

- If a bracket has an **odd** number of players, one player is chosen at random for a **bye** in that round.
- That player is recorded as the winner (`winner_id`) immediately and waits until all other fixtures in the round finish before the next draw.

### Team collision minimisation

Seeding runs **60** random order attempts and picks the ordering with the **fewest** same-team pairings in early rounds.

---

## 3. Resolution logic

The cup is updated automatically after each **league** match is registered.

### Single-player presence

- If **both** opponents have stats in the match: higher fantasy points wins.
- If **only one** has stats: that player wins by default.
- If **neither** has stats: the fixture stays active.

### Timeout / administrative forfeit

To avoid a stuck bracket:

- A **baseline** league match count is stored when a round opens (`league_match_count_baseline`).
- After **4 additional league matches** in the cup’s season without that fixture being decided (`current_matches - baseline >= 4`):
  - The matchup is resolved **administratively**.
  - The winner is the player **higher on the league standings** (same ordering as the leaderboard tie-break path used in code).
  - The “forfeiting” side loses cup eligibility for that run.

### Tie-breakers

When cup points are tied (including admin resolution):

1. **Team result:** player whose team **won** the match.
2. **Standings:** higher total points, then goals.
3. **Stable ID:** lower `player.id`.

### Retroactive match edits

- Once a matchup is closed (`is_active = False`), the result is treated as **final**.
- If an admin later edits match stats, the system does **not** re-open or swap winners automatically, to avoid breaking rounds that may already have advanced.

> [!IMPORTANT]
> **Co-op final removed:** there is no shared win in the final. There must be **one** winner (points or standings), even if both players are on the same team.

---

## 4. Advancement

When every fixture in a round is decided:

1. Winners are collected and re-seeded for the next round (e.g. semi-final, final).
2. The **forfeit baseline** is reset for the new round.

---

## 5. Season end & Hall of Fame

### Finalize incomplete cup

When the admin ends the season while the cup is still open:

1. `finalize_incomplete_cup` closes outstanding fixtures using administrative rules.
2. Remaining players are resolved **down the tree** using standings until each bracket has a champion.
3. **Outfield** and **goalkeeper** winners are written to the `HallOfFame` row for that season (where applicable).

`CupMatchup` rows for ended seasons remain in the database by `season_number`; see `docs/league/logic.md` for how this interacts with season rollover and the public cup page.

---

## 6. Season sync (display vs resolution)

### `get_active_cup_season`

- **Public cup UI** (`query_cup_for_display`) uses the league’s **current** `season_number` only—no fallback to the previous season (empty state until a new cup is generated).
- **Auto-resolution and bracket logic** use `get_active_cup_season`: they look for **active** matchups on the current season first; if none and `season_number > 1`, they check the **previous** season so a bracket that started before rollover can still complete.

This split keeps the **active** UI aligned with the current season while avoiding stuck cups across a season boundary.

---

## Technical reference

| Area | Location |
|------|----------|
| Activity filter, GK merge, baselines | `app/use_cases/generate_cup.py` |
| Forfeit (4 matches), co-op removal, finalize | `app/services/cup_service.py` |
| Active cup season helper | `app/domain/season_boundary.py` |
| Cup display queries | `app/queries/cup_queries.py` |
| Tests | `tests/test_cup.py` |

---

*Last updated March 2026.*
