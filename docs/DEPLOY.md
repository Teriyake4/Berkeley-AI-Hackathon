# Deployment Guide

How to deploy Nos (Next.js + FastAPI + Redis). For architecture details see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Quick start: Railway + Redis Cloud

You need **two Railway services** (backend + frontend) and **one Redis Cloud database**. Do not add Railway's Redis plugin if you are using Redis Cloud.

```mermaid
flowchart LR
  Browser --> Frontend["Next.js (Railway)"]
  Frontend -->|PYTHON_BACKEND_URL| Backend["FastAPI (Railway)"]
  Backend --> Redis["Redis Cloud"]
  Backend --> Claude["Anthropic API"]
```

### Step 0 — Push deploy config to GitHub

Railway builds from your repo. Make sure these files are on `main`:

- `Dockerfile`, `Dockerfile.dev`
- `backend/Dockerfile`
- `railway.frontend.toml`, `railway.backend.toml`
- `docker-compose.prod.yml`

```bash
git add Dockerfile Dockerfile.dev backend/Dockerfile railway.*.toml docs/DEPLOY.md docker-compose*.yml backend/main.py .env.example README.md
git commit -m "Add Railway production deploy config"
git push origin main
```

### Step 1 — Create Redis Cloud database

1. Go to [Redis Cloud](https://redis.io/cloud/) and create a free database.
2. Open the database → **Connect** → copy the **public** connection URL.
3. It should look like:
   ```
   rediss://default:YOUR_PASSWORD@YOUR_HOST.redis.cloud:12345
   ```
4. Use `rediss://` (TLS), not `redis://`.
5. In Redis Cloud **Security / ACL**, allow connections from anywhere (`0.0.0.0/0`) unless you know Railway's egress IPs. Railway IPs change, so open access is typical for hackathon deploys.

### Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
2. Select `Berkeley-AI-Hackathon`.
3. Railway may create one service automatically — you will end up with **two** services total (no Redis service on Railway).

### Step 3 — Deploy backend (`nos-backend`)

1. If Railway auto-created a service, rename it to `nos-backend`. Otherwise: **+ New** → **GitHub Repo** → same repo.
2. **Settings** tab:
   - **Root Directory:** leave empty (repo root)
   - **Config file path:** `railway.backend.toml`
3. **Variables** tab — add these on the **backend service only**:

   | Variable | Value |
   |----------|-------|
   | `REDIS_URL` | Your Redis Cloud URL (`rediss://...`) |
   | `ANTHROPIC_API_KEY` | Your Anthropic key |
   | `DEEPGRAM_API_KEY` | Optional — live mic STT |

4. **Networking** → **Generate Domain** → copy the URL (e.g. `https://nos-backend-production.up.railway.app`).
5. Wait for deploy to finish. Verify:
   ```bash
   curl https://YOUR-BACKEND-URL.up.railway.app/
   # → {"service":"nos-backend","status":"ok"}

   curl https://YOUR-BACKEND-URL.up.railway.app/api/status
   # → services.redis.connected should be true
   ```

   If `redis.connected` is `false`, double-check `REDIS_URL` (must be `rediss://`, password URL-encoded if it has special characters).

### Step 4 — Deploy frontend (`nos-frontend`)

1. **+ New** → **GitHub Repo** → same repo again (second service in the monorepo).
2. Rename to `nos-frontend`.
3. **Settings** tab:
   - **Root Directory:** leave empty
   - **Config file path:** `railway.frontend.toml`
4. **Variables** tab:

   | Variable | Value |
   |----------|-------|
   | `PYTHON_BACKEND_URL` | Backend URL from step 3 (no trailing slash) |

   Example: `https://nos-backend-production.up.railway.app`

   Optional: use Railway private networking if both services are in the same project:
   `http://nos-backend.railway.internal:8000` (exact name shown in backend service settings).

   Do **not** set `REDIS_URL` on the frontend.

5. **Networking** → **Generate Domain** — this is your public app URL.

### Step 5 — Smoke test

Open the frontend URL:

1. Dashboard connection indicator shows **connected** (SSE).
2. Click **Demo** — transcript, timeline, insights update.
3. **Generate Handoff Report** — modal populates.
4. Run a **Live** session, leave, then open **Session Log** (`/logs`) — session should appear (proves Redis Cloud persistence).

---

## Alternative: Railway's built-in Redis

If you prefer Railway-managed Redis instead of Redis Cloud:

1. **+ New** → **Database** → **Add Redis**.
2. On the backend service set `REDIS_URL=${{Redis.REDIS_URL}}` (reference variable from the Redis service).
3. Skip Redis Cloud entirely — do not run both.

---

## Docker images (local)

| File | Use |
|------|-----|
| `Dockerfile` | Production Next.js (`npm run build` + `npm run start`) |
| `Dockerfile.dev` | Local dev with hot reload |
| `backend/Dockerfile` | FastAPI; build context is repo root |

### Local prod test with Redis Cloud

```bash
cp .env.example .env
# Set REDIS_URL=rediss://... and ANTHROPIC_API_KEY=...
docker compose -f docker-compose.prod.yml up --build
```

Open [http://localhost:3000](http://localhost:3000).

### Local dev (bundled Redis container)

```bash
docker compose up --build
```

---

## Environment reference

| Variable | Service | Required | Notes |
|----------|---------|----------|-------|
| `REDIS_URL` | Backend only | Yes (for session logs) | Redis Cloud `rediss://` URL |
| `ANTHROPIC_API_KEY` | Backend | For real AI | Heuristic fallbacks without it |
| `DEEPGRAM_API_KEY` | Backend | Optional | Live mic STT |
| `PYTHON_BACKEND_URL` | Frontend | Yes | Backend public or internal URL |
| `CORS_ORIGINS` | Backend | Optional | Only if browser hits backend directly |
| `PORT` | Both | Auto | Injected by Railway |

---

## Production checklist

- [ ] Deploy config pushed to GitHub `main`
- [ ] Redis Cloud database created; `rediss://` URL copied
- [ ] Backend deployed; `/api/status` shows `redis.connected: true`
- [ ] Frontend deployed with `PYTHON_BACKEND_URL` pointing at backend
- [ ] Demo mode works on frontend URL
- [ ] Live session appears in `/logs` after ending (Redis persistence)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `redis.connected: false` | Wrong URL, TLS, or ACL | Use `rediss://`; allow `0.0.0.0/0` in Redis Cloud; URL-encode password |
| Dashboard never "connected" | Wrong `PYTHON_BACKEND_URL` | Set backend public URL on frontend; redeploy frontend |
| Demo works, sessions not saved | Redis not connected | Fix backend `REDIS_URL`; check `/api/status` |
| Build fails on Railway | Old Dockerfile | Ensure `railway.backend.toml` / `railway.frontend.toml` config paths are set |
| Camera/mic blocked | No HTTPS | Use Railway-generated HTTPS domain |
