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

Startup seeds four reviewer accounts (admin, operator, and two clients). Their randomly generated passwords are in ignored `.run/reviewer-accounts.json`; README lists the usernames and how to obtain passwords. Repeated startup preserves existing users and credentials. Seeding is allowed only with DJANGO_DEBUG=True. You can create additional accounts through the admin screen or createsuperuser.

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

CheckOnly/SmokeTest also run the idempotent reviewer-account setup. To start both servers temporarily, check the page and API proxy, and shut down only those servers:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -SmokeTest -BackendPort 8001 -FrontendPort 5174
```

CI runs backend tests, checks for missing migrations, and builds React using an isolated PostgreSQL service. Its clearly labelled database password is a disposable CI fixture, not an application login or production credential. No deployment stretch item is claimed.

## Fresh-clone verification
+
+Verified on 1 October 2026 using remote commit `2cdfe52`, an empty clone directory, and a new PostgreSQL database. The clone initially contained no `.env`, `.venv`, frontend dependencies, or runtime files. Database connection values were supplied privately through process environment variables; the launcher generated `.env` and its Django secret on first run. Python, Node, and PostgreSQL were already installed as documented prerequisites.
+
+The single startup command installed dependencies, created the database, applied all migrations, seeded four reviewer users, built React, waited for both servers, and passed the smoke checks for the frontend page, API proxy, reviewer logins/roles, database health, and logout. The launcher then stopped its servers. Git confirmed credentials, dependencies, and runtime artifacts were ignored, with no tracked changes in the clone. CI passed all 102 backend tests and the frontend build. This verifies a clean clone on the development Windows machine, not a new operating-system installation.
+