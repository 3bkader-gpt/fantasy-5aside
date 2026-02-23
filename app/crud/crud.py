from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from ..models import models
from ..schemas import schemas
from ..services import points

def get_league_by_slug(db: Session, slug: str):
    return db.query(models.League).filter(models.League.slug == slug).first()

def get_all_leagues(db: Session):
    return db.query(models.League).order_by(models.League.created_at.desc()).all()

def get_leaderboard(db: Session, league_id: int):
    """
    Retrieve all players for a specific league ordered by total_points descending, 
    then by total_goals descending. Calculates form based on last 3 matches.
    """
    players = db.query(models.Player).filter(models.Player.league_id == league_id).order_by(
        models.Player.total_points.desc(),
        models.Player.total_goals.desc()
    ).all()

    for player in players:
        # Fetch last 3 MatchStat records for this player
        last_3_stats = db.query(models.MatchStat).join(models.Match).filter(
            models.MatchStat.player_id == player.id,
            models.Match.league_id == league_id
        ).order_by(models.Match.date.desc()).limit(3).all()
        
        recent_points = sum(stat.points_earned for stat in last_3_stats)
        
        if recent_points >= 6:
            player.form = '🔥'
        elif recent_points <= 2 and len(last_3_stats) == 3: # Only showing cold if they actually played 3 matches
            player.form = '❄️'
        else:
            player.form = '➖'
            
    return players

def get_all_matches(db: Session, league_id: int):
    """
    Retrieve all matches for a league ordered by date descending,
    eagerly loading stats and players.
    """
    return db.query(models.Match).filter(models.Match.league_id == league_id).options(
        joinedload(models.Match.stats).joinedload(models.MatchStat.player)
    ).order_by(models.Match.date.desc()).all()

def register_match(db: Session, match_data: schemas.MatchCreate, league_id: int):
    """
    Create a new match, handle dynamic players within the league, calculate points, 
    update player totals, save everything to the DB, and auto-resolve active cup matchups.
    """
    # Verify Admin Password
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league or league.admin_password != match_data.admin_password:
        raise HTTPException(status_code=401, detail="كلمة سر الإدارة غير صحيحة")

    # Calculate Teams Scores
    team_a_score = sum(s.goals for s in match_data.stats if s.team == 'A')
    team_b_score = sum(s.goals for s in match_data.stats if s.team == 'B')

    # Create the Match record
    db_match = models.Match(
        league_id=league_id,
        team_a_name=match_data.team_a_name,
        team_b_name=match_data.team_b_name,
        team_a_score=team_a_score,
        team_b_score=team_b_score
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)

    for stat_data in match_data.stats:
        # Find or Create Player in this League
        player_name = stat_data.player_name.strip()
        player = db.query(models.Player).filter(
            models.Player.name == player_name,
            models.Player.league_id == league_id
        ).first()
        
        if not player:
            player = models.Player(name=player_name, league_id=league_id)
            db.add(player)
            db.commit()
            db.refresh(player)
            
        # Determine is_winner Dynamically
        is_winner = False
        if stat_data.team == 'A' and team_a_score > team_b_score:
            is_winner = True
        elif stat_data.team == 'B' and team_b_score > team_a_score:
            is_winner = True
            
        # Calculate points for this specific performance
        points_earned = points.calculate_player_points(
            goals=stat_data.goals,
            assists=stat_data.assists,
            is_winner=is_winner,
            is_gk=stat_data.is_gk,
            clean_sheet=stat_data.clean_sheet,
            mvp=stat_data.mvp,
            saves=stat_data.saves,
            goals_conceded=stat_data.goals_conceded,
            is_captain=stat_data.is_captain
        )

        # Create MatchStat record
        db_stat = models.MatchStat(
            match_id=db_match.id,
            player_id=player.id,
            team=stat_data.team,
            goals=stat_data.goals,
            assists=stat_data.assists,
            saves=stat_data.saves,
            goals_conceded=stat_data.goals_conceded,
            is_winner=is_winner,
            is_gk=stat_data.is_gk,
            clean_sheet=stat_data.clean_sheet,
            mvp=stat_data.mvp,
            is_captain=stat_data.is_captain,
            points_earned=points_earned
        )
        db.add(db_stat)

        # Update Player totals
        player.total_points += points_earned
        player.total_goals += stat_data.goals
        player.total_assists += stat_data.assists
        player.total_saves += stat_data.saves
        if stat_data.clean_sheet:
            player.total_clean_sheets += 1
        db.add(player)

    db.commit()

    # --- Cup Matchup Resolution ---
    # Fetch all active cup matchups for this league
    active_matchups = db.query(models.CupMatchup).filter(
        models.CupMatchup.is_active == True,
        models.CupMatchup.league_id == league_id
    ).all()
    
    # Get points earned by each player in the current match we just registered
    match_stats = db.query(models.MatchStat).filter(models.MatchStat.match_id == db_match.id).all()
    player_points_this_match = {stat.player_id: stat.points_earned for stat in match_stats}

    for matchup in active_matchups:
        # Check if BOTH players played in this specific match
        if matchup.player1_id in player_points_this_match and matchup.player2_id in player_points_this_match:
            p1_points = player_points_this_match[matchup.player1_id]
            p2_points = player_points_this_match[matchup.player2_id]

            if p1_points > p2_points:
                matchup.winner_id = matchup.player1_id
            elif p2_points > p1_points:
                matchup.winner_id = matchup.player2_id
            else:
                # Tie-breaker: overall total_points
                db_p1 = db.query(models.Player).filter(models.Player.id == matchup.player1_id).first()
                db_p2 = db.query(models.Player).filter(models.Player.id == matchup.player2_id).first()
                
                if db_p1.total_points > db_p2.total_points:
                    matchup.winner_id = matchup.player1_id
                elif db_p2.total_points > db_p1.total_points:
                    matchup.winner_id = matchup.player2_id
                else:
                    # Very rare extreme tie, default to player 1
                    matchup.winner_id = matchup.player1_id
                    
            matchup.is_active = False
            db.add(matchup)

    db.commit()
    return db_match

