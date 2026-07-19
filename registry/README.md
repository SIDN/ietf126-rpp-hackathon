# Registry

A small full-stack app with a FastAPI backend and a React + TypeScript (Vite) web UI.

## Structure

```
registry/
├── backend/          FastAPI REST API
│   ├── app/
│   │   ├── main.py    App entry point (routes, CORS)
│   │   ├── models.py  Pydantic schemas
│   │   ├── store.py   In-memory data store
│   │   ├── api/       API routers
│   │   └── core/      Configuration
│   └── requirements.txt
├── frontend/         React + TypeScript + Vite web UI
│   └── src/
│       ├── api.ts     Typed client for the backend API
│       └── App.tsx    Main UI (list/add/delete entries)
└── start.sh          Starts backend + frontend together
```

## Quick start

```bash
./start.sh
```

This creates the backend virtualenv and installs frontend dependencies on
first run, then starts both the backend and frontend together. Stop both
with Ctrl+C.

Use `--port` / `--frontend-port` to run an additional, independent instance
alongside the default one:

```bash
./start.sh --port 8010 --frontend-port 5183
```

## Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API base URL: `http://localhost:8000/api`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `GET /api/health`
- Entries CRUD: `GET/POST /api/entries`, `GET/PATCH/DELETE /api/entries/{id}`
- Domains: `GET/POST /api/domains`, `GET /api/domains/{name}` — tracks which
  registrar currently sponsors each domain name.
- Transfers use a **pull model with a transfer token**, similar to real
  domain registries:
  - Every domain has a secret `transfer_token` attribute, generated when the
    domain is created.
  - `GET /api/domains/{name}/auth-info` returns that token. It's meant to be
    requested by the domain's current (losing) registrar and shared
    out-of-band with whoever wants to gain the domain.
  - `POST /api/domains/{name}/transfer` is called by the **gaining**
    registrar with `{ "gaining_registrar": "...", "transfer_token": "..." }`.
    The registry only applies the transfer if the token matches the
    domain's current one - this is how the losing registrar's authorization
    is verified. A `403` is returned if it doesn't match.
  - On a successful transfer the token is rotated (a new one is generated),
    so the old token can't be reused for another transfer.
  - See the [registrar app](../registrar) for a UI that drives this.

Data is stored in memory and resets when the server restarts. A couple of
demo domains (`example.com`, `example.org`) are seeded on startup.

## Frontend (React + TypeScript + Vite)

```bash
cd frontend
npm install
npm run dev
```

- Web UI: `http://localhost:5173`
- Configure the API URL via `frontend/.env` (`VITE_API_URL`, defaults to `http://localhost:8000/api`)

Run the backend first (or alongside) so the UI can load and manage entries.
