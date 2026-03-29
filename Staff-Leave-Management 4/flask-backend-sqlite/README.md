# Flask Full Stack (SQLite) - Staff Leave Management

This is a Flask-only project using SQLite.
Both UI and API are served from one `run.py` process.

## Features converted

- Same API base and route paths: `/api/auth`, `/api/staff`, `/api/leaves`, `/api/notifications`, `/api/timetable`, `/api/settings`
- JWT auth with role checks (`staff`, `admin`)
- Leave workflow (apply, approve/reject, analytics, export CSV, replacement assignment)
- Password reset flow (token-based)
- SMTP settings endpoints + test email
- SQLite database via SQLAlchemy

## Project structure

- `run.py` - Flask entrypoint
- `seed.py` - seed admin/staff/timetable data
- `app/models.py` - DB models (SQLite)
- `app/routes/` - route blueprints
- `web/` - frontend static files served by Flask
- `.env.example` - environment template

## Run locally (single local link)

1. Create venv and install dependencies:

```bash
cd flask-backend-sqlite
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
```

3. Seed initial data:

```bash
python seed.py
```

4. Start server:

```bash
python run.py
```

Open `http://localhost:5001`.

- Frontend UI is served at `/`
- API is available at `/api/*`

## Frontend build path

By default Flask serves files from `./web`.
You can override with `FRONTEND_DIST` in `.env`.

## Default seeded users

- Admin: `admin@college.edu` / `Admin@123`
- Staff: `asha.verma@college.edu` / `Staff@123`
