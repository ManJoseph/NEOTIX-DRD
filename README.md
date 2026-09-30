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
