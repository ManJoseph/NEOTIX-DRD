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

The custom user model is configured. See the endpoint sections below. Create the first admin with createsuperuser, then create other accounts through the admin API. Demo accounts are not automatically seeded.
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

Import seed/episodes.csv using the endpoint below to populate your local inventory. Automated test data lives only in the separate test database.

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_assignment_api --verbosity 2
```

## CSV import (Postman)

POST to /api/episodes/import/ using an operator/admin token.
In Body > form-data, add key `file`, change its type from Text to File, and select
seed/episodes.csv. Let Postman set the multipart Content-Type automatically;
do not leave a manually set application/json Content-Type header on this request.

The UTF-8 upload limit is 5 MiB and 10,000 data records per file. Responses contain
imported, skipped, and skipped_rows (record number, episode_id, reason).
The supplied file imports 172 episodes and skips 19 records into an empty database
as of October 2026. Repeating the import adds zero and skips all 191 data records.
A 200 response means the file was processed; inspect skipped rows for validation
errors. File-level errors return 400 and cause no writes. API authorization failures
return 401/403. Other database errors roll back the import and return a server error.

Normalization trims values, uppercases episode IDs, lowercases robot/quality/task,
and collapses task whitespace. Valid quality=bad is imported, but remains ineligible
for assignment. Dates accept ISO timestamps and DD/MM/YYYY HH:MM. Offset-free
values use Kigali time; explicit offsets are respected. Future recordings are
rejected. All seven fields are required. Duration must be finite, positive, at most
3600 seconds, and representable with two decimal places. Empty/malformed rows,
unknown robots, unknown quality, and invalid values are reported as skipped.

First valid episode_id wins. Identical duplicates and conflicts have distinct
messages. Existing records are never overwritten, including assigned episodes.
Row numbers count CSV records (header is record 1), rather than physical lines
when quoted fields contain line breaks.

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_csv_import --verbosity 2
```

## Analytics API and scale

GET /api/analytics/?start_date=2026-08-01&end_date=2026-09-30 with an operator/admin
token. Both dates are required and inclusive in Africa/Kigali. Episodes are selected
by recorded_at; requests are selected by created_at (submission cohort). Request
status counts reflect their current status, not historical status at end_date.
The median uses submission to first delivery for selected requests that have been
delivered, even if delivery occurred after end_date. Never-delivered requests are
excluded from the median; an empty delivered set returns null.

The response includes episodes_per_day_per_robot, request_fulfilment
(counts_by_status and median_delivery_seconds), and top_good_tasks. Statuses with
no requests return zero. Only days/robots with recordings are listed. Good-task
counts use the recording date range and ties are ordered alphabetically.

All four report queries aggregate in PostgreSQL. Django's ORM produces GROUP BY
and COUNT queries; the median uses PostgreSQL percentile_cont(0.5) with parameterized
SQL. Python receives summary rows, not all underlying episodes or requests.

At 5 million episodes, Python memory stays proportional to summary size, but the
database still scans/aggregates matching rows. Narrow date ranges can use the
recorded_at/robot index; broad ranges may favor a sequential scan. Top-good-task
counts may benefit from a partial recorded_at/task index WHERE quality='good',
after measuring with EXPLAIN ANALYZE. Median sorting costs grow with delivered
requests. Frequent large reports would use cached results or daily summary tables;
add time partitioning only if measurements justify it. No 5-million-row benchmark
has been run. CSV import remains bounded and synchronous; large imports need a
separate streaming/batch process.

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_analytics --verbosity 2
```

## Health and structured request logging

GET /health with an Authorization: Token header. Like other protected endpoints,
it requires authentication. A reachable database returns:

```json
{"status": "ok", "database": "ok"}
```

Database connection failures return 503 with a generic message, including failures
while validating a token. This is a basic database-connectivity check, not a full
check of every table or pending migration.

Every request emits one JSON access log to the terminal with timestamp (UTC),
method, path, status, duration_ms, and authenticated user_id (null when unknown).
Successful login records the credential-verified user ID too. Bodies, passwords,
tokens, and query strings are omitted. Django's duplicate request summaries are
suppressed. Logs currently record access information rather than full stack traces;
production error monitoring is a next improvement. Local *.log files are ignored.

```powershell
.\.venv\Scripts\python.exe manage.py test desk.test_operations --verbosity 2
.\.venv\Scripts\python.exe manage.py test desk
```
