from fastapi import HTTPException
from ..models import models
from ..schemas import schemas
from ..services import points
from ..core.security import verify_password
from .interfaces import IMatchService, ICupService
from ..repositories.interfaces import ILeagueRepository, IMatchRepository, IPlayerRepository

class MatchService(IMatchService):
    def __init__(self, league_repo: ILeagueRepository, match_repo: IMatchRepository, player_repo: IPlayerRepository, cup_service: ICupService):
        self.league_repo = league_repo
        self.match_repo = match_repo
        self.player_repo = player_repo
        self.cup_service = cup_service

    def _snapshot_ranks(self, league_id: int):
        players = self.player_repo.get_leaderboard(league_id)
        for index, player in enumerate(players):
            player.previous_rank = index + 1
            self.player_repo.save(player)

    @staticmethod
    def normalize_name(name: str) -> str:
        if not name: return ""
        import re
        # 1. Remove tashkeel
        name = re.sub(r'[\u064B-\u0652]', '', name)
        # 2. Unify Alef
        name = re.sub(r'[أإآا]', 'ا', name)
        # 3. Unify Yeh
        name = re.sub(r'ى', 'ي', name)
        # 4. Unify Teh Marbuta
        name = re.sub(r'ة', 'ه', name)
        # 5. Collapse spaces
        name = re.sub(r'\s+', ' ', name)
        return name.strip()

    def register_match(self, league_id: int, match_data: schemas.MatchCreate) -> models.Match:
        league = self.league_repo.get_by_id(league_id)
        if not league or not verify_password(match_data.admin_password, league.admin_password):
            raise HTTPException(status_code=401, detail="كلمة سر الإدارة غير صحيحة")

        team_a_score = sum(s.goals for s in match_data.stats if s.team == 'A')
        team_b_score = sum(s.goals for s in match_data.stats if s.team == 'B')

        self._snapshot_ranks(league_id)

        db_match = models.Match(
            league_id=league_id,
            team_a_name=match_data.team_a_name,
            team_b_name=match_data.team_b_name,
            team_a_score=team_a_score,
            team_b_score=team_b_score
        )
        self.match_repo.save(db_match)

        # Phase 1: Collect base stats
        team_a_base = []
        team_b_base = []

        for stat_data in match_data.stats:
            player_name = self.normalize_name(stat_data.player_name)
            
            if not player_name:
                continue

            player = self.player_repo.get_by_name(league_id, player_name)
            
            if not player:
                player = self.player_repo.create(player_name, league_id)

            is_winner = False
            if stat_data.team == 'A' and team_a_score > team_b_score:
                is_winner = True
            elif stat_data.team == 'B' and team_b_score > team_a_score:
                is_winner = True
                
            is_draw = team_a_score == team_b_score
            base_points = points.calculate_player_points(
                goals=stat_data.goals,
                assists=stat_data.assists,
                is_winner=is_winner,
                is_draw=is_draw,
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded
            )

            stat_dict = {
                'id': player.id,
                'team': stat_data.team,
                'goals': stat_data.goals,
                'assists': stat_data.assists,
                'is_winner': is_winner,
                'base_points': base_points,
                'stat_data': stat_data,
                'player': player
            }
            if stat_data.team == 'A':
                team_a_base.append(stat_dict)
            else:
                team_b_base.append(stat_dict)

        # Phase 2: Calculate bonus points
        bonuses = points.calculate_bonus_points(team_a_base, team_b_base)

        # Phase 3: Apply bonuses, save stats, save updates
        combined_stats = team_a_base + team_b_base
        for s in combined_stats:
            player = s['player']
            stat_data = s['stat_data']
            bonus = bonuses.get(player.id, 0)
            total_points = s['base_points'] + bonus
            
            db_stat = models.MatchStat(
                match_id=db_match.id,
                player_id=player.id,
                team=s['team'],
                goals=stat_data.goals,
                assists=stat_data.assists,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded,
                is_winner=s['is_winner'],
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                points_earned=total_points,
                bonus_points=bonus
            )
            
            self.match_repo.db.add(db_stat)

            player.total_points += total_points
            player.total_goals += stat_data.goals
            player.total_assists += stat_data.assists
            player.total_saves += stat_data.saves
            if stat_data.clean_sheet:
                player.total_clean_sheets += 1
            self.player_repo.save(player)

        self.match_repo.db.commit()
        self.cup_service.auto_resolve_cups(league_id, db_match.id)
        
        return db_match

    def update_match(self, league_id: int, match_id: int, update_data: schemas.MatchEditRequest) -> models.Match:
        league = self.league_repo.get_by_id(league_id)
        if not league or not verify_password(update_data.admin_password, league.admin_password):
            raise HTTPException(status_code=401, detail="كلمة سر الإدارة غير صحيحة")

        match = self.match_repo.get_by_id(match_id)
        if not match or match.league_id != league_id:
            raise HTTPException(status_code=404, detail="Match not found")

        self._snapshot_ranks(league_id)

        # Revert old stats
        for stat in list(match.stats):
            player = stat.player
            player.total_points = max(0, player.total_points - stat.points_earned)
            player.total_goals = max(0, player.total_goals - stat.goals)
            player.total_assists = max(0, player.total_assists - stat.assists)
            player.total_saves = max(0, player.total_saves - stat.saves)
            if stat.clean_sheet:
                player.total_clean_sheets = max(0, player.total_clean_sheets - 1)
            self.player_repo.save(player)
            
        # Clear out old match stats completely linked to this match
        self.match_repo.delete_match_stats(match_id)

        # Ensure match object handles newly appended state correctly
        match.stats = []

        team_a_score = sum(s.goals for s in update_data.stats if s.team == 'A')
        team_b_score = sum(s.goals for s in update_data.stats if s.team == 'B')

        match.team_a_name = update_data.team_a_name
        match.team_b_name = update_data.team_b_name
        match.team_a_score = team_a_score
        match.team_b_score = team_b_score

        # Phase 1: Collect base stats
        team_a_base = []
        team_b_base = []

        for stat_data in update_data.stats:
            player_name = stat_data.player_name.strip()
            player = self.player_repo.get_by_name(league_id, player_name)
            
            if not player:
                player = self.player_repo.create(player_name, league_id)

            is_winner = False
            if stat_data.team == 'A' and team_a_score > team_b_score:
                is_winner = True
            elif stat_data.team == 'B' and team_b_score > team_a_score:
                is_winner = True
                
            is_draw = team_a_score == team_b_score
            base_points = points.calculate_player_points(
                goals=stat_data.goals,
                assists=stat_data.assists,
                is_winner=is_winner,
                is_draw=is_draw,
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded
            )

            stat_dict = {
                'id': player.id,
                'team': stat_data.team,
                'goals': stat_data.goals,
                'assists': stat_data.assists,
                'is_winner': is_winner,
                'base_points': base_points,
                'stat_data': stat_data,
                'player': player
            }
            if stat_data.team == 'A':
                team_a_base.append(stat_dict)
            else:
                team_b_base.append(stat_dict)

        # Phase 2: Calculate bonus points
        bonuses = points.calculate_bonus_points(team_a_base, team_b_base)

        # Phase 3: Apply bonuses, save stats, save updates
        combined_stats = team_a_base + team_b_base
        for s in combined_stats:
            player = s['player']
            stat_data = s['stat_data']
            bonus = bonuses.get(player.id, 0)
            total_points = s['base_points'] + bonus

            db_stat = models.MatchStat(
                match_id=match.id,
                player_id=player.id,
                team=s['team'],
                goals=stat_data.goals,
                assists=stat_data.assists,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded,
                is_winner=s['is_winner'],
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                points_earned=total_points,
                bonus_points=bonus
            )
            
            self.match_repo.db.add(db_stat)

            player.total_points += total_points
            player.total_goals += stat_data.goals
            player.total_assists += stat_data.assists
            player.total_saves += stat_data.saves
            if stat_data.clean_sheet:
                player.total_clean_sheets += 1
            self.player_repo.save(player)

        self.match_repo.db.commit()
        self.cup_service.auto_resolve_cups(league_id, match.id)
        
        return match

    def delete_match(self, match_id: int, league_id: int) -> bool:
        match = self.match_repo.get_by_id(match_id)
        
        if not match or match.league_id != league_id:
            raise HTTPException(status_code=404, detail="Match not found")
            
        self._snapshot_ranks(league_id)
            
        for stat in match.stats:
            player = stat.player
            player.total_points = max(0, player.total_points - stat.points_earned)
            player.total_goals = max(0, player.total_goals - stat.goals)
            player.total_assists = max(0, player.total_assists - stat.assists)
            player.total_saves = max(0, player.total_saves - stat.saves)
            if stat.clean_sheet:
                player.total_clean_sheets = max(0, player.total_clean_sheets - 1)
            self.player_repo.save(player)
            
        self.match_repo.delete(match.id)
        return True
