import re
import uuid

from app.core import security
from app.models.user_model import User
from app.models import models


def _set_user_cookie(client, user_id: int) -> None:
    token = security.create_access_token(data={"sub": str(user_id), "scope": "user"})
    client.cookies.set("user_access_token", f"Bearer {token}")


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m
    return m.group(1)


def test_dashboard_shows_owned_leagues(client, db_session):
    email = f"dash+{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, hashed_password=security.get_password_hash("StrongPass1"), is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    league = models.League(
        name=f"League {uuid.uuid4().hex[:6]}",
        slug=f"league-{uuid.uuid4().hex[:6]}",
        admin_password=security.get_password_hash("StrongPass1"),
        admin_email=user.email,
        owner_user_id=user.id,
    )
    db_session.add(league)
    db_session.commit()

    # Add players + one match to validate stats
    db_session.add(models.Player(name="P1", league_id=league.id))
    db_session.add(models.Player(name="P2", league_id=league.id))
    db_session.add(models.Match(league_id=league.id))
    db_session.commit()

    _set_user_cookie(client, user.id)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert league.slug in resp.text
    assert "عدد اللاعبين" in resp.text


def test_onboarding_happy_path_creates_league_and_players(client, db_session):
    email = f"ob+{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, hashed_password=security.get_password_hash("StrongPass1"), is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _set_user_cookie(client, user.id)

    # Start
    r = client.get("/onboarding/start")
    assert r.status_code == 200
    csrf = _extract_csrf(r.text)

    # League step GET (to set csrf cookie)
    r = client.get("/onboarding/league")
    assert r.status_code == 200
    csrf = _extract_csrf(r.text)

    slug = f"ob-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/onboarding/league",
        data={
            "name": f"Onboard {uuid.uuid4().hex[:6]}",
            "slug": slug,
            "admin_password": "StrongPass1",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 307, 308)
    assert "league_id=" in r.headers.get("location", "")

    # follow to teams GET
    teams_url = r.headers["location"]
    r = client.get(teams_url)
    assert r.status_code == 200
    csrf = _extract_csrf(r.text)

    # submit teams
    league_id = int(re.search(r"league_id=(\d+)", teams_url).group(1))
    r = client.post(
        "/onboarding/teams",
        data={
            "league_id": league_id,
            "team_a_label": "الأحمر",
            "team_b_label": "الأزرق",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 307, 308)
    players_url = r.headers["location"]

    # players GET
    r = client.get(players_url)
    assert r.status_code == 200
    csrf = _extract_csrf(r.text)

    r = client.post(
        "/onboarding/players",
        data={
            "league_id": league_id,
            "players_text": "Ali\nOmar\nAli\n",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 307, 308)
    done_url = r.headers["location"]

    r = client.get(done_url)
    assert r.status_code == 200
    assert slug in r.text

    created_league = db_session.query(models.League).filter(models.League.id == league_id).first()
    assert created_league is not None
    assert created_league.owner_user_id == user.id
    assert created_league.admin_email == user.email
    assert created_league.team_a_label == "الأحمر"
    assert created_league.team_b_label == "الأزرق"

    players = db_session.query(models.Player).filter(models.Player.league_id == league_id).all()
    assert {p.name for p in players} == {"Ali", "Omar"}


def test_onboarding_start_redirects_when_user_has_leagues(client, db_session):
    email = f"ob2+{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, hashed_password=security.get_password_hash("StrongPass1"), is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    league = models.League(
        name=f"League {uuid.uuid4().hex[:6]}",
        slug=f"league-{uuid.uuid4().hex[:6]}",
        admin_password=security.get_password_hash("StrongPass1"),
        admin_email=user.email,
        owner_user_id=user.id,
    )
    db_session.add(league)
    db_session.commit()

    _set_user_cookie(client, user.id)
    r = client.get("/onboarding/start", follow_redirects=False)
    assert r.status_code in (302, 303, 307, 308)
    # User owns a league but hasn't created players yet → resume at players step.
    assert r.headers.get("location") == f"/onboarding/players?league_id={league.id}&resumed=1"

