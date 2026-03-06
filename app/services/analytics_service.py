"""
Analytics service: player stats, form, chart data.
Badges use single source of truth: achievements.achievement_service (aligned with "كيف تلعب؟").
"""
from typing import List, Optional
from ..models import models
from .interfaces import IAnalyticsService
from ..repositories.interfaces import IPlayerRepository, IMatchRepository

class AnalyticsService(IAnalyticsService):
    def __init__(self, player_repo: IPlayerRepository, match_repo: IMatchRepository):
        self.player_repo = player_repo
        self.match_repo = match_repo
        
    def get_player_analytics(self, player_id: int, league_id: int):
        player = self.player_repo.get_by_id(player_id)
        if not player or player.league_id != league_id:
            return None

        history = self.match_repo.get_player_history(player.id)

        total_matches = len(history)
        wins = sum(1 for stat in history if stat.is_winner)
        
        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
        total_goals_assists_all_time = player.all_time_goals + player.all_time_assists + player.total_goals + player.total_assists
        ga_per_match = (total_goals_assists_all_time / total_matches) if total_matches > 0 else 0

        # Sort history properly by match date (desc for UI)
        history_desc = sorted(history, key=lambda s: s.match.date, reverse=True)

        # Badges: use single source of truth (achievements) aligned with "كيف تلعب؟"
        from .achievements import achievement_service
        badges = achievement_service.get_earned_badges(player, history_desc)

        # Get chart data using the already fetched history
        form_and_chart = self.get_player_form_and_chart_data(player_id, league_id, history=history)

        return {
            "player": player,
            "history": history_desc,
            "total_matches": total_matches,
            "win_rate": round(win_rate, 2),
            "ga_per_match": round(ga_per_match, 2),
            "badges": badges,
            "form_and_chart": form_and_chart
        }

    def get_player_form_and_chart_data(self, player_id: int, league_id: int, history: List[models.MatchStat] = None):
        if history is None:
            player = self.player_repo.get_by_id(player_id)
            if not player or player.league_id != league_id:
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
