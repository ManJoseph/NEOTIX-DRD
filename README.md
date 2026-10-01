# NEOTIX Dataset Request Desk

Dataset Request Desk replaces spreadsheets used to manage robot recording datasets. A client requests episodes of a task, such as a robot picking up a cup. An operator selects suitable recordings and delivers the dataset. The client then accepts it or requests rework.

## Who uses it?

| Role | Responsibilities |
| --- | --- |
| Client | Create requests, track only their own requests, accept or reject deliveries |
| Operator | Manage all requests, import episode metadata, assign suitable episodes, deliver datasets |
| Admin | Operator responsibilities plus account creation, deactivation, and role changes |

## Main workflow

```text
submitted → in_progress → delivered → accepted
                              ↓
                           rejected → in_progress (rework)
```

An episode can belong to only one current assignment. Only good or usable episodes with the matching task can be assigned. A request needs at least its requested episode count before delivery. The backend enforces authentication, role permissions, client ownership, and workflow rules, and records who changed each status and when.

## Technology and current progress

The backend uses Python, Django REST Framework, and PostgreSQL. It includes token authentication, account management, requests, assignments, repeat-safe CSV import, date-range analytics, health checks, structured logs, migrations, and automated tests.

The React frontend provides login/logout, client request creation/review, operator request and assignment workflows, and admin account creation. A single PowerShell command prepares and starts the local system; follow the running guide. Startup creates development-only reviewer accounts with generated local passwords; existing accounts are never reset.

## Quick start and tests

On Windows, install Python 3.13, Node.js 22.12+ in the 22.x line, and PostgreSQL, then clone the repository and run this command from its root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

On the first run, enter your local PostgreSQL connection details. The command creates `.env`, the database if missing, applies migrations, seeds reviewer accounts, installs/builds React, and starts both servers. Open `http://127.0.0.1:5173`. Keep the terminal open; Ctrl+C stops the app servers. For alternate ports and troubleshooting, see the [running guide](docs/RUNNING.md).

Run all backend tests with:

```powershell
.\.venv\Scripts\python.exe manage.py test desk --noinput
```

The database user needs permission to create Django's separate test database. CI also runs these tests and builds React. All 102 tests passed, and first-run startup was verified from a fresh remote clone against a new database; see the running guide for the verification record.

## Reviewer login credentials

| Username | Role | Password |
| --- | --- | --- |
| reviewer-admin | admin | Generated at startup; see local credential file below |
| reviewer-operator | operator | Generated at startup; see local credential file below |
| reviewer-client-a | client | Generated at startup; see local credential file below |
| reviewer-client-b | client | Generated at startup; see local credential file below |

Each password is recorded in `.run/reviewer-accounts.json` on your machine. Open that local file after startup to obtain the credentials; it is ignored by Git and is not uploaded. Passwords are hashed in PostgreSQL, are not printed to startup logs, and are preserved on repeated starts. Seeding requires `DJANGO_DEBUG=True` and is for local assessment review only. If a username already exists without its recorded password, it is left unchanged and the file shows null; use its existing password. Import `seed/episodes.csv` through the operator screen to populate inventory. No sample requests are created automatically.

## Analytics with 5 million episodes

Analytics groups/counts in PostgreSQL and calculates the median using `percentile_cont`; Python receives summaries rather than millions of records. Date/task indexes help relevant filters, but broad ranges still require database scans and aggregation. At that volume, measure query plans and consider cached daily summaries or a partial index for good episodes. No 5-million-row benchmark is claimed. Details are in the [backend guide](docs/BACKEND.md#analytics-health-and-logs).

## Documentation and useful files

| Start here | What you will find |
| --- | --- |
| [Running guide](docs/RUNNING.md) | One-command startup, prerequisites, first admin, ports, logs, and verification |
| [Backend guide](docs/BACKEND.md) | Installation, environment/database configuration, running tests, API reference, Postman walkthrough, model structure tables, ERD, and implementation explanations |
| [Frontend guide](docs/FRONTEND.md) | Running React, frontend file structure, login flow, and current progress |
| [Design notes](NOTES.md) | Decisions, assumptions, omissions, debugging, security, scale, and disclosed AI assistance |
| [Episode resources](seed/README.md) | Supplied CSV fixture and optional larger-data generator |
| [Dependency list](requirements.txt) | Pinned backend packages |
| [Environment template](.env.example) | Configuration keys to copy into your own ignored `.env` |
| [Database models](desk/models.py) | Application schema, relationships, constraints, and indexes |
| [Migrations](desk/migrations/) | Versioned database changes |
| [API routes](desk/urls.py) | Backend endpoint definitions |

To run the whole project, follow the [running guide](docs/RUNNING.md). For API/Postman examples, follow the [backend guide](docs/BACKEND.md). To understand the database, start with its [model tables](docs/BACKEND.md#model-structure-tables) and [ERD](docs/BACKEND.md#entity-relationship-diagram-erd).

This repository implements the NEOTIX Software Engineer technical assignment. The design notes identify remaining work and deliberate simplifications.
