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

## Request workflow API

| Method | Path | Purpose |
| --- | --- | --- |
| GET / POST | /api/requests/ | List visible requests / client creates a request |
| GET | /api/requests/<id>/ | View a visible request |
| GET | /api/requests/<id>/history/ | View chronological status history |
| POST | /api/requests/<id>/status/ | Change status according to role and workflow |

Clients see only their own requests; operators/admins see all. Only clients create
requests. Request lists return count, next, previous, and results, with 50 records
per page; use ?page=2 for the next page. Other clients' request IDs return 404.
Request editing and deletion are not offered in this version.

Example request creation, using a client token:

```json
{"task_name": "pick cup", "episodes_requested": 3, "deadline": "2026-10-03", "notes": "Training data"}
```

POST to /api/requests/<id>/status/ with an operator/admin token:

```json
{"status": "in_progress"}
```

Delivery uses {"status": "delivered"} and requires at least the requested count
of assigned episodes. Assignment endpoints will be added in the next stage.
The owning client reviews delivery with {"status": "accepted"} or
{"status": "rejected"}. An operator/admin can return a rejected request to
in_progress for rework. Status responses return the updated request.

Run workflow tests:

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_request_api --verbosity 2
```

## Episode and assignment API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/episodes/ | Operator/admin episode inventory |
| GET | /api/requests/<id>/assignments/ | Assignments for a visible request |
| POST | /api/requests/<id>/assignments/ | Operator/admin assigns an episode |
| DELETE | /api/requests/<id>/assignments/<assignment-id>/ | Operator/admin removes an assignment |

Inventory example: /api/episodes/?task_name=pick%20cup&quality=good&available=true
Filters are exact matches after normalizing casing/whitespace. Quality accepts
good/usable/bad. available=true means unassigned; available=false means assigned.
An available episode can still have bad quality, so use the quality filter too.
Episode and assignment lists use the same 50-record paginated response as requests.
Clients cannot browse inventory but can read assignment metadata for their own requests.

Assign using the episode's internal numeric id from inventory results:

```json
{"episode": 12}
```

Assignments only change while the request is in_progress. Eligible episodes have
good/usable quality, the same task as the request, and no existing assignment.
The URL chooses the request and the token chooses the operator. Responses include
episode_details for reviewing metadata. Removal deletes only the assignment and
releases its episode for reuse. Returned status is 204. After client rejection,
return the request to in_progress before replacing episodes.

CSV import is the next stage; the test data lives only in the separate test database.

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_assignment_api --verbosity 2
```
