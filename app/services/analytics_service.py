"""
Analytics service: player stats, form, chart data.
Badges use single source of truth: achievements.achievement_service (aligned with "كيف تلعب؟").
"""
from typing import List, Optional, Dict, Any
from ..models import models
from .interfaces import IAnalyticsService
from ..repositories.interfaces import IPlayerRepository, IMatchRepository


class AnalyticsService(IAnalyticsService):
    def __init__(self, player_repo: IPlayerRepository, match_repo: IMatchRepository) -> None:
        self.player_repo = player_repo
        self.match_repo = match_repo

    def compute_streaks(self, history: List[models.MatchStat]) -> Dict[str, Dict[str, int]]:
        """Compute current and max streaks for goals, wins, clean sheets, and unbeaten runs."""
        if not history:
            return {
                "goals": {"current": 0, "max": 0},
                "wins": {"current": 0, "max": 0},
                "clean_sheets": {"current": 0, "max": 0},
                "unbeaten": {"current": 0, "max": 0},
            }

        # Ensure chronological order (oldest -> newest)
        history_chron = sorted(
            [s for s in history if getattr(s.match, "date", None) is not None],
            key=lambda s: s.match.date,
        )

        current_goals = current_wins = current_cs = current_unbeaten = 0
        max_goals = max_wins = max_cs = max_unbeaten = 0

        for stat in history_chron:
            goals = getattr(stat, "goals", 0) or 0
            clean_sheet = bool(getattr(stat, "clean_sheet", False))
            is_winner = bool(getattr(stat, "is_winner", False))

            # Goal streak: match with at least one goal
            if goals > 0:
                current_goals += 1
            else:
                max_goals = max(max_goals, current_goals)
                current_goals = 0

            # Win streak: player marked as winner in that match
            if is_winner:
                current_wins += 1
            else:
                max_wins = max(max_wins, current_wins)
                current_wins = 0

            # Clean sheet streak
            if clean_sheet:
                current_cs += 1
            else:
                max_cs = max(max_cs, current_cs)
                current_cs = 0

            # Unbeaten streak: win or draw (any non-loss)
            match = stat.match
            is_draw = bool(
                match
                and getattr(match, "team_a_score", None) is not None
                and match.team_a_score == match.team_b_score
            )
            if is_winner or is_draw:
                current_unbeaten += 1
            else:
                max_unbeaten = max(max_unbeaten, current_unbeaten)
                current_unbeaten = 0

        # Final update for trailing streaks
        max_goals = max(max_goals, current_goals)
        max_wins = max(max_wins, current_wins)
        max_cs = max(max_cs, current_cs)
        max_unbeaten = max(max_unbeaten, current_unbeaten)

        return {
            "goals": {"current": current_goals, "max": max_goals},
            "wins": {"current": current_wins, "max": max_wins},
            "clean_sheets": {"current": current_cs, "max": max_cs},
            "unbeaten": {"current": current_unbeaten, "max": max_unbeaten},
        }

    def get_player_analytics(self, player_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        player = self.player_repo.get_by_id_for_league(league_id, player_id)
        if not player:
            return None

        history = self.match_repo.get_player_history(player.id)

        total_matches = len(history)
        wins = sum(1 for stat in history if stat.is_winner)

        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
        total_goals_assists_all_time = (
            (player.all_time_goals or 0)
            + (player.all_time_assists or 0)
            + (player.total_goals or 0)
            + (player.total_assists or 0)
        )
        ga_per_match = (total_goals_assists_all_time / total_matches) if total_matches > 0 else 0

        # Sort history properly by match date (desc for UI)
        history_desc = sorted(history, key=lambda s: s.match.date, reverse=True)

        # Badges: use single source of truth (achievements) aligned with "كيف تلعب؟"
        from .achievements import achievement_service

        badges = achievement_service.get_earned_badges(player, history_desc)

        # Get chart data using the already fetched history
        form_and_chart = self.get_player_form_and_chart_data(player_id, league_id, history=history)

        streaks = self.compute_streaks(history)

        return {
            "player": player,
            "history": history_desc,
            "total_matches": total_matches,
            "win_rate": round(win_rate, 2),
            "ga_per_match": round(ga_per_match, 2),
            "badges": badges,
            "form_and_chart": form_and_chart,
            "streaks": streaks,
        }

    def get_player_form_and_chart_data(self, player_id: int, league_id: int, history: List[models.MatchStat] = None):
        if history is None:
            player = self.player_repo.get_by_id_for_league(league_id, player_id)
            if not player:
                return None
            # Chronological order for chart (Oldest to Newest)
            history = self.match_repo.get_player_history(player.id)
        
        # Chronological sort for chart
        history_chron = sorted(history, key=lambda s: s.match.date)

        chart_labels = []
        chart_data = []
        point_colors = []
        
        for stat in history_chron:
            match = stat.match
            chart_labels.append(match.date.strftime("%m/%d"))
            chart_data.append(stat.points_earned)
            
            # Determine Top/Bottom scorer in THAT match
            match_points = [s.points_earned for s in match.stats]
            if not match_points:
                point_colors.append("#6c757d") # Normal gray
                continue
                
            max_p = max(match_points)
            min_p = min(match_points)
            
            if stat.points_earned == max_p and stat.points_earned > 0:
                point_colors.append("#2ecc71") # Green (Top)
            elif stat.points_earned == min_p and len(match_points) > 1:
                point_colors.append("#e74c3c") # Red (Bottom)
            else:
                point_colors.append("#6c757d") # Gray

        # Form history (Last 5 matches, outcome)
        # Outcome: Win, Draw, Loss (determined by match score)
        recent_history = sorted(history, key=lambda s: s.match.date, reverse=True)[:5]
        form_history = []
        for stat in recent_history:
            if stat.is_winner:
                form_history.append('W')
            elif stat.match.team_a_score == stat.match.team_b_score:
                form_history.append('D')
            else:
                form_history.append('L')

        return {
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "point_colors": point_colors,
            "form_history": list(reversed(form_history)) # Show in order: Oldest to Newest in UI usually, or stay consistent. 
            # Prompt says "last 5 match outcomes", usually read left to right (Newest on right).
        }

    def get_head_to_head(self, player1_id: int, player2_id: int, league_id: int) -> Dict[str, Any] | None:
        if player1_id == player2_id:
            return None

        p1 = self.player_repo.get_by_id_for_league(league_id, player1_id)
        p2 = self.player_repo.get_by_id_for_league(league_id, player2_id)
        if not p1 or not p2:
            return None

        h1 = self.match_repo.get_player_history(p1.id)
        h2 = self.match_repo.get_player_history(p2.id)

        agg1 = {
            "points": sum(s.points_earned for s in h1),
            "goals": sum(getattr(s, "goals", 0) or 0 for s in h1),
            "assists": sum(getattr(s, "assists", 0) or 0 for s in h1),
            "clean_sheets": sum(1 for s in h1 if getattr(s, "clean_sheet", False)),
            "matches": len(h1),
        }
        agg2 = {
            "points": sum(s.points_earned for s in h2),
            "goals": sum(getattr(s, "goals", 0) or 0 for s in h2),
            "assists": sum(getattr(s, "assists", 0) or 0 for s in h2),
            "clean_sheets": sum(1 for s in h2 if getattr(s, "clean_sheet", False)),
            "matches": len(h2),
        }

        by_match1: Dict[int, models.MatchStat] = {s.match_id: s for s in h1 if getattr(s, "match_id", None)}
        by_match2: Dict[int, models.MatchStat] = {s.match_id: s for s in h2 if getattr(s, "match_id", None)}
        shared_ids = sorted(set(by_match1.keys()) & set(by_match2.keys()))

        shared_matches = []
        for mid in shared_ids:
            s1 = by_match1[mid]
            s2 = by_match2[mid]
            m = s1.match or s2.match
            winner = None
            if s1.points_earned > s2.points_earned:
                winner = "p1"
            elif s2.points_earned > s1.points_earned:
                winner = "p2"
            shared_matches.append(
                {
                    "match_id": mid,
                    "date": m.date if m else None,
                    "score": f"{m.team_a_score}-{m.team_b_score}" if m else "",
                    "p1_points": s1.points_earned,
                    "p2_points": s2.points_earned,
                    "winner": winner,
                }
            )

        radar1 = [
            agg1["goals"],
            agg1["assists"],
            sum(getattr(s, "saves", 0) or 0 for s in h1),
            agg1["clean_sheets"],
            round(agg1["points"] / agg1["matches"], 2) if agg1["matches"] > 0 else 0,
        ]
        radar2 = [
            agg2["goals"],
            agg2["assists"],
            sum(getattr(s, "saves", 0) or 0 for s in h2),
            agg2["clean_sheets"],
            round(agg2["points"] / agg2["matches"], 2) if agg2["matches"] > 0 else 0,
        ]

        return {
            "player1": {"id": p1.id, "name": p1.name, "aggregates": agg1, "radar": radar1},
            "player2": {"id": p2.id, "name": p2.name, "aggregates": agg2, "radar": radar2},
            "shared_matches": shared_matches,
        }

    def get_league_stats(self, league_id: int) -> Dict[str, Any]:
        """Aggregate league-wide stats for the current season."""
        matches = self.match_repo.get_all_for_league(league_id)
        total_matches = len(matches)

        total_goals = 0
        total_assists = 0
        total_saves = 0

        highest_goal_match: Optional[models.Match] = None
        highest_goal_sum = -1

        most_exciting_match: Optional[models.Match] = None
        best_exciting_score: Optional[tuple[int, int]] = None  # (diff, -total_goals)

        best_single_game: Optional[models.MatchStat] = None

        # Per-player aggregates for per-match contribution
        per_player_stats: Dict[int, Dict[str, float]] = {}

        for match in matches:
            if match.team_a_score is not None and match.team_b_score is not None:
                goal_sum = (match.team_a_score or 0) + (match.team_b_score or 0)
                total_goals += goal_sum

                if goal_sum > highest_goal_sum:
                    highest_goal_sum = goal_sum
                    highest_goal_match = match

                diff = abs((match.team_a_score or 0) - (match.team_b_score or 0))
                key = (diff, -goal_sum)
                if best_exciting_score is None or key < best_exciting_score:
                    best_exciting_score = key
                    most_exciting_match = match

            for stat in match.stats:
                assists = getattr(stat, "assists", 0) or 0
                saves = getattr(stat, "saves", 0) or 0
                total_assists += assists
                total_saves += saves

                if best_single_game is None or stat.points_earned > best_single_game.points_earned:
                    best_single_game = stat

                pid = stat.player_id
                agg = per_player_stats.setdefault(
                    pid, {"points": 0.0, "goals": 0.0, "assists": 0.0, "matches": 0.0}
                )
                agg["points"] += stat.points_earned
                agg["goals"] += getattr(stat, "goals", 0) or 0
                agg["assists"] += assists
                agg["matches"] += 1

        avg_goals_per_match = (total_goals / total_matches) if total_matches > 0 else 0.0

        # Build records
        highest_goals_record: Optional[Dict[str, Any]] = None
        if highest_goal_match is not None:
            highest_goals_record = {
                "match_id": highest_goal_match.id,
                "date": highest_goal_match.date,
                "score": f"{highest_goal_match.team_a_score}-{highest_goal_match.team_b_score}",
                "team_a_name": highest_goal_match.team_a_name,
                "team_b_name": highest_goal_match.team_b_name,
                "total_goals": (highest_goal_match.team_a_score or 0) + (highest_goal_match.team_b_score or 0),
            }

        most_exciting_record: Optional[Dict[str, Any]] = None
        if most_exciting_match is not None:
            diff = abs(
                (most_exciting_match.team_a_score or 0) - (most_exciting_match.team_b_score or 0)
            )
            most_exciting_record = {
                "match_id": most_exciting_match.id,
                "date": most_exciting_match.date,
                "score": f"{most_exciting_match.team_a_score}-{most_exciting_match.team_b_score}",
                "team_a_name": most_exciting_match.team_a_name,
                "team_b_name": most_exciting_match.team_b_name,
                "point_diff": diff,
            }

        single_game_record: Optional[Dict[str, Any]] = None
        if best_single_game is not None:
            m = best_single_game.match
            single_game_record = {
                "match_id": best_single_game.match_id,
                "player_id": best_single_game.player_id,
                "player_name": best_single_game.player.name if best_single_game.player else "",
                "date": m.date if m else None,
                "points": best_single_game.points_earned,
            }

        # Best per-match contribution players (by points per match, top 3)
        best_contributors: list[Dict[str, Any]] = []
        if per_player_stats:
            # We need player objects; reuse player_repo
            all_players = {p.id: p for p in self.player_repo.get_all_for_league(league_id)}
            scored = []
            for pid, agg in per_player_stats.items():
                matches_played = agg["matches"]
                if matches_played <= 0:
                    continue
                ppm = agg["points"] / matches_played
                ga_per_match = (agg["goals"] + agg["assists"]) / matches_played
                scored.append(
                    {
                        "player_id": pid,
                        "player_name": all_players.get(pid).name if all_players.get(pid) else "",
                        "points_per_match": round(ppm, 2),
                        "ga_per_match": round(ga_per_match, 2),
                        "matches": int(matches_played),
                    }
                )
            scored.sort(key=lambda x: x["points_per_match"], reverse=True)
            best_contributors = scored[:3]

        return {
            "totals": {
                "matches": total_matches,
                "goals": total_goals,
                "assists": total_assists,
                "saves": total_saves,
                "avg_goals_per_match": round(avg_goals_per_match, 2),
            },
            "records": {
                "highest_scoring_match": highest_goals_record,
                "most_exciting_match": most_exciting_record,
                "single_game_points_record": single_game_record,
                "best_contributors": best_contributors,
            },
        }
