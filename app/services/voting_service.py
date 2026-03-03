from typing import List, Dict, Any, Optional
from ..models import models
from ..schemas import schemas
from ..repositories.interfaces import IVotingRepository, IMatchRepository, IPlayerRepository
from .interfaces import IVotingService
from sqlalchemy import text

class VotingService(IVotingService):
    def __init__(
        self, 
        voting_repo: IVotingRepository, 
        match_repo: IMatchRepository,
        player_repo: IPlayerRepository
    ):
        self.voting_repo = voting_repo
        self.match_repo = match_repo
        self.player_repo = player_repo

    def get_voting_status(self, match_id: int, voter_id: int) -> schemas.VotingStatusResponse:
        match = self.match_repo.get_by_id(match_id)
        if not match:
            return schemas.VotingStatusResponse(is_open=False, current_round=0, has_voted=False, excluded_player_ids=[])
        
        if match.voting_round == 0:
            return schemas.VotingStatusResponse(is_open=False, current_round=0, has_voted=False, excluded_player_ids=[])
        
        # Check if already voted in current round
        existing_vote = self.voting_repo.get_vote_by_voter(match_id, voter_id, match.voting_round)
        has_voted = existing_vote is not None
        
        # Excluded players are those who won previous rounds
        excluded_ids = []
        if match.voting_round > 1:
            # Round 1 winner
            r1_results = self.voting_repo.get_round_results(match_id, 1)
            if r1_results:
                excluded_ids.append(r1_results[0]["candidate_id"])
        if match.voting_round > 2:
            # Round 2 winner
            r2_results = self.voting_repo.get_round_results(match_id, 2)
            if r2_results:
                excluded_ids.append(r2_results[0]["candidate_id"])
                
        return schemas.VotingStatusResponse(
            is_open=True,
            current_round=match.voting_round,
            has_voted=has_voted,
            excluded_player_ids=excluded_ids
        )

    CHEAT_MESSAGE = "يا غشاش يا حرامي يا وسخ! 🤡 انت عملت تصويت قبل كده من الجهاز ده... فاكر إنك هتعدّيها علينا؟"
    MAX_VOTES_PER_IP = 2

    def submit_vote(self, match_id: int, vote_in: schemas.VoteCreate, ip_address: str = "") -> models.Vote:
        from fastapi import HTTPException

        match = self.match_repo.get_by_id(match_id)
        if not match or match.voting_round == 0:
            raise HTTPException(status_code=400, detail="التصويت مغلق حالياً")

        if vote_in.round_number != match.voting_round:
            raise HTTPException(status_code=400, detail="رقم الجولة غير صحيح")

        # Anti-cheat: check device fingerprint
        fp = vote_in.device_fingerprint.strip() if vote_in.device_fingerprint else ""
        if fp:
            existing_fp = self.voting_repo.get_vote_by_fingerprint(match_id, fp, match.voting_round)
            if existing_fp:
                raise HTTPException(status_code=403, detail=self.CHEAT_MESSAGE)

        # Anti-cheat: check IP address (allow up to MAX_VOTES_PER_IP from same IP)
        if ip_address:
            ip_votes = self.voting_repo.get_votes_by_ip(match_id, ip_address, match.voting_round)
            if len(ip_votes) >= self.MAX_VOTES_PER_IP:
                raise HTTPException(status_code=403, detail=self.CHEAT_MESSAGE)

        # Check if voter_id already voted
        existing = self.voting_repo.get_vote_by_voter(match_id, vote_in.voter_id, match.voting_round)
        if existing:
            raise HTTPException(status_code=400, detail="لقد قمت بالتصويت بالفعل في هذه الجولة")

        # Check if candidate is excluded
        status = self.get_voting_status(match_id, vote_in.voter_id)
        if vote_in.candidate_id in status.excluded_player_ids:
            raise HTTPException(status_code=400, detail="هذا اللاعب فاز بالفعل في جولة سابقة")

        vote = models.Vote(
            match_id=match_id,
            league_id=match.league_id,
            voter_id=vote_in.voter_id,
            candidate_id=vote_in.candidate_id,
            round_number=match.voting_round,
            ip_address=ip_address,
            device_fingerprint=fp,
        )
        return self.voting_repo.save_vote(vote)

    def close_round(self, match_id: int) -> dict:
        match = self.match_repo.get_by_id(match_id)
        if not match or match.voting_round == 0:
            return {"status": "error", "message": "التصويت غير مفتوح"}
            
        round_results = self.voting_repo.get_round_results(match_id, match.voting_round)
        if not round_results:
            # No votes? Just close it or move on
            if match.voting_round < 3:
                match.voting_round += 1
                self.match_repo.save(match)
                return {"status": "next_round", "round": match.voting_round}
            else:
                match.voting_round = 0
                self.match_repo.save(match)
                return {"status": "closed"}

        winner_id = round_results[0]["candidate_id"]
        winner = self.player_repo.get_by_id(winner_id)
        
        # Award bonus points
        bonus_map = {1: 3, 2: 2, 3: 1}
        bonus = bonus_map.get(match.voting_round, 0)
        
        if winner:
            winner.total_points += bonus
            self.player_repo.save(winner)
            
            # Update MatchStat if exists to reflect bonus? 
            # Or just add to total points. Usually we want it in the match history too.
            # Let's find the match stat for this player
            for stat in match.stats:
                if stat.player_id == winner_id:
                    stat.points += bonus
                    # No need to call repo.save for stat if match.stats are managed by session
                    break
        
        if match.voting_round < 3:
            match.voting_round += 1
            self.match_repo.save(match)
            return {"status": "next_round", "round": match.voting_round, "winner": winner.name if winner else "Unknown"}
        else:
            match.voting_round = 0
            self.match_repo.save(match)
            return {"status": "closed", "winner": winner.name if winner else "Unknown"}

    def open_voting(self, match_id: int) -> dict:
        match = self.match_repo.get_by_id(match_id)
        if not match:
            return {"status": "error", "message": "الماتش غير موجود"}
        
        match.voting_round = 1
        self.match_repo.save(match)
        return {"status": "opened", "round": 1}
