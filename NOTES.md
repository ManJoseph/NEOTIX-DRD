# Design notes (work in progress)

## Data model

One Django app (`desk`) holds five models. User extends Django AbstractUser and
adds name, organisation, and a client/operator/admin role. Username remains the
standard login identifier; seed usernames will equal their email addresses.
Email is unique. Passwords use Django's password hashing. Users are deactivated
with is_active rather than deleted. createsuperuser also sets the business admin role.

A DatasetRequest belongs to one user (the API will require a client), and records
the task, count, deadline, notes, current status, creation/update time, and first
delivery time. First delivery time stays unchanged on rework, so analytics will
measure submission to first delivery. StatusChange stores each transition, its
actor, and timestamp, including an initial submission event with empty from_status.
The API will write the status update and history event in one database transaction.

Episode stores CSV metadata, not video files. episode_id is a unique external ID;
the internal numeric id is used for relationships. Decimal durations preserve
values such as 45.5 seconds. Known robots are a fixed list from the supplied pack.

Assignment links a request to one episode, with the assigning user and time.
The episode link is unique, so concurrent assignments cannot claim the same
episode twice. Removing an assignment releases that episode. Assignment removal
will be allowed only while working on a request; assignments remain reserved
after acceptance. Historical assignment tracking is outside this first version.
PROTECT relationships prevent accidental deletion of referenced business records.

## Constraints and indexes

Database checks reject unknown roles, statuses, qualities, and robots, non-positive
episode duration, and requests with fewer than one requested episode. choices
and validators also support readable validation errors, but save() does not
automatically run full model validation. Database constraints provide another guard.

Primary keys and unique fields have indexes automatically. ForeignKey fields
also have indexes; OneToOneField supplies a unique index. Explicit indexes are:
- Episode (recorded_at, robot_id): date-range analytics and robot grouping input.
- Episode (task_name, quality): episode selection by task and quality.
- DatasetRequest created_at: date-range filtering for request analytics.

Indexes speed relevant reads but cost disk space and writes. A large date range
may still require scanning many rows. Query plans and production data will guide
further indexing; these indexes do not guarantee every aggregate is fast.

Cross-table rules (eligible quality, client ownership, actor role, enough episodes
for delivery) and valid workflow transitions belong in the API stage. A choices
list restricts valid status names; it does not enforce transition order.

## Authentication and simplifications

DRF database tokens are used without sessions or the Django admin website.
Built-in tokens do not expire automatically. Logout will revoke the token.
Use HTTPS in production. Django auth/contenttypes tables are retained to reuse
the standard user framework; business authorization will check the role field.

## AI tooling

Codex helped explain the requirements, configure the project, and draft models,
migrations, and tests. Work is reviewed in stages with the candidate. Remaining
security, scale, omissions, and debugging notes will be completed as work proceeds.

PostgreSQL also has Django-generated varchar_pattern_ops indexes on unique text
fields (episode_id, username, email). The unique indexes enforce exact uniqueness;
the extra pattern indexes support suitable text-prefix lookups such as startswith.
All current indexes use PostgreSQL B-tree, its standard ordered lookup structure.
The desk_user_groups and desk_user_user_permissions tables are join tables for
inherited Django many-to-many relationships. auth_group_permissions joins groups
to permissions. django_migrations records migration names and application times;
django_content_type identifies models; authtoken_token connects a token to a user.
There is no auth_user table because AUTH_USER_MODEL selects desk.User instead.
There are no Django admin or session tables.

## Serializer stage

Serializers use explicit field lists. User output excludes passwords and Django
permission flags. Episode and history serializers are output-only. Request input
can set task, count, deadline, and notes; owner, status, and timestamps are read-only.
Read-only input is ignored by DRF. The upcoming view must supply the authenticated
client when saving and write initial history in the same transaction.
Task names are lowercased and internal whitespace is collapsed; import and episode
filtering will use the same convention. Dates are checked for valid date syntax;
we have not imposed a rule against past deadlines because the brief does not require it.
Assignment input accepts only an episode id. It rejects bad quality and existing
assignments with readable errors. This pre-check cannot prevent concurrent claims;
the upcoming view will also handle database uniqueness errors safely.
RequestStatusSerializer accepts known status names only; transition rules and actor
permissions remain for the upcoming workflow view. Serializers do not yet expose URLs.

Admin account input now uses separate creation and update serializers. Creation
uses Django password validators and create_user to hash passwords; password is
write-only. Only role and is_active are writable in the update serializer. Neither
serializer accepts Django is_superuser/is_staff flags. These serializers do not
check who is calling them: their views must be admin-only. There is no public signup.

## Authentication API stage

APIView classes use explicit get/post/patch methods. Login uses Django authenticate
and reuses an existing DRF token. Invalid credentials and inactive users get the
same 401 response. Logout deletes the current token. Admin-only permission checks
the business role, not is_staff or is_superuser. Deactivation revokes the token;
role changes are effective on subsequent requests because authentication reloads
the user. Admins cannot deactivate/demote themselves. Account lists are currently
unpaginated, acceptable for the small user set; pagination is a next improvement.

Login throttling limits attempts per IP using Django's local-memory cache. This
is a development safeguard, not full brute-force protection. A multi-process
production deployment needs shared cache and edge rate limiting; DRF throttling
is approximate under concurrency. There is one token per user, so logout affects
all clients using it. Login endpoint disables token authentication to allow login
even if a caller sends a stale token. Seed users are still a later stage.

## Request workflow stage

One shared queryset helper restricts client access across request lists, detail,
history, and transitions. Other clients' records return 404. Operators/admins can
view all records but cannot create client requests or accept/reject deliveries.
Request creation writes a submission event atomically. Status changes lock the
request row with select_for_update, validate role and transition order, check the
assigned count for delivery, and save status plus history in one transaction.
Failure to write history rolls back the request creation or status update.

The upcoming assignment/removal views must lock the same request row before
changing its assignments; this coordinates those actions with delivery checks.
The delivery threshold is at least the requested count. First delivery time is
retained on rework. Request lists are paginated by 50. History is chronological
and currently unpaginated because the expected event count per request is small.
There are no generic update/delete request routes that could bypass the workflow.
Tests cover every pair of statuses for each business role, ownership, the delivery
threshold, rework timestamps, pagination, and rollback if audit creation fails.

## Episode assignment stage

Operators/admins browse inventory with exact normalized task/quality filters and
optional assignment availability. Clients can only read assignments on owned
requests. Inventory and assignment lists are paginated; assignment output embeds
episode metadata, with select_related to avoid one episode query per assignment.

Assignment creation/removal is restricted to in_progress, preventing changes to
an already delivered selection. We require task names to match: this is a deliberate
interpretation of client task requirements beyond the explicit quality/exclusivity
rules. Rejected deliveries must return to in_progress for rework. Removal releases
an episode; accepted deliveries continue reserving their episodes.

Assignment creation locks the request first, then the episode, and rechecks quality
and availability after the locks. The same request lock coordinates assignment
changes with delivery counts. Database uniqueness remains a final guard, with an
inner transaction savepoint for clean recovery from expected duplicate conflicts.
Unexpected integrity errors are re-raised. No concurrency stress test has been run
in this stage; sequential API conflicts and database uniqueness are tested.
