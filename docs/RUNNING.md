# Run the whole project

Return to the [project overview](../README.md). This is a Windows local-development startup, not a public deployment.

## Prerequisites

Install Python 3.13, Node.js 22.12+ in the 22.x line, and PostgreSQL (developed with PostgreSQL 18). PostgreSQL must accept the credentials you provide. Its user needs database creation permission if the application database does not exist and for Django's separate test database. To start a stopped PostgreSQL Windows service, Windows may require an elevated terminal; an already running service needs no change. A remote database can also be configured in `.env`.

## One startup command

Clone the repository and open PowerShell in its root. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

The execution policy override applies only to this process. The script creates a virtual environment if needed, installs dependencies, and creates an ignored local `.env` if missing. It prompts for your PostgreSQL connection details without echoing the password and generates a local Django secret. Existing `.env` values are preserved. It starts an installed PostgreSQL Windows service if stopped, creates the named database only if absent, applies migrations, and checks Django.

When no active admin exists, the normal `createsuperuser` command prompts for your own account. No demo accounts or published credentials are seeded. Create clients/operators through the admin frontend after signing in. This deliberately differs from the assignment's seed-user request, following the candidate's preference.

The script installs frontend dependencies from the lockfile, builds React, and starts Django and Vite. Open `http://127.0.0.1:5173`. Keep the terminal open; Ctrl+C stops the servers started by this script. PostgreSQL remains running. Logs are in ignored `.run/*.log`. Django runs without autoreload in this launcher; restart it after backend code changes. Frontend edits still update through Vite.

If the default ports are already used, stop your previous servers or run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -BackendPort 8001 -FrontendPort 5174
```

The frontend proxy follows the chosen backend port. No existing database or accounts are overwritten. Install/update steps require internet access on a clean clone. Database passwords and Django secrets stay in `.env`, not Git or frontend code.

## Verification commands

```powershell
.\.venv\Scripts\python.exe manage.py test desk --noinput
```

To verify configuration, database setup, migrations, and the frontend build without starting servers:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -CheckOnly
```

An active admin must already exist for CheckOnly/SmokeTest. To start both servers temporarily, check the page and API proxy, and shut down only those servers:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -SmokeTest -BackendPort 8001 -FrontendPort 5174
```

CI runs backend tests, checks for missing migrations, and builds React using an isolated PostgreSQL service. Its clearly labelled database password is a disposable CI fixture, not an application login or production credential. No deployment stretch item is claimed.
