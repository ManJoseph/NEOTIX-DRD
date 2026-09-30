# NEOTIX Dataset Request Desk

Backend: Django REST Framework and PostgreSQL.
Frontend: a small React application (to be added later).

## Local backend setup (PowerShell)

1. Create the environment: `py -3.13 -m venv .venv`
2. Install dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and enter your local settings.
4. Create the PostgreSQL database named in `.env`.
5. Check configuration: `.\.venv\Scripts\python.exe manage.py check`

Models, migrations, endpoints, seed accounts, and tests will be added in the next stages.
Do not run initial migrations before we configure the project user model.

Never commit `.env`; it contains local secrets.

## Authentication choice

The API uses DRF token authentication, without Django's admin website or database sessions.
Protected requests will send `Authorization: Token <token>`.
The login endpoint and custom user roles will be added in later stages.
DRF stores tokens in a database table; this is a simple opaque token, not a JWT.
Use HTTPS in production. Built-in DRF tokens do not expire automatically.
