# Deploying eNaviga

The app deploys as **one service**: the FastAPI backend also serves the built
React site, so the whole thing lives at a single web address. That keeps login
cookies first-party (no cross-site cookie problems in Safari/Chrome) and needs
no CORS setup. The [Dockerfile](Dockerfile) builds it; it runs on any Docker
host. The steps below use **Render**.

## 1. Create the service on Render

1. Sign up at <https://render.com> (signing in with GitHub is easiest).
2. **New → Web Service** → connect GitHub → pick the `byahetabai` repository.
3. Settings:
   - **Branch:** the branch you want live (e.g. `main`)
   - **Language / Runtime:** Docker (detected from the Dockerfile)
   - **Region:** Singapore (closest to the Atlas cluster and the Philippines)
   - **Instance type:** *Starter* for client demos (always on). *Free* works but
     sleeps after ~15 minutes idle and takes a minute or more to wake up.
4. **Environment variables:** add every line from your local `backend/demo.env`
   (never committed). The required keys are:

   | Key | Value |
   |---|---|
   | `MONGO_URL` | Atlas connection string |
   | `DB_NAME` | database for this deployment (e.g. `enaviga_demo`) |
   | `JWT_SECRET` | long random string, unique per deployment |
   | `COOKIE_SECURE` | `true` (Render serves HTTPS) |
   | `COOKIE_SAMESITE` | `lax` |
   | `TRUSTED_PROXY_HOPS` | `1` |
   | `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_DISPLAY_NAME` | master admin |

   `PORT` is set by Render automatically. `CORS_ORIGINS` isn't needed (same
   address), but may be set to the service URL.
5. **Create Web Service.** The first build takes several minutes.

## 2. Let Render into MongoDB Atlas

Atlas only accepts connections from approved IP addresses.

1. In Render, open the service → **Connect** (top right) → **Outbound** tab and
   copy the listed IP addresses/ranges.
2. In Atlas → **Security → Network Access → Add IP Address**, add each one
   (comment: `Render`).
3. In Render, **Manual Deploy → Restart service** if the first start failed to
   reach the database (`SSL handshake failed` in the logs).

## 3. First-time database setup

Run once per new database, from your PC (`backend` folder), with the deployment's
values:

```powershell
$env:DB_NAME="enaviga_demo"; $env:ADMIN_EMAIL="..."; $env:ADMIN_PASSWORD="..."; .\.venv\Scripts\python seed.py
```

`seed.py` creates the admin plus demo data (demo agent, sample packages).

## 4. Updating

Push to the deployed branch — Render rebuilds and redeploys automatically.

## Notes

- Agent logos are stored in MongoDB (`stored_files`), so uploads work on any host.
- To rename the admin later: `scripts/update_admin.py` (usage inside).
- Health check: `GET /api/` returns `{"message": "Hello World"}`.
