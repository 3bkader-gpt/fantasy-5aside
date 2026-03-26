# ⚽🏆 5-a-side Fantasy Football SaaS

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg?logo=sqlalchemy&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

A modern, fast, and fully functional **Multi-tenant Fantasy Football SaaS** built specifically for local, 5-a-side community matches (groups of friends, villages, company tournaments, or local clubs).

Say goodbye to manual spreadsheets. Create your league, log the stats, and let the engine handle the H2H Cups, Leaderboards, and Hall of Fame!

---

## 🌟 Core Gameplay Features
- **Dynamic Players:** No need to pre-register players! Just type a name when entering match stats, and the player is automatically created, merged, and tracked.
- **Advanced Scoring Engine:** Points are calculated automatically based on goals, assists, saves, MVP awards, clean sheets, and match outcomes (including integer-division formulas for Goalkeeper saves and penalty deductions).
- **H2H Monthly Cup:** Auto-generates a knockout tournament for the top 10 players. Matchups resolve automatically when both players play in the same match, complete with a co-op final rule!
- **Player Analytics:** Deep-dive profiles showing Win Rate, Goal Contribution per match, All-Time stats, and interactive Form Indicators (🔥 Hot / ❄️ Cold).
- **Automated Seasons & Hall of Fame:** Seasons auto-reset every 4 matches (configurable). The winner is immortalized in the Hall of Fame, and current stats migrate to All-Time records.
- **Anti‑Cheat Voting System:** Triple‑layer protection against MVP vote fraud (IP + Browser Fingerprint + LocalStorage) with sarcastic warnings for cheaters.

## 🚀 Enterprise SaaS Capabilities (v3.0)
- **True Multi-Tenancy:** Anyone can sign up, complete the Onboarding Wizard, and instantly get their own isolated League with a unique URL slug (`/l/my-league`).
- **Superadmin Dashboard:** A secure, secret-header/Basic-Auth protected backdoor for platform owners to monitor all leagues, view platform metrics, and perform soft-deletes.
- **Asynchronous Background Workers:** Transactional emails (Verification/Reset) and VAPID Web Push notifications are processed via non-blocking `BackgroundTasks` and Database claim-locking for maximum UX performance.
- **Cloud Media Storage:** Native integration with **Supabase Storage** for Match Galleries, including automated bulk-cleanup tasks to prevent orphaned files and runaway costs.
- **Data Integrity:** Soft-delete mechanisms for Leagues, robust transactional boundaries, and proper timezone-aware token expirations.

---

## 📖 Architecture & Documentation

This project is meticulously documented. If you want to understand the inner workings, start here:
- 📚 **[Domain Docs Index](docs/README.md)** — Table of contents for Auth, League Lifecycle, Match Logic, Cup Engine, Points Calculator, and more.
- 🏗️ **[Project Architecture & Context](docs/project/context.md)** — System design and technical decisions.
- 🗺️ **[SaaS Master Plan](docs/project/saas_plan.md)** — The roadmap and feature checklist.

---

## 🛠️ Tech Stack
- **Backend**: Python 3, [FastAPI](https://fastapi.tiangolo.com/)
- **Database**:
  - Local/Testing: SQLite
  - Production: PostgreSQL (via SQLAlchemy ORM with advanced locking mechanisms)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (Server-side rendered via Jinja2)
- **Integrations**: Supabase (Media), Brevo (SMTP/Email), PyWebPush (Notifications)

---

## 💻 Running Locally (Development)

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd fantasy
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   ```bash
   uvicorn app.main:app --reload
   ```
   *The app uses a local SQLite database by default (`./data/fantasy.db`).*

5. **Access the App:** Open your browser and navigate to `http://127.0.0.1:8000`

---

## ☁️ Deploying to Production (Render)

This repository includes a `render.yaml` Blueprint for 1-click deployments to [Render.com](https://render.com/).

### Quick Deploy:
1. Create a new **PostgreSQL Database** on Render (Required: free disk storage is ephemeral).
2. Copy the \"Internal Database URL\".
3. Go to **Blueprints** -> **New Blueprint Instance**, connect your repo, and paste the `DATABASE_URL`.

### Crucial Production Variables:
- `ENV=production` (Enables secure cookies and production behaviors).
- `SECRET_KEY` = A strong, random 256-bit string for JWT and Sessions.
- `BASE_URL` = Your explicit HTTPS domain (e.g., `https://my-fantasy-saas.com`) to ensure absolute links in emails work perfectly.
- `CORS_ORIGINS` = Comma-separated list of allowed origins.

**Important Note on Proxy Headers:** Render terminates SSL at the load balancer. The `render.yaml` is pre-configured to run Uvicorn with `--proxy-headers --forwarded-allow-ips=\"*\"`. Do not remove this, or secure auth cookies will fail!

### Cloud Storage (Optional but Recommended):
To persist uploaded match photos across deploys, create a **Supabase** Storage bucket named `match-media` (set to Public) and add:
- `SUPABASE_PROJECT_URL` = `https://<your-project-ref>.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` = Your project’s service_role key.

*(Failed cloud uploads in production will safely fail-fast `HTTP 503` rather than falling back to ephemeral local storage).*

---
*Built with passion, caffeine, and lots of Python.* 🐍⚡
