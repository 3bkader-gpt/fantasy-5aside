# 5-a-side Fantasy Football SaaS ⚽🏆

A modern, fast, and fully functional multi-tenant Fantasy Football web application built specifically for local, 5-a-side community matches (groups of friends, villages, company tournaments, etc.).

## 🌟 Features
- **Multi-Tenancy**: Anyone can create their own isolated "League" with a unique URL slug (`/l/my-league`) and a secure admin password.
- **Dynamic Players**: No need to pre-register players! Just type a name when entering match stats, and the player is automatically created and tracked.
- **Advanced Scoring System**: Points are calculated automatically based on goals, assists, saves, MVP awards, clean sheets, and winning matches.
- **Captain Chip**: Admins can designate a "Captain" for a match who receives **double points (x2)** for that specific game. 
- **Monthly Cup (Head-to-Head)**: Auto-generate a knockout tournament for the top 10 players based on current standings. Matchups resolve automatically when both players play in the same match!
- **Player Analytics Profile**: Click on any player to see their Win Rate, Goal Contribution per match, complete history, and All-Time stats.
- **Form Indicator**: Players on the leaderboard show a 🔥 (hot) or ❄️ (cold) indicator based on the points scored in their last 3 matches.
- **Hall of Fame & Seasons**: At the end of the month, the Admin can "End Season", archiving the winner to the Hall of Fame, moving current stats to All-Time stats, and resetting the leaderboard for a fresh start.

## 🧾 v3.0 Highlights
- **New Cup Engine**: Separate brackets for goalkeepers vs outfield players, automatic H2H resolution after each match, co‑op final rule (two winners if they play on the same team), and automatic progression between rounds.
- **Goalkeeper Overhaul**: GK `goals_conceded` is now auto‑calculated from opponent goals; scoring updated so every 3 saves = **+2 points** and every 4 goals conceded = **−1 point**.
- **Anti‑Cheat Voting System**: Triple‑layer protection against vote fraud (IP + browser fingerprint + localStorage) with fun sarcastic messages for cheaters.
- **Automated Seasons & Fixed Teams**: Seasons auto‑reset every 4 matches, with persistent fixed teams (A/B) and configurable team labels used across the UI.
- **Own Goals & Bonus System**: Own goals correctly apply a −1 penalty, and an improved BPS‑style bonus algorithm awards 3/2/1 bonus points per match.
- **Performance & DX**: Multiple DB resilience and indexing improvements, cleaner admin flows, and a refined UI/UX suitable for a polished portfolio project.

## 🛠️ Tech Stack
- **Backend**: Python 3, [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: 
  - Local: SQLite
  - Production: PostgreSQL (via SQLAlchemy ORM)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript, rendered server-side via Jinja2 Templates.

## 🚀 Running Locally (Development)

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd fantasy
   ```

2. **Set up a Virtual Environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   ```bash
   uvicorn app.main:app --reload
   ```
   *The app uses a local SQLite database by default (`data/fantasy.db`).*

5. **Access the App:** 
   Open your browser and navigate to `http://127.0.0.1:8000`

## ☁️ Deploying to Production (Render)

This repository includes a `render.yaml` Blueprint for 1-click deployments to [Render.com](https://render.com/).

1. Push your code to a GitHub repository.
2. Sign up/Log in to Render.com.
3. If using Render's free tier, you **must use PostgreSQL** because free disk storage is wiped continuously. Create a new **PostgreSQL Database** on Render.
4. Copy the "Internal Database URL" from your new Render Postgres DB.
5. In Render, go to **Blueprints** -> **New Blueprint Instance** and connect your GitHub repository.
6. Render will read the `render.yaml` file and prompt you to provide the `DATABASE_URL` environment variable.
7. Paste your PostgreSQL URL and click **Apply**.

**Security / environment (production):**
- Set `ENV=production` and `SECRET_KEY` to a strong random value.
- Set `CORS_ORIGINS` to a comma-separated list of allowed origins (e.g. `https://fantasy-5aside.onrender.com`). Use `*` only for development.
- Run `pip-audit -r requirements.txt` (or rely on CI) to check for known dependency vulnerabilities.

Render will automatically build and deploy your Fantasy SaaS! 🚀
