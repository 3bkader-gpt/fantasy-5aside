# 📋 Project Index - 5-a-Side Fantasy Football SaaS

### 🔗 Quick navigation
- **High-level context**: see `PROJECT_CONTEXT.md`
- **Overview**: [Project Overview](#-project-overview)
- **Structure**: [Project Structure](#-project-structure)
- **Data model**: [Database Schema](#️-database-schema)
- **Features**: [Core Features](#-core-features)
- **Architecture patterns**: [Architectural Patterns](#-architectural-patterns)
- **API**: [API Routes](#️-api-routes)
- **Security**: [Security](#-security)
- **Tests**: [Tests](#-tests)
- **Stats**: [Available Statistics](#-available-statistics)
- **Frontend**: [Frontend](#-frontend)
- **Deployment**: [Deployment](#-deployment)
- **Workflow**: [Workflow](#-workflow)
- **Notes & roadmap**: [Important Notes](#-important-notes), [Future Roadmap](#-future-roadmap-from-saas_planmd), [Development Tips](#-development-tips)

---

## 🎯 Project Overview

**Type**: Multi-tenant Fantasy Football SaaS for local 5-a-side matches

**Tech Stack**:
- **Backend**: FastAPI + Python 3
- **Database**: SQLite (development) / PostgreSQL (production) + SQLAlchemy ORM
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript + Jinja2 Templates
- **Authentication**: JWT Tokens + Cookie-based sessions
- **Security**: bcrypt password hashing, anti-cheat voting system

**Current Version**: v3.0

---

## 📁 Project Structure

```
fantasy/
├── app/                          # Main application
│   ├── main.py                  # FastAPI entrypoint
│   ├── database.py              # Database configuration
│   ├── dependencies.py          # Dependency Injection container
│   │
│   ├── core/                    # Core configuration
│   │   ├── config.py           # Environment & settings management
│   │   └── security.py         # JWT + password hashing
│   │
│   ├── models/                  # Database models (SQLAlchemy)
│   │   └── models.py           # All models
│   │
│   ├── schemas/                 # Pydantic schemas for the API
│   │   └── schemas.py          # All schemas
│   │
│   ├── repositories/            # Data access layer (Repository Pattern)
│   │   ├── interfaces.py       # Abstract interfaces
│   │   └── db_repository.py    # Concrete implementation
│   │
│   ├── services/                # Business logic layer
│   │   ├── interfaces.py       # Service interfaces
│   │   ├── league_service.py   # League and season management
│   │   ├── match_service.py    # Match creation and updates
│   │   ├── cup_service.py      # Cup system (knockout tournament)
│   │   ├── voting_service.py   # Voting system
│   │   ├── analytics_service.py # Analytics and statistics
│   │   ├── achievements.py     # Badges and achievements system
│   │   └── points.py           # Points calculation (Strategy Pattern)
│   │
│   ├── routers/                 # API Routes
│   │   ├── public.py           # Public pages
│   │   ├── admin.py            # Admin dashboard
│   │   ├── auth.py             # Login / logout
│   │   └── voting.py           # Voting API
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html           # Base layout
│   │   ├── landing.html        # Landing page
│   │   ├── leaderboard.html    # League leaderboard
│   │   ├── matches.html        # Matches list
│   │   ├── player.html         # Player profile
│   │   ├── cup.html            # Cup page
│   │   ├── hof.html            # Hall of Fame
│   │   ├── admin/
│   │   │   └── dashboard.html  # Admin dashboard
│   │   └── auth/
│   │       ├── login.html      # Login page
│   │       └── unauthorized.html
│   │
│   └── static/                  # Static assets
│       ├── css/style.css
│       ├── js/
│       │   ├── main.js
│       │   ├── admin_dashboard.js
│       │   ├── leaderboard.js
│       │   ├── matches.js
│       │   └── player_chart.js
│       └── img/
│
├── tests/                       # Tests
│   ├── conftest.py             # Test configuration & fixtures
│   ├── test_points.py          # Points calculation tests
│   ├── test_match_service.py   # Match service tests
│   ├── test_league_service.py  # League service tests
│   ├── test_cup.py             # Cup system tests
│   ├── test_voting_live.py     # Voting tests
│   └── test_api_*.py           # API tests
│
├── data/                        # Local database
│   └── fantasy.db              # SQLite DB (development)
│
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Pytest configuration
├── render.yaml                  # Render.com deployment config
└── SAAS_PLAN.md                # Plan to evolve into full SaaS
```

---

## 🗄️ Database Schema

### Main tables:

#### 1. **leagues**
```python
- id: Unique identifier
- name: League name (unique)
- slug: URL slug (unique)
- admin_password: Hashed admin password
- current_season_matches: Number of matches in the current season
- season_number: Season number
- team_a_label: Label for Team A
- team_b_label: Label for Team B
- created_at: Creation timestamp
```

#### 2. **players**
```python
- id, league_id (Foreign Key)
- name: Player name
- team_id: Registered team (optional)
- default_is_gk: Is the player a goalkeeper by default?

# Current season stats:
- total_points, total_goals, total_assists
- total_saves, total_clean_sheets, total_own_goals
- total_matches, previous_rank

# All-time stats:
- all_time_points, all_time_goals, all_time_assists
- all_time_saves, all_time_clean_sheets, all_time_own_goals
- all_time_matches

# For undoing season end:
- last_season_points, last_season_goals, ...

# For the cup:
- is_active_in_cup: Is the player participating in the current cup?
```

#### 3. **teams** (registered teams - new system)
```python
- id, league_id
- name: Team name
- short_code: Short code (e.g. HR, IT)
- color: Team color in hex
```

#### 4. **matches**
```python
- id, league_id
- date: Match date
- team_a_name, team_b_name: Team names
- team_a_id, team_b_id: Team ids (if fixed-team system is enabled)
- team_a_score, team_b_score: Final score
- voting_round: Voting status (0-4)
  * 0 = not open
  * 1-3 = voting rounds
  * 4 = closed
```

#### 5. **match_stats** (per-player match stats)
```python
- id, player_id, match_id
- team: A or B
- goals, assists, saves, goals_conceded, own_goals
- is_winner, is_gk, clean_sheet, mvp, is_captain
- points_earned, bonus_points
```

#### 6. **cup_matchups**
```python
- id, league_id
- player1_id, player2_id (nullable - bye)
- round_name: Round name
- bracket_type: "outfield" or "goalkeeper"
- winner_id: Winner id
- is_active: Is this matchup active?
- is_revealed: Has the matchup been revealed to users?
- match_id: Match that decided the winner
```

#### 7. **votes**
```python
- id, league_id, match_id
- voter_id, candidate_id: Who voted and for whom
- round_number: Voting round number (1-3)
- ip_address: IP address (anti-cheat)
- device_fingerprint: Device fingerprint (anti-cheat)
- created_at
```

#### 8. **hall_of_fame**
```python
- id, league_id, player_id
- month_year: Season label (e.g. "Mar 2026 - S3")
- points_scored: Points scored in that season
```

#### 9. **transfers** (team transfers)
```python
- id, league_id, player_id
- from_team_id, to_team_id
- reason: Reason for transfer
- created_at
```

---

## 🎮 Core Features

### 1. **Multi-Tenancy**
- Each league is fully isolated from others
- Unique URL per league: `/l/{slug}`
- Separate admin password per league

### 2. **Advanced Points System** (`app/services/points.py`)

Uses the **Strategy Pattern** to calculate points:

#### Strategies:
```python
1. ParticipationPoints: +2 for participation
2. GoalPoints: +3 per goal (+6 for goalkeeper)
3. AssistPoints: +2 per assist (+4 for goalkeeper)
4. WinPoints:
   - Win: +2
   - Draw: +1
   - Loss: -1
5. CleanSheetPoints (for goalkeeper):
   - 0–2 goals conceded: +10
   - 3–6 goals conceded: +4
   - >6 goals conceded: 0
6. SavePoints (goalkeeper): every 3 saves = +2
7. GoalsConcededPenalty (goalkeeper): every 4 goals conceded = -1
8. OwnGoalPenalty: each own goal = -1
```

### 3. **Captain System**
- Admin can assign a captain per match
- Captain receives **double points** (×2)

### 4. **Monthly Cup System**
- Automatically generated cup for top 10 players
- Head-to-head knockouts
- Two brackets: goalkeepers vs outfield players
- Automatic resolution when both players appear in the same match
- Cooperative final rule: if both finalists are on the same team, they share the win

### 5. **MVP Voting System**
- 3 voting rounds after each match
- Each round grants extra points:
  - Round 1: +3 points
  - Round 2: +2 points
  - Round 3: +1 point
- Triple-layer anti-cheat:
  1. **localStorage**: prevent duplicate votes in the same browser
  2. **IP Address**: max 2 votes from the same IP
  3. **Device Fingerprint**: unique device fingerprint

### 6. **Auto Seasons**
- Every 4 matches = new season
- Automatically:
  1. Save the winner to Hall of Fame
  2. Move current stats to All-Time
  3. Reset season counters for the new season
- Supports undoing season end

### 7. **Fixed Teams System**
- Register permanent company teams (e.g. HR, IT, Sales...)
- Track player team memberships
- Track transfer history between teams

### 8. **Badges / Achievements**
Automatic badges on the leaderboard:
```python
- 🔫 Sniper: 6 goals in a single match
- 🛡️ The Wall: 3 clean sheets
- 🎯 Playmaker: 15 assists
- ⚡ Rocket: 5 goals in 3 consecutive matches
- 🤡 Defensive Clown: scored own goals
- 🔥 Hot Form: excellent performance in last 3 matches
- ❄️ Cold Form: poor performance in last 3 matches
```

### 9. **Player Analytics Page**
- Win rate (Win Rate %)
- Goal contribution per match
- Performance over time chart (Chart.js)
- Full match history

---

## 🔧 Architectural Patterns

### 1. **Repository Pattern**
Separates data access logic from business logic:
```
├── repositories/interfaces.py    → abstract definitions
└── repositories/db_repository.py → concrete implementation
```

### 2. **Dependency Injection**
All services and repositories are injected via `dependencies.py`:
```python
get_league_service(...)
get_match_service(...)
get_cup_service(...)
```

### 3. **Strategy Pattern**
Used in points calculation (`points.py`):
```python
class PointsStrategy(ABC):
    @abstractmethod
    def calculate(self, ctx: PointsContext) -> int:
        pass
```

### 4. **Service Layer Pattern**
Business logic is isolated in the Services layer:
- LeagueService
- MatchService
- CupService
- VotingService
- AnalyticsService

---

## 🛣️ API Routes

### Public Routes (`routers/public.py`):
```
GET  /                             → Landing page
POST /create-league                → Create a new league
GET  /l/{slug}                     → League leaderboard
GET  /l/{slug}/matches             → Matches page
GET  /l/{slug}/cup                 → Cup page
GET  /l/{slug}/player/{id}         → Player profile
GET  /l/{slug}/hof                 → Hall of Fame
```

### Admin Routes (`routers/admin.py`) - requires JWT:
```
GET  /l/{slug}/admin                 → Admin dashboard
POST /l/{slug}/admin/match           → Create match
PUT  /l/{slug}/admin/match/{id}      → Update match
DELETE /l/{slug}/admin/match/{id}    → Delete match
POST /l/{slug}/admin/cup/generate    → Generate cup
POST /l/{slug}/admin/season/end      → End season
POST /l/{slug}/admin/season/undo     → Undo end season
POST /l/{slug}/admin/settings/update → Update league settings
POST /l/{slug}/admin/player/add      → Add player
PUT  /l/{slug}/admin/player/{id}     → Update player
DELETE /l/{slug}/admin/player/{id}   → Delete player
POST /l/{slug}/admin/team/create     → Create team
```

### Auth Routes (`routers/auth.py`):
```
GET  /login                        → Login page
POST /login                        → Perform login
GET  /logout                       → Logout
```

### Voting API (`routers/voting.py`):
```
GET  /api/voting/match/{id}/status → Voting status
GET  /api/voting/match/{id}/live   → Live voting stats
POST /api/voting/vote              → Submit vote
POST /api/voting/{slug}/open/{id}  → Open voting for a match (Admin)
POST /api/voting/{slug}/close/{id} → Close voting round (Admin)
```

---

## 🔒 Security

### 1. **JWT Authentication**
```python
# In core/security.py:
- create_access_token(): create access token
- verify_token(): validate token
- Token lifetime: 7 days
```

### 2. **Password Hashing**
```python
# Using passlib + bcrypt:
- get_password_hash(): hash password
- verify_password(): verify password
```

### 3. **Cookie-based Sessions**
```python
# JWT stored in httpOnly cookie:
response.set_cookie(
    key="access_token",
    value=f"Bearer {token}",
    httponly=True,
    samesite="lax"
)
```

### 4. **Anti-Cheat in Voting**
```python
# Anti-cheat layers:
1. localStorage: prevent duplicate browser votes
2. IP Limit: max 2 votes per IP
3. Fingerprint: unique device fingerprint
```

---

## 🧪 Tests

```
tests/
├── conftest.py                  → fixtures & shared setup
├── test_points.py              → points calculation tests
├── test_match_service.py       → match registration tests
├── test_league_service.py      → league / season tests
├── test_cup.py                 → cup system tests
├── test_voting_live.py         → voting tests
├── test_api_admin.py           → admin API tests
├── test_api_public.py          → public API tests
├── test_analytics_service.py   → analytics tests
└── test_repos.py               → repository tests
```

### Running tests:
```bash
pytest                          # run all tests
pytest tests/test_points.py    # run specific test file
pytest -v                      # verbose mode
```

---

## 📊 Available Statistics

### Player-level:
- Current season stats
- All-time stats
- Last season snapshot (for undo)
- Win rate
- Goal contribution per match (GA/Match)
- Form (Hot 🔥 / Cold ❄️)

### Match-level:
- Final score and per-player detailed stats
- MVP (from voting)
- Captain
- Bonus points

### League-level:
- Leaderboard
- Hall of Fame
- Cup bracket
- Total matches in current season

---

## 🎨 Frontend

### Technologies:
- **Vanilla JavaScript**: no frontend framework
- **Chart.js**: charts and visualizations
- **CSS Custom Properties**: theming
- **Font Awesome**: icons

### Main files:
```
static/
├── css/style.css               → styles
└── js/
    ├── main.js                → shared JS logic
    ├── admin_dashboard.js     → admin dashboard logic
    ├── leaderboard.js         → leaderboard page logic
    ├── matches.js             → matches page logic
    └── player_chart.js        → player chart rendering
```

---

## 🚀 Deployment

### Local development:
```bash
# 1. Create virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Run the app
uvicorn app.main:app --reload

# 4. Access
http://127.0.0.1:8000
```

### Production (Render.com):
- `render.yaml` is ready
- Requires PostgreSQL database
- Environment variables:
  ```
  DATABASE_URL=postgresql://...
  SECRET_KEY=...
  ```

---

## 🔄 Workflow

### 1. Create a new league:
```
User → fills the form (name + slug + password)
      ↓
System → creates League in the database
      ↓
      redirects to /l/{slug}
```

### 2. Register a match:
```
Admin → logs in with league password
       ↓
       goes to /l/{slug}/admin
       ↓
       enters match data + per-player stats
       ↓
MatchService → creates Match + MatchStats
              updates player statistics
              calculates points (PointsCalculator)
              resolves cup matchups (CupService)
       ↓
System → updates leaderboard
```

### 3. MVP voting:
```
Admin → opens voting for a match
       ↓
Players → vote (3 rounds)
       ↓
System → applies anti-cheat (IP + fingerprint)
         saves vote
       ↓
Admin → closes each round
       ↓
System → grants extra points to winners
```

### 4. End season:
```
Admin → clicks "End Season"
       ↓
LeagueService → stores winner in Hall of Fame
                moves stats to All-Time
                resets total_* fields to 0
                deletes current cup
       ↓
New season starts automatically
```

---

## 📝 Important Notes

### 1. **Arabic name normalization**
In `match_service.py`:
```python
def normalize_name(name: str) -> str:
    # Remove diacritics
    # Normalize Alef variants (أ إ آ ا)
    # Normalize Ya / Alef-Maqsura (ى ي)
    # Normalize Ta Marbuta (ة ه)
```

### 2. **Manual-style migrations**
In `main.py` → `lifespan()`:
- New columns are added automatically on app startup
- Safe: ignores columns that already exist

### 3. **Special cup cases**
- **Bye**: when players count is odd, one player advances automatically
- **Co-op Final**: if both finalists play on the same team in the final = shared win

### 4. **Goalkeeper clean sheet logic**
- ≤2 goals conceded = +10 pts
- 3–6 goals conceded = +4 pts
- >6 goals conceded = 0 pts

---

## 🔮 Future Roadmap (from `SAAS_PLAN.md`)

### Current stage:
✅ Multi-tenant architecture in place  
✅ Self-signup implemented  
✅ JWT Auth implemented  
✅ Slug-based routing  

### Needed for full SaaS:
❌ User accounts system  
❌ Pricing plans  
❌ Billing  
❌ Super Admin dashboard  
❌ Marketing / landing page  

---

## 🛠️ Development Tips

### 1. Adding a new feature:
```
1. Add Model in models/models.py
2. Add Schema in schemas/schemas.py
3. Add Repository methods in repositories/
4. Add Service logic in services/
5. Add Routes in routers/
6. Write tests in tests/
```

### 2. Modifying the points system:
```python
# In services/points.py:
# Add a new Strategy:
class MyCustomPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        # your logic here
        return points
        
# Register it in the calculator:
self.strategies.append(MyCustomPoints())
```

### 3. Adding a new badge:
```python
# In services/achievements.py:
class MyBadge(BadgeRule):
    def evaluate(self, player, history):
        # condition for earning the badge
        if condition:
            return {
                "name": "Badge Name",
                "icon": "🏅",
                "description": "Description"
            }
        return None
```

---

## 📚 Useful Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy ORM**: https://docs.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/
- **Chart.js**: https://www.chartjs.org/

---

**Last updated**: March 2026  
**Version**: 3.1  
**Status**: In production ✅  
**Monitoring**: GA4 integrated via `base.html` analytics block (non-admin traffic only)

تمام، هذه نسخة `PROJECT_INDEX.md` كاملة بالإنجليزي. يمكنك استبدال محتوى الملف بهذا النص:

```markdown
# 📋 Project Index - 5-a-Side Fantasy Football SaaS

## 🎯 Project Overview

**Type**: Multi-tenant Fantasy Football SaaS for local 5-a-side matches

**Tech Stack**:
- **Backend**: FastAPI + Python 3
- **Database**: SQLite (development) / PostgreSQL (production) + SQLAlchemy ORM
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript + Jinja2 Templates
- **Authentication**: JWT Tokens + Cookie-based sessions
- **Security**: bcrypt password hashing, anti-cheat voting system

**Current Version**: v3.0

---

## 📁 Project Structure

```
fantasy/
├── app/                          # Main application
│   ├── main.py                  # FastAPI entrypoint
│   ├── database.py              # Database configuration
│   ├── dependencies.py          # Dependency Injection container
│   │
│   ├── core/                    # Core configuration
│   │   ├── config.py           # Environment & settings management
│   │   └── security.py         # JWT + password hashing
│   │
│   ├── models/                  # Database models (SQLAlchemy)
│   │   └── models.py           # All models
│   │
│   ├── schemas/                 # Pydantic schemas for the API
│   │   └── schemas.py          # All schemas
│   │
│   ├── repositories/            # Data access layer (Repository Pattern)
│   │   ├── interfaces.py       # Abstract interfaces
│   │   └── db_repository.py    # Concrete implementation
│   │
│   ├── services/                # Business logic layer
│   │   ├── interfaces.py       # Service interfaces
│   │   ├── league_service.py   # League and season management
│   │   ├── match_service.py    # Match creation and updates
│   │   ├── cup_service.py      # Cup system (knockout tournament)
│   │   ├── voting_service.py   # Voting system
│   │   ├── analytics_service.py # Analytics and statistics
│   │   ├── achievements.py     # Badges and achievements system
│   │   └── points.py           # Points calculation (Strategy Pattern)
│   │
│   ├── routers/                 # API Routes
│   │   ├── public.py           # Public pages
│   │   ├── admin.py            # Admin dashboard
│   │   ├── auth.py             # Login / logout
│   │   └── voting.py           # Voting API
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html           # Base layout
│   │   ├── landing.html        # Landing page
│   │   ├── leaderboard.html    # League leaderboard
│   │   ├── matches.html        # Matches list
│   │   ├── player.html         # Player profile
│   │   ├── cup.html            # Cup page
│   │   ├── hof.html            # Hall of Fame
│   │   ├── admin/
│   │   │   └── dashboard.html  # Admin dashboard
│   │   └── auth/
│   │       ├── login.html      # Login page
│   │       └── unauthorized.html
│   │
│   └── static/                  # Static assets
│       ├── css/style.css
│       ├── js/
│       │   ├── main.js
│       │   ├── admin_dashboard.js
│       │   ├── leaderboard.js
│       │   ├── matches.js
│       │   └── player_chart.js
│       └── img/
│
├── tests/                       # Tests
│   ├── conftest.py             # Test configuration & fixtures
│   ├── test_points.py          # Points calculation tests
│   ├── test_match_service.py   # Match service tests
│   ├── test_league_service.py  # League service tests
│   ├── test_cup.py             # Cup system tests
│   ├── test_voting_live.py     # Voting tests
│   └── test_api_*.py           # API tests
│
├── data/                        # Local database
│   └── fantasy.db              # SQLite DB (development)
│
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Pytest configuration
├── render.yaml                  # Render.com deployment config
└── SAAS_PLAN.md                # Plan to evolve into full SaaS
```

---

## 🗄️ Database Schema

### Main tables:

#### 1. **leagues**
```python
- id: Unique identifier
- name: League name (unique)
- slug: URL slug (unique)
- admin_password: Hashed admin password
- current_season_matches: Number of matches in the current season
- season_number: Season number
- team_a_label: Label for Team A
- team_b_label: Label for Team B
- created_at: Creation timestamp
```

#### 2. **players**
```python
- id, league_id (Foreign Key)
- name: Player name
- team_id: Registered team (optional)
- default_is_gk: Is the player a goalkeeper by default?

# Current season stats:
- total_points, total_goals, total_assists
- total_saves, total_clean_sheets, total_own_goals
- total_matches, previous_rank

# All-time stats:
- all_time_points, all_time_goals, all_time_assists
- all_time_saves, all_time_clean_sheets, all_time_own_goals
- all_time_matches

# For undoing season end:
- last_season_points, last_season_goals, ...

# For the cup:
- is_active_in_cup: Is the player participating in the current cup?
```

#### 3. **teams** (registered teams - new system)
```python
- id, league_id
- name: Team name
- short_code: Short code (e.g. HR, IT)
- color: Team color in hex
```

#### 4. **matches**
```python
- id, league_id
- date: Match date
- team_a_name, team_b_name: Team names
- team_a_id, team_b_id: Team ids (if fixed-team system is enabled)
- team_a_score, team_b_score: Final score
- voting_round: Voting status (0-4)
  * 0 = not open
  * 1-3 = voting rounds
  * 4 = closed
```

#### 5. **match_stats** (per-player match stats)
```python
- id, player_id, match_id
- team: A or B
- goals, assists, saves, goals_conceded, own_goals
- is_winner, is_gk, clean_sheet, mvp, is_captain
- points_earned, bonus_points
```

#### 6. **cup_matchups**
```python
- id, league_id
- player1_id, player2_id (nullable - bye)
- round_name: Round name
- bracket_type: "outfield" or "goalkeeper"
- winner_id: Winner id
- is_active: Is this matchup active?
- is_revealed: Has the matchup been revealed to users?
- match_id: Match that decided the winner
```

#### 7. **votes**
```python
- id, league_id, match_id
- voter_id, candidate_id: Who voted and for whom
- round_number: Voting round number (1-3)
- ip_address: IP address (anti-cheat)
- device_fingerprint: Device fingerprint (anti-cheat)
- created_at
```

#### 8. **hall_of_fame**
```python
- id, league_id, player_id
- month_year: Season label (e.g. "Mar 2026 - S3")
- points_scored: Points scored in that season
```

#### 9. **transfers** (team transfers)
```python
- id, league_id, player_id
- from_team_id, to_team_id
- reason: Reason for transfer
- created_at
```

---

## 🎮 Core Features

### 1. **Multi-Tenancy**
- Each league is fully isolated from others
- Unique URL per league: `/l/{slug}`
- Separate admin password per league

### 2. **Advanced Points System** (`app/services/points.py`)

Uses the **Strategy Pattern** to calculate points:

#### Strategies:
```python
1. ParticipationPoints: +2 for participation
2. GoalPoints: +3 per goal (+6 for goalkeeper)
3. AssistPoints: +2 per assist (+4 for goalkeeper)
4. WinPoints: 
   - Win: +2
   - Draw: +1
   - Loss: -1
5. CleanSheetPoints (for goalkeeper):
   - 0–2 goals conceded: +10
   - 3–6 goals conceded: +4
   - >6 goals conceded: 0
6. SavePoints (goalkeeper): every 3 saves = +2
7. GoalsConcededPenalty (goalkeeper): every 4 goals conceded = -1
8. OwnGoalPenalty: each own goal = -1
```

### 3. **Captain System**
- Admin can assign a captain per match
- Captain receives **double points** (×2)

### 4. **Monthly Cup System**
- Automatically generated cup for top 10 players
- Head-to-head knockouts
- Two brackets: goalkeepers vs outfield players
- Automatic resolution when both players appear in the same match
- Cooperative final rule: if both finalists are on the same team, they share the win

### 5. **MVP Voting System**
- 3 voting rounds after each match
- Each round grants extra points:
  - Round 1: +3 points
  - Round 2: +2 points
  - Round 3: +1 point
- Triple-layer anti-cheat:
  1. **localStorage**: prevent duplicate votes in the same browser
  2. **IP Address**: max 2 votes from the same IP
  3. **Device Fingerprint**: unique device fingerprint

### 6. **Auto Seasons**
- Every 4 matches = new season
- Automatically:
  1. Save the winner to Hall of Fame
  2. Move current stats to All-Time
  3. Reset season counters for the new season
- Supports undoing season end

### 7. **Fixed Teams System**
- Register permanent company teams (e.g. HR, IT, Sales...)
- Track player team memberships
- Track transfer history between teams

### 8. **Badges / Achievements**
Automatic badges on the leaderboard:
```python
- 🔫 Sniper: 6 goals in a single match
- 🛡️ The Wall: 3 clean sheets
- 🎯 Playmaker: 15 assists
- ⚡ Rocket: 5 goals in 3 consecutive matches
- 🤡 Defensive Clown: scored own goals
- 🔥 Hot Form: excellent performance in last 3 matches
- ❄️ Cold Form: poor performance in last 3 matches
```

### 9. **Player Analytics Page**
- Win rate (Win Rate %)
- Goal contribution per match
- Performance over time chart (Chart.js)
- Full match history

---

## 🔧 Architectural Patterns

### 1. **Repository Pattern**
Separates data access logic from business logic:
```
├── repositories/interfaces.py    → abstract definitions
└── repositories/db_repository.py → concrete implementation
```

### 2. **Dependency Injection**
All services and repositories are injected via `dependencies.py`:
```python
get_league_service(...)
get_match_service(...)
get_cup_service(...)
```

### 3. **Strategy Pattern**
Used in points calculation (`points.py`):
```python
class PointsStrategy(ABC):
    @abstractmethod
    def calculate(self, ctx: PointsContext) -> int:
        pass
```

### 4. **Service Layer Pattern**
Business logic is isolated in the Services layer:
- LeagueService
- MatchService
- CupService
- VotingService
- AnalyticsService

---

## 🛣️ API Routes

### Public Routes (`routers/public.py`):
```
GET  /                             → Landing page
POST /create-league                → Create a new league
GET  /l/{slug}                     → League leaderboard
GET  /l/{slug}/matches             → Matches page
GET  /l/{slug}/cup                 → Cup page
GET  /l/{slug}/player/{id}         → Player profile
GET  /l/{slug}/hof                 → Hall of Fame
```

### Admin Routes (`routers/admin.py`) - requires JWT:
```
GET  /l/{slug}/admin               → Admin dashboard
POST /l/{slug}/admin/match         → Create match
PUT  /l/{slug}/admin/match/{id}    → Update match
DELETE /l/{slug}/admin/match/{id}  → Delete match
POST /l/{slug}/admin/cup/generate  → Generate cup
POST /l/{slug}/admin/season/end    → End season
POST /l/{slug}/admin/season/undo   → Undo end season
POST /l/{slug}/admin/settings/update → Update league settings
POST /l/{slug}/admin/player/add    → Add player
PUT  /l/{slug}/admin/player/{id}   → Update player
DELETE /l/{slug}/admin/player/{id} → Delete player
POST /l/{slug}/admin/team/create   → Create team
```

### Auth Routes (`routers/auth.py`):
```
GET  /login                        → Login page
POST /login                        → Perform login
GET  /logout                       → Logout
```

### Voting API (`routers/voting.py`):
```
GET  /api/voting/match/{id}/status → Voting status
GET  /api/voting/match/{id}/live   → Live voting stats
POST /api/voting/vote              → Submit vote
POST /api/voting/{slug}/open/{id}  → Open voting for a match (Admin)
POST /api/voting/{slug}/close/{id} → Close voting round (Admin)
```

---

## 🔒 Security

### 1. **JWT Authentication**
```python
# In core/security.py:
- create_access_token(): create access token
- verify_token(): validate token
- Token lifetime: 7 days
```

### 2. **Password Hashing**
```python
# Using passlib + bcrypt:
- get_password_hash(): hash password
- verify_password(): verify password
```

### 3. **Cookie-based Sessions**
```python
# JWT stored in httpOnly cookie:
response.set_cookie(
    key="access_token",
    value=f"Bearer {token}",
    httponly=True,
    samesite="lax"
)
```

### 4. **Anti-Cheat in Voting**
```python
# Anti-cheat layers:
1. localStorage: prevent duplicate browser votes
2. IP Limit: max 2 votes per IP
3. Fingerprint: unique device fingerprint
```

---

## 🧪 Tests

```
tests/
├── conftest.py                  → fixtures & shared setup
├── test_points.py              → points calculation tests
├── test_match_service.py       → match registration tests
├── test_league_service.py      → league / season tests
├── test_cup.py                 → cup system tests
├── test_voting_live.py         → voting tests
├── test_api_admin.py           → admin API tests
├── test_api_public.py          → public API tests
├── test_analytics_service.py   → analytics tests
└── test_repos.py               → repository tests
```

### Running tests:
```bash
pytest                          # run all tests
pytest tests/test_points.py    # run specific test file
pytest -v                      # verbose mode
```

---

## 📊 Available Statistics

### Player-level:
- Current season stats
- All-time stats
- Last season snapshot (for undo)
- Win rate
- Goal contribution per match (GA/Match)
- Form (Hot 🔥 / Cold ❄️)

### Match-level:
- Final score and per-player detailed stats
- MVP (from voting)
- Captain
- Bonus points

### League-level:
- Leaderboard
- Hall of Fame
- Cup bracket
- Total matches in current season

---

## 🎨 Frontend

### Technologies:
- **Vanilla JavaScript**: no frontend framework
- **Chart.js**: charts and visualizations
- **CSS Custom Properties**: theming
- **Font Awesome**: icons

### Main files:
```
static/
├── css/style.css               → styles
└── js/
    ├── main.js                → shared JS logic
    ├── admin_dashboard.js     → admin dashboard logic
    ├── leaderboard.js         → leaderboard page logic
    ├── matches.js             → matches page logic
    └── player_chart.js        → player chart rendering
```

---

## 🚀 Deployment

### Local development:
```bash
# 1. Create virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Run the app
uvicorn app.main:app --reload

# 4. Access
http://127.0.0.1:8000
```

### Production (Render.com):
- `render.yaml` is ready
- Requires PostgreSQL database
- Environment variables:
  ```
  DATABASE_URL=postgresql://...
  SECRET_KEY=...
  ```

---

## 🔄 Workflow

### 1. Create a new league:
```
User → fills the form (name + slug + password)
      ↓
System → creates League in the database
      ↓
      redirects to /l/{slug}
```

### 2. Register a match:
```
Admin → logs in with league password
       ↓
       goes to /l/{slug}/admin
       ↓
       enters match data + per-player stats
       ↓
MatchService → creates Match + MatchStats
              updates player statistics
              calculates points (PointsCalculator)
              resolves cup matchups (CupService)
       ↓
System → updates leaderboard
```

### 3. MVP voting:
```
Admin → opens voting for a match
       ↓
Players → vote (3 rounds)
       ↓
System → applies anti-cheat (IP + fingerprint)
         saves vote
       ↓
Admin → closes each round
       ↓
System → grants extra points to winners
```

### 4. End season:
```
Admin → clicks "End Season"
       ↓
LeagueService → stores winner in Hall of Fame
                moves stats to All-Time
                resets total_* fields to 0
                deletes current cup
       ↓
New season starts automatically
```

---

## 📝 Important Notes

### 1. **Arabic name normalization**
In `match_service.py`:
```python
def normalize_name(name: str) -> str:
    # Remove diacritics
    # Normalize Alef variants (أ إ آ ا)
    # Normalize Ya / Alef-Maqsura (ى ي)
    # Normalize Ta Marbuta (ة ه)
```

### 2. **Manual-style migrations**
In `main.py` → `lifespan()`:
- New columns are added automatically on app startup
- Safe: ignores columns that already exist

### 3. **Special cup cases**
- **Bye**: when players count is odd, one player advances automatically
- **Co-op Final**: if both finalists play on the same team in the final = shared win

### 4. **Goalkeeper clean sheet logic**
- ≤2 goals conceded = +10 pts
- 3–6 goals conceded = +4 pts
- >6 goals conceded = 0 pts

---

## 🔮 Future Roadmap (from `SAAS_PLAN.md`)

### Current stage:
✅ Multi-tenant architecture in place  
✅ Self-signup implemented  
✅ JWT Auth implemented  
✅ Slug-based routing  

### Needed for full SaaS:
❌ User accounts system  
❌ Pricing plans  
❌ Billing  
❌ Super Admin dashboard  
❌ Marketing / landing page  

---

## 🛠️ Development Tips

### 1. Adding a new feature:
```
1. Add Model in models/models.py
2. Add Schema in schemas/schemas.py
3. Add Repository methods in repositories/
4. Add Service logic in services/
5. Add Routes in routers/
6. Write tests in tests/
```

### 2. Modifying the points system:
```python
# In services/points.py:
# Add a new Strategy:
class MyCustomPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        # your logic here
        return points
        
# Register it in the calculator:
self.strategies.append(MyCustomPoints())
```

### 3. Adding a new badge:
```python
# In services/achievements.py:
class MyBadge(BadgeRule):
    def evaluate(self, player, history):
        # condition for earning the badge
        if condition:
            return {
                "name": "Badge Name",
                "icon": "🏅",
                "description": "Description"
            }
        return None
```

---

## 📚 Useful Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy ORM**: https://docs.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/
- **Chart.js**: https://www.chartjs.org/

---

**Last updated**: March 2026  
**Version**: 3.0  
**Status**: In production ✅