# NEOTIX Dataset Request Desk

An internal platform for requesting robot recording datasets. Clients submit requests, operators select suitable episodes and deliver them, and clients accept or reject the delivery.

Backend: Python 3.13, Django 5.2, Django REST Framework, PostgreSQL. Dependencies are pinned in `requirements.txt`. The backend is implemented; the React frontend and whole-system startup command are pending. This is currently a local development setup.

## Run the backend (Windows PowerShell)

Prerequisites: Python 3.13 and a running PostgreSQL server. Clone this repository and open PowerShell in its root:

```powershell
git clone https://github.com/ManJoseph/NEOTIX-DRD.git
cd NEOTIX-DRD
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally. Set `DJANGO_SECRET_KEY` to a newly generated secret, `DJANGO_DEBUG=True` for development, and `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` to your PostgreSQL connection settings. Generate a Django secret with:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Create an empty PostgreSQL database matching `DB_NAME`, using pgAdmin or PostgreSQL's `createdb` tool. The application does not create this database. Then run:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

`createsuperuser` prompts for your own username, email, and password and assigns the application `admin` role. There is no Django admin website. Use the admin API to create client/operator accounts. Demo users are not seeded and there are no shared login credentials. `.env`, `.venv`, and local log files are ignored by Git.

Base URL: `http://127.0.0.1:8000`. Subsequent backend starts need only the `runserver` command while PostgreSQL is running. On Linux/macOS, create a virtual environment with `python3 -m venv .venv` and substitute `.venv/bin/python` for the Windows Python path.

## Run tests

```powershell
.\.venv\Scripts\python.exe manage.py test desk --noinput
```

Tests create and remove a separate `test_<DB_NAME>` database; the configured database user needs permission to create it. They do not populate your development database. The last full backend run passed all 97 tests. To focus on one area, replace `desk` with, for example, `desk.test_csv_import` or `desk.test_request_api`.

## Authentication and roles

POST `/api/auth/login/` with JSON:

```json
{"username": "<your username>", "password": "<your password>"}
```

Copy `token` from the response. All other endpoints, including `/health`, require the header `Authorization: Token <token>`. Use `Content-Type: application/json` for JSON bodies. These are opaque DRF database tokens, not JWTs. Tokens have no automatic expiry; logout revokes the user's token. One token is shared across that user's logins.

Clients can create requests and read/review only their own. Operators can read all requests, import inventory, assign episodes, change operational status, and read analytics. Admins have operator permissions plus account management. Authorization is enforced by the backend.

## API reference

All paths below are relative to the base URL. Keep trailing slashes except for `/health`.

| Method | Path | Access / purpose |
| --- | --- | --- |
| POST | `/api/auth/login/` | Public; username/password login |
| GET | `/api/auth/me/` | Authenticated; own profile |
| POST | `/api/auth/logout/` | Authenticated; revoke token, 204 |
| GET / POST | `/api/users/` | Admin; list/create accounts |
| GET / PATCH | `/api/users/<id>/` | Admin; read account/change role or activity |
| GET / POST | `/api/requests/` | List visible requests / client creates request |
| GET | `/api/requests/<id>/` | Read a visible request |
| GET | `/api/requests/<id>/history/` | Read its chronological status history |
| POST | `/api/requests/<id>/status/` | Role and transition restricted |
| GET | `/api/episodes/` | Operator/admin; filter inventory |
| POST | `/api/episodes/import/` | Operator/admin; upload CSV |
| GET / POST | `/api/requests/<id>/assignments/` | Read visible assignments / operator assigns |
| DELETE | `/api/requests/<id>/assignments/<assignment-id>/` | Operator/admin; remove assignment, 204 |
| GET | `/api/analytics/` | Operator/admin; date-range report |
| GET | `/health` | Authenticated; database connectivity |

Request, inventory, and assignment lists have 50 records per page and return `count`, `next`, `previous`, `results`. Use `?page=2`. User lists and status history are currently unpaginated. Successful creates return 201; other successful reads/updates return 200 unless shown above.

Validation errors return 400; missing/invalid credentials 401; denied roles 403; missing records or another client's requests 404. Database connectivity failures return a generic 503. Read-only input fields are ignored; the server supplies ownership, actors, status, and timestamps. There is no public registration or generic request update/delete endpoint.

## Postman walkthrough

1. Log in as your admin. POST `/api/users/` to create a client and an operator, choosing a password for each:

```json
{
  "username": "client@example.com",
  "email": "client@example.com",
  "name": "Example Client",
  "organisation": "Example Robotics",
  "role": "client",
  "password": "<choose a strong password>"
}
```

