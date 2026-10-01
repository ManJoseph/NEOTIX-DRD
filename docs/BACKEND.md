# Backend developer guide

Read the root README first for setup and API examples. This guide explains how the backend fits together.

## Code map

| File | Responsibility |
| --- | --- |
| `manage.py` | Django commands: migrations, tests, shell, server, initial admin |
| Project `settings.py` | Environment/database settings, authentication, middleware, logging |
| `desk/models.py` | Database structure, choices, constraints, indexes, admin user manager |
| `desk/migrations/` | Versioned schema changes |
| `desk/serializers.py` | Allowed input/output fields and input validation |
| `desk/permissions.py` | Business-role access checks |
| `desk/views.py` | Endpoint actions, ownership, workflow rules, transactions |
| `desk/urls.py` | API route → view mapping |
| `desk/pagination.py` | 50-record list pages |
| `desk/csv_import.py` | CSV parsing, normalization, validation, import reports |
| `desk/analytics.py` | Database aggregates and median query |
| `desk/middleware.py` | Request timing and JSON access logs |
| `desk/exceptions.py` | Safe database-unavailability responses |
| `desk/throttles.py` | Login attempt rate limit |
| `desk/tests.py`, `desk/test_*.py` | Automated behavior checks |

## How a request travels through the code

The URL selects a view. DRF's default token authentication identifies the caller; permissions determine whether their role may use the action. A client ownership filter limits the records they can access. A serializer checks supplied fields. The view applies cross-record business rules and writes through models into PostgreSQL. The response serializer formats the result. Request middleware surrounds this work, measures elapsed time, and emits a JSON log.

Authentication answers “who is calling?” Permissions answer “may they perform this action?” An ownership query answers “may they access this particular request?” All three are needed. Login explicitly allows unauthenticated access. The default for other actions is authenticated access, with additional role checks where needed.

## Models and relationships

`User`: standard Django username, unique email, hashed password, activity flags, plus name, organisation, and client/operator/admin role. `DeskUserManager` makes `createsuperuser` also set the business admin role. A Django superuser flag and the business role are different concepts; API authorization checks the business role.

`Episode`: one imported recording's metadata. Numeric `id` is the internal primary key; unique `episode_id` is the recording system's external ID. Duration is a decimal, not a float. Robot/quality choices make valid names explicit.

`DatasetRequest`: client foreign key, task, requested count, deadline, notes, current status, creation/update times, and nullable first delivery time. One client can have many requests.

`Assignment`: request foreign key, episode one-to-one field, assigning user foreign key, assignment timestamp. One request can have many assignments; one episode can have at most one current assignment. Deleting the link frees the episode without deleting its metadata.

`StatusChange`: request foreign key, previous/new status, actor foreign key, and timestamp. Initial submission uses an empty previous status. Rework adds events rather than replacing old history.

Business foreign keys use `PROTECT`, preventing accidental ORM deletion of referenced records. Database constraints reject invalid role/status/robot/quality values, nonpositive duration/count, and duplicate unique IDs or assignments. Model `save()` does not automatically run every validator: API/import validation and database constraints serve different purposes.

## Why the extra Django tables exist

`django_migrations` tracks applied migrations. `django_content_type` identifies models for Django's auth framework. `auth_group`, `auth_permission`, and their join tables support inherited Django permissions/groups. User group/permission join tables come from `AbstractUser`. `authtoken_token` associates opaque tokens with users. Our custom user table replaces `auth_user`; sessions and Django admin tables are not installed. Built-in permission data is retained for Django compatibility while business authorization uses `role`.

## Constraints versus indexes

A constraint rejects invalid stored data. An index helps PostgreSQL locate or order matching data. Primary keys, unique fields, foreign keys, and the episode one-to-one relationship create indexes automatically. Django also creates pattern lookup indexes for certain unique text fields on PostgreSQL.

Explicit indexes are episode `(recorded_at, robot_id)` for date-oriented inventory statistics, episode `(task_name, quality)` for selection filters, and request `created_at` for submission-date reports. Indexes cost storage and writes. They do not guarantee a fast full-table aggregation; inspect actual plans before adding more.

## Workflow and safe writes

| From | To | Allowed role |
| --- | --- | --- |
| submitted | in_progress | operator/admin |
| in_progress | delivered | operator/admin; enough assignments required |
| delivered | accepted | owning client |
| delivered | rejected | owning client |
| rejected | in_progress | operator/admin |

Other transitions are rejected. Status names being valid does not make every transition valid. Ownership is enforced consistently for detail, history, assignments, and client review.

`transaction.atomic()` groups writes so a failure rolls them back together. `select_for_update()` locks selected rows until that transaction finishes. Request creation saves its initial history atomically. Status changes lock the request and save status/history together. Assignment changes lock the same request, coordinating with the delivery count check; creation also locks the episode and repeats eligibility checks. Database uniqueness is the final duplicate guard. Expected uniqueness conflicts are translated into readable errors; unrelated integrity errors are not disguised.

Serializers check ordinary input and can pre-check duplicate assignments. A pre-check alone cannot prevent two simultaneous callers from claiming the same episode; transactions and database uniqueness handle that race. Request owners and assignment actors come from the authenticated user rather than input JSON.

## CSV and analytics implementation

The importer uses Python's CSV parser so quoting and embedded commas work. It parses the bounded file before database writes, validates each record, then uses `get_or_create` on the canonical unique ID. Value errors produce skip reasons; unexpected database failures roll back all writes. Existing records are compared for identical/conflicting duplicate reports, never overwritten. See README for formats, limits, and fixture counts.

Analytics uses a half-open timestamp interval: start-date midnight ≤ timestamp < midnight after end-date. This includes the complete end date without relying on an artificial last second. Three ORM queries group/count records; a parameterized PostgreSQL percentile query computes the median. Only aggregate results reach Python.

## Learning and changing the backend

Inspect serializer validation without saving anything:

```powershell
.\.venv\Scripts\python.exe manage.py shell
```

```python
from desk.serializers import DatasetRequestSerializer
serializer = DatasetRequestSerializer(data={
    "task_name": "Pick Cup", "episodes_requested": 0,
    "deadline": "2026-10-04", "notes": "Learning example",
})
serializer.is_valid()
serializer.errors
```

Create a new serializer with a positive count and inspect `validated_data` to see the normalized task. No database record is created until `save()` is called. In tests, `cls` refers to the test class in `setUpTestData`; `self` refers to one test instance. `assertRaises` passes only when the expected exception occurs.

For a model change: edit the model, run `manage.py makemigrations`, inspect the generated migration, run `manage.py migrate`, then test the affected behavior. Commit migrations with the code. Never rewrite an already shared migration to hide a later change. For an API change, update writable fields, permissions, business checks, tests, and README examples together.

Test modules cover models, serializers, auth/admin, requests, assignments, CSV, analytics, and operations. Use the root README's single test command before pushing behavior changes. A serializer-only check does not replace API permission tests or database constraint checks.

## Operational limits

Login throttling uses a process-local cache and is approximate. Production needs a shared cache and stronger rate limiting. `/health` is authenticated and checks connectivity, not full schema readiness. JSON access logs omit sensitive input; comprehensive error monitoring remains future work. Tokens are long-lived and shared per user. Development settings are not a deployment configuration. Frontend and whole-system startup remain separate remaining milestones.
