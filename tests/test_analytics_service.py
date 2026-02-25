from app.schemas import schemas
from app.core import security
from app.models import models

class TestAnalyticsService:
    def test_get_player_analytics_badges_and_stats(self, db_session, league_repo, player_repo, match_repo, analytics_service):
        # 1. Setup
        league = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        p = player_repo.create("Super Player", league.id)
        
        # Manually set some stats to trigger badges
        p.total_goals = 5 # SniperBadge
        p.total_assists = 5 # TopAssistsBadge
        player_repo.save(p)
        
        # Add a match with a hat-trick
        match1 = models.Match(league_id=league.id, team_a_name="Team A", team_b_name="Team B", team_a_score=3, team_b_score=0)
        match_repo.save(match1)
        stat1 = models.MatchStat(
            match_id=match1.id, 
            player_id=p.id, 
            team="A", 
            goals=3, 
            is_winner=True,
            points_earned=10
        )
        db_session.add(stat1)
        
        # Add two more matches to verify win_rate and ga_per_match
        match2 = models.Match(league_id=league.id, team_a_name="Team A", team_b_name="Team B", team_a_score=1, team_b_score=2)
        match_repo.save(match2)
        stat2 = models.MatchStat(
            match_id=match2.id, 
            player_id=p.id, 
            team="A", 
            goals=0, 
            is_winner=False,
            points_earned=2
        )
        db_session.add(stat2)
        db_session.commit()
        
        # 2. Execute
        analytics = analytics_service.get_player_analytics(p.id, league.id)
        
        # 3. Verify
        assert analytics["total_matches"] == 2
        assert analytics["win_rate"] == 50.0
        assert "القناص 🔫" in analytics["badges"] # 5 total goals
        assert "عمود الوسط 🎯" in analytics["badges"] # 5 total assists
        assert "هاتريك ⚽⚽⚽" in analytics["badges"] # 3 goals in match1
        assert analytics["ga_per_match"] == 5.0 # (5+5)/2
        assert len(analytics["history"]) == 2

    def test_wall_badge_for_goalkeeper(self, db_session, league_repo, player_repo, match_repo, analytics_service):
        league = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        gk = player_repo.create("GK", league.id)
        
        # Create 3 matches with clean sheets as GK
        for i in range(3):
            m = models.Match(league_id=league.id)
            match_repo.save(m)
            s = models.MatchStat(match_id=m.id, player_id=gk.id, is_gk=True, clean_sheet=True)
            db_session.add(s)
        db_session.commit()
        
        analytics = analytics_service.get_player_analytics(gk.id, league.id)
        assert "الحائط 🛡️" in analytics["badges"]

    def test_octopus_badge(self, db_session, league_repo, player_repo, match_repo, analytics_service):
        league = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        p = player_repo.create("P", league.id)
        
        m = models.Match(league_id=league.id)
        match_repo.save(m)
        s = models.MatchStat(match_id=m.id, player_id=p.id, saves=5)
        db_session.add(s)
        db_session.commit()
        
        analytics = analytics_service.get_player_analytics(p.id, league.id)
        assert "أخطبوط 🐙" in analytics["badges"]
