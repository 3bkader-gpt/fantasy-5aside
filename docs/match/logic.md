# Match & Scoring Logic

This document covers match registration, per-player points, and MVP voting—the core rules that keep league scoring fair.

---

## 1. Match lifecycle

A match goes through three stages:

1. **Registration:** the admin enters teams, scores, and per-player stats.
2. **Voting:** MVP rounds run after the match is played.
3. **Close:** when voting finishes, bonus points are applied permanently and count toward the season.

---

## 2. Scoring system

**All numeric weights** (goals, assists, win/draw/loss, clean sheets, saves chunks, conceded penalties, own goals, defensive contribution) are defined in code by the strategy stack in **`app/services/points.py`** and documented in **`docs/points/logic.md`**. Treat that doc as the single place for “how many points for X” so this file and the implementation never drift.

**Goalkeeper role for scoring (per match):** GK-specific rules apply when that **match line** marks the player as goalkeeper (`MatchStat.is_gk`, i.e. the admin’s `is_gk` on the stat row). They do **not** follow `Player.default_is_gk` alone for that calculation path—always set `is_gk` correctly on the match stats.

---

## 3. Voting & MVP

The app uses **round-based** voting to pick the top three performers in a match.

### Round bonuses

- **Round 1 (1st place):** **+3** bonus points.
- **Round 2 (2nd):** **+2**.
- **Round 3 (3rd):** **+1**.

### Exclusion

A player who wins a round is **removed** from later rounds in the same match so others can be rewarded.

### Integrity controls

1. **No self-vote.**
2. **Device fingerprint:** one vote per browser/device per round.
3. **IP cap:** at most **two** votes from the same IP per round (household / shared connection).
4. **Participation:** only players who were in the match (or are otherwise allowed) can vote.
5. **Whitelist:** the admin can restrict voting to a specific list of player IDs for a given match.

### MVP tie when closing a round

If two or more candidates have the **same** vote count, the winner is chosen **deterministically** from match performance: higher `MatchStat.points_earned` for that match, then higher `goals`, then **lower** `goals_conceded`, then **lower** `candidate_id` (player id). Anyone tied on votes but missing a stat row for that match is ranked last among the tied group.

If you still want a **clean re-vote** (e.g. policy or optics), use **Reset votes for current round** in admin (`reset_current_round_votes` / admin voting reset for that match) and run the round again.

### Match edit while voting is open

`update_match` rebuilds `MatchStat` rows from the new payload but **votes** reference `Player` + `Match`, not `MatchStat`. While rounds **1–3** are open, after each successful edit the app **removes votes in the current round** whose **voter** or **candidate** is no longer in the new participant set, so counts stay aligned with the roster.

If you change stats without changing who is on the pitch, existing votes remain. When in doubt—especially after large roster changes—use **reset current round votes** before closing the round.

---

## 4. Admin operations

### Edit / delete matches

- On edit, the system **reverts** previously applied points from player totals, then applies the new breakdown.
- **Current-season** matches affect `total_*`; **past-season** matches affect `all_time_*` only (see service layer for exact rules).
- If **MVP voting** is open (rounds 1–3), stale votes for voters or candidates **dropped from the new lineup** are deleted automatically for the **current** round (see **Match edit while voting is open** above).

### Recompute totals

**Recompute Totals** rebuilds all player totals from stored match data—useful after bugs or manual DB fixes.

---

## 5. Technical notes

- **Captain:** `is_captain` exists in the schema and UI but **does not** multiply points in code today; it is visual / badge only.
- **Implementation:** `app/services/points.py` uses a strategy-style layout so point weights can change without rewriting the whole pipeline.
