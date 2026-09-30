# NEOTIX Dataset Request Desk

Backend: Django REST Framework and PostgreSQL.
Frontend: a small React application (to be added later).

## Local backend setup (PowerShell)

1. Create the environment: `py -3.13 -m venv .venv`
2. Install dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and enter your local settings.
4. Create the PostgreSQL database named in `.env`.
5. Check configuration: `.\.venv\Scripts\python.exe manage.py check`

6. Apply migrations: `.\.venv\Scripts\python.exe manage.py migrate`
7. Run tests: `.\.venv\Scripts\python.exe manage.py test desk`
8. Create an application admin: `.\.venv\Scripts\python.exe manage.py createsuperuser`

The custom user model is configured. Endpoints and seed accounts will be added in later stages.
Django tests use a separate test database; the local database user needs permission to create it.

Never commit `.env`; it contains local secrets.

## Authentication choice

The API uses DRF token authentication, without Django's admin website or database sessions.
Protected requests will send `Authorization: Token <token>`.
The login endpoint and custom user roles will be added in later stages.
DRF stores tokens in a database table; this is a simple opaque token, not a JWT.
Use HTTPS in production. Built-in DRF tokens do not expire automatically.

## Testing serializers from the terminal

Run all serializer tests:

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_serializers --verbosity 2
```

Run one test class:

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_serializers.AccountSerializerTests --verbosity 2
```

Explore input validation interactively (does not save records unless you call save):

```powershell
.\.venv\Scripts\python.exe manage.py shell
```

```python
from desk.serializers import DatasetRequestSerializer
serializer = DatasetRequestSerializer(data={"task_name": "Pick Cup", "episodes_requested": 0, "deadline": "2026-10-03"})
serializer.is_valid()
serializer.errors
```

Change the count to 3, construct a new serializer, run is_valid again, and inspect
serializer.validated_data. Type exit() to leave the shell.

## Authentication and admin API (Postman)

Create your first admin interactively:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Use http://127.0.0.1:8000 as the base URL.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /api/auth/login/ | Login with username and password; returns token and user |
| GET | /api/auth/me/ | Current user details |
| POST | /api/auth/logout/ | Delete current token; returns 204 |
| GET / POST | /api/users/ | Admin lists or creates accounts |
| GET / PATCH | /api/users/<id>/ | Admin reads an account or changes role/is_active |

For login, choose Body > raw > JSON in Postman:

```json
{"username": "your-admin-username", "password": "your-admin-password"}
```

For all other endpoints, add a header: `Authorization: Token <returned-token>`.
Use Content-Type: application/json for JSON request bodies.

Example account creation (admin only):

```json
{
  "username": "client@example.com",
  "email": "client@example.com",
  "name": "Example Client",
  "organisation": "Example Robotics",
  "role": "client",
  "password": "Choose-a-strong-local-password!42"
}
```

To change a role, PATCH with `{"role": "operator"}`. To deactivate, PATCH with
`{"is_active": false}`. Deactivation also deletes the user's token. An admin
cannot deactivate themselves or remove their own admin role. There is no DELETE
endpoint and no public registration endpoint. Login is limited to 20 attempts
per minute per IP with the development process's local cache.

Run authentication and admin endpoint tests:

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_auth_api --verbosity 2
```