For the operator, choose a different username/email and `"role": "operator"`. Passwords are validated and hashed. PATCH a user's URL with `{"role":"operator"}` or `{"is_active":false}` to manage them. Deactivation revokes their token. Admins cannot deactivate or demote themselves.

2. Log in as the operator. POST `/api/episodes/import/`: Body → form-data, key `file`, type File, select `seed/episodes.csv`. Let Postman set the multipart Content-Type; remove any manually configured JSON Content-Type.
3. Log in as the client and POST `/api/requests/`:

```json
{"task_name":"pick cup","episodes_requested":1,"deadline":"2026-10-04","notes":"Training dataset"}
```

4. Save the returned request `id`. Using the operator token, POST its `/status/` URL with `{"status":"in_progress"}`.
5. GET `/api/episodes/?task_name=pick%20cup&quality=good&available=true`. Choose a returned episode's numeric `id`. POST the request's `/assignments/` URL with `{"episode":12}`, substituting that ID. The external `episode_id` such as `EP00001` is not the assignment input ID.
6. POST `/status/` with `{"status":"delivered"}`. Delivery requires at least the requested number of assignments.
7. Using the owning client's token, POST `/status/` with `{"status":"accepted"}` or `{"status":"rejected"}`. GET `/history/` to see who changed each status and when.
8. For rework, the operator moves `rejected` back to `in_progress`, removes/replaces assignments, and delivers again. DELETE an assignment releases its episode. Assignments can change only in `in_progress`.

Only good/usable, unassigned episodes with a matching normalized task can be assigned. Inventory quality filters accept `good`, `usable`, or `bad`; availability accepts `true` or `false`. Availability alone does not imply eligible quality. A client's attempt to read another client's request returns 404.

## CSV behavior

Required columns: `episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality`. Header order may vary. UTF-8 (including BOM) uploads are limited to 5 MiB and 10,000 data records.

Values are trimmed; IDs uppercased; robot/quality/task lowercased; task whitespace collapsed. Known robots are `arm-01`, `arm-02`, `arm-03`, `mobile-01`, `humanoid-01`. Dates accept ISO timestamps or `DD/MM/YYYY HH:MM`; timestamps without offsets use Kigali time. Future recordings are skipped. Durations must be finite, positive, at most 3600 seconds, and fit two decimal places. Bad quality is valid inventory but cannot be assigned.

The first valid canonical episode ID wins. Identical duplicates and conflicting duplicates are skipped with different reasons; existing metadata is never overwritten. Responses contain `imported`, `skipped`, and `skipped_rows` with record number, episode ID, and reason. Record numbering includes the header and counts CSV records rather than physical lines. A 200 response can contain skipped rows: inspect the report.

The supplied fixture imports 172 and skips 19 records into an empty database with the October 2026 test clock. A repeat imports zero and skips 191. File syntax/header errors return 400 before writes. Invalid individual rows are skipped; unexpected database failures roll back the entire import.

## Analytics, health, and logs

GET `/api/analytics/?start_date=2026-08-01&end_date=2026-09-30`. Both dates are required, inclusive in `Africa/Kigali`. Output contains `episodes_per_day_per_robot`, `request_fulfilment` (`counts_by_status`, `median_delivery_seconds`), and `top_good_tasks`.

Episode statistics use recording dates. Requests use submission dates and their current status. The median measures submission to first delivery, even if delivery is outside the selected range; never-delivered requests are excluded. Empty medians return null, missing status counts zero. Top-task ties use alphabetical order.

Three ORM aggregation queries and one parameterized PostgreSQL `percentile_cont(0.5)` query compute results in the database. With 5 million episodes, Python receives only summary rows, but PostgreSQL still scans and aggregates matching data. Narrow ranges can benefit from the date/robot index; broad ranges may use sequential scans. Measure with `EXPLAIN ANALYZE` before adding indexes; frequent reports could use cached/daily summaries. No 5-million-row benchmark was performed.

GET `/health` returns `{"status":"ok","database":"ok"}` after a database connectivity check. It does not verify every table or migration. Request middleware writes one JSON console line containing UTC timestamp, method, path, status, duration_ms, and authenticated user_id (otherwise null). Tokens, passwords, bodies, and query strings are omitted. Full exception monitoring is not implemented.

See [backend developer guide](docs/BACKEND.md) for code structure and database explanations, and [design notes](NOTES.md) for tradeoffs, security, scale, AI usage, and remaining work.
