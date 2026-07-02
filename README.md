# Digilock — Module 2: Digital Shift Logbook

A working full-stack build: FastAPI + SQLite backend, single-page frontend served
from the same app (no separate frontend deploy needed).

## What's real here
- Every log entry, delete, and equipment status update hits SQLite (`digilock.db`) — reload the page and your data is still there.
- `GET /api/logs`, `POST /api/logs`, `DELETE /api/logs/{id}`, `GET/PUT /api/equipment`, `GET /api/stats` are live endpoints, not mocked JS.
- Interactive docs are auto-generated at `/docs` (Swagger UI) once running.

## Run it locally
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Open `http://localhost:8000` — frontend and API are on the same origin, so there's no CORS setup to fight.

## Deploy it for free — Render (recommended, ~2 minutes)
1. Push this `backend/` folder to a new GitHub repo (see git commands below).
2. Go to [render.com](https://render.com) → **New** → **Web Service** → connect the repo.
3. Render auto-detects `render.yaml` and fills in the build/start commands. Click **Deploy**.
4. You'll get a live URL like `https://digilock-module2.onrender.com` in a couple of minutes.

Free tier note: Render's free web services spin down after 15 minutes idle and take ~30s to
wake back up on the next request — that's Render's limit, not a bug in the app.

## Deploy it — Railway (also free tier, similarly fast)
1. Push to GitHub as above.
2. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Railway reads the `Procfile` automatically. Click **Deploy**.

## Deploy it — Docker (any host: Fly.io, a VPS, etc.)
```bash
docker build -t digilock .
docker run -p 8000:8000 digilock
```

## Push this folder to GitHub
```bash
cd backend
git init
git add .
git commit -m "Digilock Module 2 — Digital Shift Logbook"
git branch -M main
git remote add origin https://github.com/<your-username>/digilock-module2.git
git push -u origin main
```

## Notes on the SQLite database
SQLite here is a single file (`digilock.db`) — great for a demo/module prototype, but most
free-tier hosts (Render, Railway) use an ephemeral filesystem, so the DB resets on redeploy.
For anything beyond a demo, swap in a managed Postgres (Render and Railway both offer a free
Postgres instance) — the code only touches the DB through the `get_db()` helper in `main.py`,
so that's a small, contained change.
