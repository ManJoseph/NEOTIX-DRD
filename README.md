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

The React frontend provides login/logout, client request creation/review, operator request and assignment workflows, and admin account creation. Startup for the whole system is also pending; current backend instructions describe local development.

## Documentation and useful files

| Start here | What you will find |
| --- | --- |
| [Backend guide](docs/BACKEND.md) | Installation, environment/database configuration, running tests, API reference, Postman walkthrough, model structure tables, ERD, and implementation explanations |
| [Frontend guide](docs/FRONTEND.md) | Running React, frontend file structure, login flow, and current progress |
| [Design notes](NOTES.md) | Decisions, assumptions, omissions, debugging, security, scale, and disclosed AI assistance |
| [Episode resources](seed/README.md) | Supplied CSV fixture and optional larger-data generator |
| [Dependency list](requirements.txt) | Pinned backend packages |
| [Environment template](.env.example) | Configuration keys to copy into your own ignored `.env` |
| [Database models](desk/models.py) | Application schema, relationships, constraints, and indexes |
| [Migrations](desk/migrations/) | Versioned database changes |
| [API routes](desk/urls.py) | Backend endpoint definitions |

To run the project or try a client/operator scenario, follow the [backend guide](docs/BACKEND.md#run-the-backend-windows-powershell). To understand the database, start with its [model tables](docs/BACKEND.md#model-structure-tables) and [ERD](docs/BACKEND.md#entity-relationship-diagram-erd).

This repository implements the NEOTIX Software Engineer technical assignment. The design notes identify remaining work and deliberate simplifications.
