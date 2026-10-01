# Design notes

## Design and decisions

PostgreSQL is the source of truth for accounts, episode metadata, requests, assignments, and status history. `User` extends Django's user model with name, organisation, and a business role. Each request belongs to one client. An assignment links a request to an episode and records the assigning user/time. Each status change records its request, previous/new status, actor, and timestamp. The request stores current status and first delivery time; history preserves transitions. Django migrations manage the schema.

Three decisions required the most care:

1. **Episode exclusivity and concurrent changes.** A one-to-one episode link prevents two current assignments at the database level. API transactions lock the request before assignment changes or delivery; assignment creation also locks its episode and repeats eligibility checks. Status and history are saved together. Removing an assignment releases the episode; accepted requests retain theirs. Removed assignments have no separate audit history. Sequential conflicts and database uniqueness are tested; concurrent load has not been stress-tested.
2. **Messy imports without destructive updates.** Normalize IDs, tasks, robots, and quality, then keep the first valid row for an ID. Identical duplicates and conflicts have separate skip reasons. Updating existing metadata could silently change delivered datasets, so imports never overwrite it. Invalid rows are reported and skipped; malformed files fail before writes, and unexpected database errors roll back the import. The simple importer is synchronous and bounded to 5 MiB/10,000 records.
3. **Meaning of analytics dates and delivery time.** Date ranges are inclusive Kigali dates. Requests form a submission-date cohort; counts show current status. Median time uses first delivery, including delivery after the selected range. Rework does not reset that timestamp. PostgreSQL performs aggregation, including a short parameterized SQL median query.

Additional interpretations: assigned episodes must match the request's normalized task; duration cannot exceed one hour; future recordings are invalid; new request deadlines must be today or later in Kigali time, following candidate review. Robots are restricted to the five supplied IDs.

## Simplifications and next steps

Explicit APIView methods and ordinary serializers keep the code readable. Django auth/contenttypes support tables remain, but the Django admin website and sessions are disabled. There is no public signup; reviewer accounts are seeded by local startup; additional accounts use createsuperuser or the admin API. Following the final assessment review, startup seeds four development-only reviewer users. Passwords are generated locally and recorded in an ignored file, rather than published as fixed credentials; README documents their usernames and password location. Repeated runs never reset existing accounts.

The React client/operator workflows, CSV upload, and admin account creation are implemented. A single PowerShell launcher prepares the local database, migrations, first admin, API, and frontend with installed Python/Node/PostgreSQL prerequisites. GitHub Actions checks migrations, runs backend tests, and builds React. There is no Docker setup, public deployment, or optional stretch item. Startup seeds reviewer users; normal admin account creation remains available. Account/history lists are unpaginated. Request editing/deletion, removed-assignment history, expiring tokens, asynchronous import, and full error monitoring are omitted.

With two more days, add a repeatable browser test against an isolated real backend, provide a cross-platform container startup, improve production configuration and token lifecycle, paginate remaining lists, and test competing assignments against PostgreSQL concurrently. Keep the core business rules ahead of optional features.

## A problem found while building

Duration validation originally used the float `0.01` as its minimum. Binary floating-point cannot represent that decimal exactly, making comparison with a decimal field unsafe at the boundary. During importer validation review, the minimum was changed to `Decimal("0.01")`; a regression test verifies that exactly 0.01 seconds is accepted. Migration 0002 records the validator change without changing the stored decimal type. Boundary checks matter even when normal values work. Fresh-clone testing also exposed a startup race: Vite served the page before Django accepted connections, causing a proxy ECONNREFUSED error. Inspecting the separate server logs identified it; the launcher now waits for both the frontend page and the authenticated API response before reporting readiness.

## Security

Django hashes passwords and applies its password validators. Output serializers exclude passwords; account creation uses `create_user`, not direct plaintext storage. DRF database tokens authenticate every action except login. Logout and account deactivation revoke tokens. Tokens do not expire automatically and one token is shared across a user's logins. HTTPS is required for a production deployment. Secrets belong in ignored `.env` files, never source code.

Explicit writable fields prevent callers from selecting request owners, assignment actors, or initial statuses. Server permissions and ownership-filtered queries protect every request route. Serializers/import validation give readable errors; database uniqueness/check constraints provide a final guard. SQL parameters protect analytics inputs. Logs omit credentials and bodies. Login has approximate per-IP throttling using local-memory cache.

The two main concerns are **token theft**, because a stolen long-lived bearer token grants access until revoked, and **broken object-level authorization**, because a missed ownership check could expose another client's dataset. Production improvements include short-lived/rotated credentials, HTTPS, shared-cache/edge rate limits, and continued ownership regression tests. Development DEBUG/localhost settings must be replaced before deployment; current logs are access records rather than complete error monitoring.

## Scale

At 10× users, local-memory throttling becomes inconsistent across workers, and unpaginated account/history endpoints become less suitable. Use shared cache, pagination, measured database connection management, and multiple API workers. Assignment transactions deliberately serialize changes to the same request.

At 100× episodes, synchronous per-row import queries and broad analytics scans are likely early bottlenecks. Python analytics memory remains proportional to summary output, but PostgreSQL still does grouping and median sorting. The existing episode date/robot and task/quality indexes help relevant filters, not every large aggregation. Measure query plans; consider a partial date/task index for good episodes, cached daily aggregates, and streamed/batched background imports. Time partitioning should follow measurements. No large-volume benchmark has been run.

## AI tooling and validation

OpenAI Codex assisted with understanding the brief, explanations, scaffolding, models, serializers, views, migrations, tests, debugging, and documentation. The candidate chose the stack and reviewed stages through questions about managers, constraints, authentication, ownership, transactions, import, and logging. AI assistance is disclosed rather than presented as unaided work; the candidate must still be able to explain and modify the submitted code.

The full CI backend test run passed 102 tests covering models, serializers, role/ownership permissions, the status transition matrix, assignment rules, import idempotency/rollback, analytics boundaries/medians, health, and logging. The frontend build passed. A one-off headless browser smoke test with mocked API responses exercised account/request creation, past-date blocking, multipart upload/reporting, assignment/removal, delivery, rejection/rework/acceptance, and mobile layout with no JavaScript errors. A separate launcher smoke test started both real servers, checked the frontend and Django proxy, then cleaned up its processes. Full browser-to-real-database end-to-end testing and a fresh-machine install have not been performed. These checks do not claim production readiness.
