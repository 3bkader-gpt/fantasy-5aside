import re
from fastapi import HTTPException
from ..models import models
from ..schemas import schemas
from ..services import points
from ..core.security import verify_password
from .interfaces import IMatchService, ICupService
from ..repositories.interfaces import ILeagueRepository, IMatchRepository, IPlayerRepository, ITeamRepository

class MatchService(IMatchService):
    def __init__(
        self,
        league_repo: ILeagueRepository,
        match_repo: IMatchRepository,
        player_repo: IPlayerRepository,
        cup_service: ICupService,
        team_repo: ITeamRepository = None,
    ):
        self.league_repo = league_repo
        self.match_repo = match_repo
        self.player_repo = player_repo
        self.cup_service = cup_service
        self.team_repo = team_repo

    def _snapshot_ranks(self, league_id: int):
        players = self.player_repo.get_leaderboard(league_id)
        for index, player in enumerate(players):
            player.previous_rank = index + 1
            self.player_repo.save(player)

    @staticmethod
    def _compute_team_scores_from_stats(stats) -> tuple[int, int]:
        team_a_score = sum(s.goals for s in stats if s.team == 'A')
        team_b_score = sum(s.goals for s in stats if s.team == 'B')
        return team_a_score, team_b_score

    def _build_combined_stats(
        self,
        league_id: int,
        stats,
        team_a_score: int,
        team_b_score: int,
    ) -> list[dict]:
        """Shared logic to resolve players, compute base points, and build combined stats."""
        team_a_base: list[dict] = []
        team_b_base: list[dict] = []

        for stat_data in stats:
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

            # Update clean sheet evaluation for GK (6 goals or fewer = clean sheet)
            if stat_data.is_gk and stat_data.goals_conceded <= 6:
                stat_data.clean_sheet = True

            base_points = points.calculate_player_points(
                goals=stat_data.goals,
                assists=stat_data.assists,
                is_winner=is_winner,
                is_draw=is_draw,
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded,
                own_goals=stat_data.own_goals,
                defensive_contribution=getattr(stat_data, "defensive_contribution", False),
            )

            bonus_bps = getattr(stat_data, 'bonus_points', 0) or 0
            stat_dict = {
                'id': player.id,
                'team': stat_data.team,
                'goals': stat_data.goals,
                'assists': stat_data.assists,
                'is_winner': is_winner,
                'base_points': base_points,
                'bonus_bps': bonus_bps,
                'stat_data': stat_data,
                'player': player,
            }
            if stat_data.team == 'A':
                team_a_base.append(stat_dict)
            else:
                team_b_base.append(stat_dict)

        combined_for_check = team_a_base + team_b_base
        player_ids = [s["id"] for s in combined_for_check]
        if len(player_ids) != len(set(player_ids)):
            raise HTTPException(status_code=400, detail="لاعب مكرر في التشكيلة")
        return combined_for_check

    def _apply_combined_stats_to_match(
        self,
        match: models.Match,
        combined_stats: list[dict],
    ) -> None:
        """Persist MatchStat rows and update player aggregates."""
        for s in combined_stats:
            player = s['player']
            stat_data = s['stat_data']
            base_points = s['base_points']
            bonus_bps = s.get('bonus_bps', 0) or 0
            full_points = base_points + bonus_bps

            db_stat = models.MatchStat(
                match_id=match.id,
                player_id=player.id,
                team=s['team'],
                goals=stat_data.goals,
                assists=stat_data.assists,
                saves=stat_data.saves,
                goals_conceded=stat_data.goals_conceded,
                own_goals=stat_data.own_goals,
                is_winner=s['is_winner'],
                is_gk=stat_data.is_gk,
                clean_sheet=stat_data.clean_sheet,
                defensive_contribution=getattr(stat_data, "defensive_contribution", False),
                points_earned=full_points,
                bonus_points=bonus_bps,
            )

            self.match_repo.db.add(db_stat)

            player.total_points += full_points
            player.total_goals += stat_data.goals
            player.total_assists += stat_data.assists
            player.total_saves += stat_data.saves
            player.total_own_goals += stat_data.own_goals
            player.total_matches += 1
            if stat_data.clean_sheet:
                player.total_clean_sheets += 1
            self.player_repo.save(player, commit=False)

    @staticmethod
    def normalize_name(name: str) -> str:
        if not name: return ""
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
        if not league:
            raise HTTPException(status_code=404, detail="League not found")

        team_a_obj = None
        team_b_obj = None

        # --- New Teams System ---
        if self.team_repo:
            registered_teams = self.team_repo.get_all_for_league(league_id)
            if registered_teams:
                # League has adopted the team system – require at least 2 teams and valid IDs
                if len(registered_teams) < 2:
                    raise HTTPException(
                        status_code=422,
                        detail="يجب تسجيل فريقين على الأقل قبل إنشاء مباراة"
                    )
                if not match_data.team_a_id or not match_data.team_b_id:
                    raise HTTPException(
                        status_code=422,
                        detail="يجب اختيار الفريق أ والفريق ب من قائمة الفرق المسجلة"
                    )
                team_a_obj = self.team_repo.get_by_id(match_data.team_a_id)
                team_b_obj = self.team_repo.get_by_id(match_data.team_b_id)
                if not team_a_obj or team_a_obj.league_id != league_id:
                    raise HTTPException(status_code=400, detail="الفريق أ غير موجود في هذا الدوري")
                if not team_b_obj or team_b_obj.league_id != league_id:
                    raise HTTPException(status_code=400, detail="الفريق ب غير موجود في هذا الدوري")

        team_a_name = team_a_obj.name if team_a_obj else match_data.team_a_name
        team_b_name = team_b_obj.name if team_b_obj else match_data.team_b_name

        team_a_score, team_b_score = self._compute_team_scores_from_stats(match_data.stats)

        # Start Transaction
        try:
            self._snapshot_ranks(league_id)

            db_match = models.Match(
                league_id=league_id,
                team_a_name=team_a_name,
                team_b_name=team_b_name,
                team_a_id=match_data.team_a_id,
                team_b_id=match_data.team_b_id,
                team_a_score=team_a_score,
                team_b_score=team_b_score
            )
            self.match_repo.save(db_match, commit=False)

            combined_stats = self._build_combined_stats(league_id, match_data.stats, team_a_score, team_b_score)
            self._apply_combined_stats_to_match(db_match, combined_stats)
            
            self.match_repo.db.commit()
            self.match_repo.db.refresh(db_match)
            
            self.cup_service.auto_resolve_cups(league_id, db_match.id)
            return db_match
        except Exception:
            self.match_repo.db.rollback()
            raise

    def update_match(self, league_id: int, match_id: int, update_data: schemas.MatchEditRequest) -> models.Match:
        league = self.league_repo.get_by_id(league_id)
        if not league:
            raise HTTPException(status_code=404, detail="League not found")

        match = self.match_repo.get_by_id(match_id)
        if not match or match.league_id != league_id:
            raise HTTPException(status_code=404, detail="Match not found")

        # الاحتفاظ بتاريخ المباراة الأصلي حتى لا تنتقل للموسم التالي بعد التعديل (الترتيب بالتاريخ)
        original_date = match.date

        try:
            self._snapshot_ranks(league_id)

            # Revert old stats
            for stat in list(match.stats):
                player = stat.player
                player.total_points = max(0, player.total_points - stat.points_earned)
                player.total_goals = max(0, player.total_goals - stat.goals)
                player.total_assists = max(0, player.total_assists - stat.assists)
                player.total_saves = max(0, player.total_saves - stat.saves)
                player.total_own_goals = max(0, player.total_own_goals - stat.own_goals)
                player.total_matches = max(0, player.total_matches - 1)
                if stat.clean_sheet:
                    player.total_clean_sheets = max(0, player.total_clean_sheets - 1)
                self.player_repo.save(player, commit=False)
                # Remove stat from session correctly to avoid conflict with cascade
                self.match_repo.db.delete(stat)
                
            # Ensure match object handles newly appended state correctly
            match.stats = []

            team_a_score, team_b_score = self._compute_team_scores_from_stats(update_data.stats)

            match.team_a_name = update_data.team_a_name
            match.team_b_name = update_data.team_b_name
            match.team_a_score = team_a_score
            match.team_b_score = team_b_score
            if getattr(update_data, "team_a_id", None) is not None:
                match.team_a_id = update_data.team_a_id
            if getattr(update_data, "team_b_id", None) is not None:
                match.team_b_id = update_data.team_b_id

            combined_stats = self._build_combined_stats(league_id, update_data.stats, team_a_score, team_b_score)
            self._apply_combined_stats_to_match(match, combined_stats)
            # استخدام التاريخ المرسل من الواجهة إن وُجد، وإلا الاحتفاظ بالأصلي (لتصحيح مباراة انتقلت لموسم خاطئ)
            if getattr(update_data, "date", None) is not None:
                from datetime import timezone
                d = update_data.date
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                match.date = d
            else:
                match.date = original_date
            self.match_repo.db.commit()
            self.match_repo.db.refresh(match)
            self.cup_service.auto_resolve_cups(league_id, match.id)
            
            return match
        except Exception:
            self.match_repo.db.rollback()
            raise

    def delete_match(self, match_id: int, league_id: int) -> bool:
        match = self.match_repo.get_by_id(match_id)
        if not match or match.league_id != league_id:
            raise HTTPException(status_code=404, detail="Match not found")
            
        try:
            self._snapshot_ranks(league_id)
                
            for stat in match.stats:
                player = stat.player
                player.total_points = max(0, player.total_points - stat.points_earned)
                player.total_goals = max(0, player.total_goals - stat.goals)
                player.total_assists = max(0, player.total_assists - stat.assists)
                player.total_saves = max(0, player.total_saves - stat.saves)
                player.total_own_goals = max(0, player.total_own_goals - stat.own_goals)
                player.total_matches = max(0, player.total_matches - 1)
                if stat.clean_sheet:
                    player.total_clean_sheets = max(0, player.total_clean_sheets - 1)
                self.player_repo.save(player, commit=False)
                
            self.match_repo.delete(match.id, commit=True) # Repository delete calls commit
            return True
        except Exception:
            self.match_repo.db.rollback()
            raise