def generate_cup_draw(db: Session, league_id: int):
    """
    Fetch top 10 players of the league and create Quarter-Final matchups.
    """
    # Delete old cup draws for a clean new monthly tournament in this league
    db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete()
    
    top_players = db.query(models.Player).filter(models.Player.league_id == league_id).order_by(
        models.Player.total_points.desc()
    ).limit(10).all()
    
    if len(top_players) < 2:
        return False # Need at least 2 players
        
    # Matchups: 1st vs 10th, 2nd vs 9th, etc.
    num_players = len(top_players)
    matchups = []
    for i in range(num_players // 2):
        p1 = top_players[i]
        p2 = top_players[num_players - 1 - i]
        
        matchup = models.CupMatchup(
            league_id=league_id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name='ربع النهائي (Quarter-Final)',
            is_active=True
        )
        db.add(matchup)
    
    db.commit()
    return True

def get_active_cup_matchups(db: Session, league_id: int):
    # Returns all active and resolved matchups from the current cup draw for the league.
    return db.query(models.CupMatchup).filter(
        models.CupMatchup.league_id == league_id
    ).options(
        joinedload(models.CupMatchup.player1),
        joinedload(models.CupMatchup.player2)
    ).all()

def end_current_season(db: Session, month_name: str, league_id: int):
    # 1. Find the player with the highest current total_points in the league
    top_player = db.query(models.Player).filter(models.Player.league_id == league_id).order_by(
        models.Player.total_points.desc(), 
        models.Player.total_goals.desc()
    ).first()
    
    if top_player and top_player.total_points > 0:
        # 2. Create a HallOfFame record
        hof = models.HallOfFame(
            league_id=league_id,
            month_year=month_name,
            player_id=top_player.id,
            points_scored=top_player.total_points
        )
        db.add(hof)

    # 3 & 4. Add current stats to all_time stats and reset current stats
    all_players = db.query(models.Player).filter(models.Player.league_id == league_id).all()
    for player in all_players:
        player.all_time_points += player.total_points
        player.all_time_goals += player.total_goals
        player.all_time_assists += player.total_assists
        player.all_time_saves += player.total_saves
        player.all_time_clean_sheets += player.total_clean_sheets

        player.total_points = 0
        player.total_goals = 0
        player.total_assists = 0
        player.total_saves = 0
        player.total_clean_sheets = 0
        db.add(player)

    # 5. Delete all active CupMatchup records for this league
    db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete()

    # 6. Commit the transaction
    db.commit()


def get_player_analytics(db: Session, player_id: int, league_id: int):
    player = db.query(models.Player).filter(
        models.Player.id == player_id,
        models.Player.league_id == league_id
    ).first()
    if not player:
        return None

    history = db.query(models.MatchStat).options(
        joinedload(models.MatchStat.match)
    ).filter(
        models.MatchStat.player_id == player.id
    ).order_by(models.MatchStat.match_id.desc()).all()

    total_matches = len(history)
    wins = sum(1 for stat in history if stat.is_winner)
    
    win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
    total_goals_assists_all_time = player.all_time_goals + player.all_time_assists + player.total_goals + player.total_assists
    ga_per_match = (total_goals_assists_all_time / total_matches) if total_matches > 0 else 0

    # Sort history properly by match date
    history.sort(key=lambda s: s.match.date, reverse=True)

    return {
        "player": player,
        "history": history,
        "total_matches": total_matches,
        "win_rate": round(win_rate, 2),
        "ga_per_match": round(ga_per_match, 2)
    }

def delete_match(db: Session, match_id: int, league_id: int):
    match = db.query(models.Match).filter(
        models.Match.id == match_id,
        models.Match.league_id == league_id
    ).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
        
    for stat in match.stats:
        player = stat.player
        player.total_points = max(0, player.total_points - stat.points_earned)
        player.total_goals = max(0, player.total_goals - stat.goals)
        player.total_assists = max(0, player.total_assists - stat.assists)
        player.total_saves = max(0, player.total_saves - stat.saves)
        if stat.clean_sheet:
            player.total_clean_sheets = max(0, player.total_clean_sheets - 1)
        db.add(player)
        
    db.delete(match)
    db.commit()
    return True
