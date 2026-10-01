# Frontend guide

Return to the [project overview](../README.md). Django setup, accounts, and API rules are in the [backend guide](BACKEND.md).

## Current stage

The frontend provides login/logout and a client workspace for creating requests, listing their requests with pagination, and accepting/rejecting delivered requests. Admins can also create accounts and list users. Operators/admins can list all requests, import CSV metadata, manage operational status, and assign/remove episodes. This covers the required client/operator screens; the running guide provides whole-system startup. Browser workflow verification is tracked separately.

## Run locally

Prerequisites: Node.js 22.12 or newer in the 22.x release line (the development machine uses 22.17), or a supported newer Node release, and the configured Django backend.

Start Django in a terminal at the repository root:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Log in using an account created through Django's `createsuperuser` command or the admin API. Reviewer usernames and the local generated-password file are described in README. Use `npm run build` to check that the frontend compiles; it creates ignored `frontend/dist` output. Use `npm install` when intentionally changing dependencies; commit the updated lockfile.

## Files and concepts

| File | Purpose |
| --- | --- |
| `frontend/package.json` | Dependencies and dev/build commands |
| `frontend/package-lock.json` | Exact dependency versions for repeatable installs |
| `frontend/index.html` | Browser HTML with the root element |
| `frontend/vite.config.js` | React build support and development API proxy |
| `frontend/src/main.jsx` | Mounts React into the root element |
| `frontend/src/App.jsx` | Stores the current login in memory; shows login or welcome; handles logout |
| `frontend/src/EpisodeImport.jsx` | CSV file selection, upload, and paginated skipped-record report |
| `frontend/src/OperatorRequests.jsx` | All requests, pagination, and request selection |
| `frontend/src/OperatorRequest.jsx` | Selected request details and operational status changes |
| `frontend/src/EpisodeAssignments.jsx` | Filter available episodes, assign/remove links, and paginate both lists |
| `frontend/src/UserForm.jsx` | Admin account creation with role selection and password validation feedback |
| `frontend/src/AdminUsers.jsx` | Admin-only account list and creation screen |
| `frontend/src/RequestForm.jsx` | Client request fields, validation feedback, and submission |
| `frontend/src/ClientRequests.jsx` | Loads requests, paginates, refreshes, and reviews deliveries |
| `frontend/src/LoginForm.jsx` | Username/password fields, submission, loading, and errors |
| `frontend/src/api.js` | Ordinary fetch requests, JSON, token header, and error messages |
| `frontend/src/styles.css` | Plain CSS for the page and form |

`useState` stores values that can change and cause React to redraw the screen. `onChange` updates form values. `onSubmit` calls our handler; `preventDefault` prevents a browser page reload. `async`/`await` waits for the API response. `onLogin` is a function passed from App to LoginForm so the form can report a successful login.

The browser sends `/api/auth/login/` to Vite on port 5173. Vite forwards `/api` requests to Django on port 8000. Django returns a token and safe user details; App stores them in memory. Protected API calls include `Authorization: Token <token>`. No token or password is written to browser storage. Refresh clears the local login but does not revoke the server token; successful logout calls Django to revoke it. A failed logout keeps the session visible and displays the error.

The development proxy avoids cross-origin browser requests without changing Django permissions. It does not enforce authorization: Django remains responsible for that. The proxy is a development feature; production hosting and API routing remain to be configured. No frontend environment secrets are needed.

## Manual checks

Try valid login, invalid login, an empty form, logout, and login while Django is stopped. Password input is hidden, fields have labels, submission buttons disable while waiting, and errors are shown on the page. After refreshing, the sign-in form should return. Backend authentication tests already cover server-side account/permission behavior; a build alone does not verify browser behavior.

Reference documentation: [React useState](https://react.dev/reference/react/useState), [Vite guide](https://vite.dev/guide/), [Vite development proxy](https://vite.dev/config/server-options.html#server-proxy).

## Client request stage

After a client logs in, App renders ClientRequests and passes its token. RequestForm sends only task, count, deadline, and notes; Django supplies ownership and initial status. A successful creation clears the form and reloads page one so the newest request is visible. Failed submissions preserve entered values.

ClientRequests uses `useEffect` to load data when the token, page, or reload counter changes. Its cleanup ignores responses for an old screen/page. The API's `results` are the displayed records; `count` and `next` drive pagination. Refresh fetches current operator changes. Accept/reject buttons appear only for delivered requests; Django still enforces ownership and valid transitions. Review success replaces that request with the API's updated record. The `(current) => ...` state update uses the latest list rather than an older captured value.

Manual checks: create a request with valid fields; verify count/date errors and that failed input stays in the form; refresh; review a delivered request; check that no review buttons appear on other statuses. Log in as a different client and verify that the first client's requests are absent. For pagination, use more than 50 requests in a testing environment. Operator/admin users see the operator workspace, never the client creation screen.

## Create accounts to test the client screen

1. Whole-system startup seeds reviewer-admin; obtain its generated password from the local credential file described in README. For manual backend setup, you can instead run createsuperuser. Do not put personal credentials in source code.
2. Sign in to the frontend as that admin. The account creation form is shown only to admins; Django independently enforces admin permissions.
3. Enter a client's username, email, name, optional organisation, role Client, and a strong password. A success message confirms creation and refreshes the account list. Passwords are never returned in account output or stored in browser storage. Validation errors preserve account fields but clear the password for re-entry.
4. Sign out, then sign in using that client's username/password to test request creation and listing.
5. Repeat admin creation with role Operator to test the operator workspace. Account deactivation and role changes remain available through the backend admin API; their frontend controls are not implemented in this stage.

Manual checks: create a client and log in as them, try a duplicate username/email, try a weak password, and verify that a client/operator cannot see the account screen. Server-side tests cover unauthorized access and password hashing; do not infer backend security from hidden UI controls alone.

New request deadlines must be today or later using Africa/Kigali. The date picker sets its minimum to the Kigali date; Django independently validates the deadline and returns a field error for past dates. Existing requests are allowed to become overdue.

## Operator workflow

Log in as an operator/admin. Open a request from All requests. Start work moves submitted to in_progress; Start rework moves rejected to in_progress. The assignment area defaults to the request's task and good quality, showing only available inventory. Apply filters explicitly rather than sending a query for every keystroke. Choose usable quality to include usable recordings. All qualities may show bad recordings, but their assignment buttons are disabled. A different task can be browsed, but only matching tasks can be assigned.

Assign adds an episode using its numeric ID; Remove deletes the assignment using its assignment ID. Both actions reload inventory and assignments. The total assignment count comes from the paginated API's count, not just the current page length. Delivery enables when the known count meets the requested count. Django repeats eligibility and delivery checks, so another operator's concurrent changes produce readable errors rather than bypassing rules. Refresh request or Refresh episodes to obtain current data.

After delivery, assignment editing disappears. The client reviews through their own screen. On rejection, the operator starts rework before changing the selected episodes. Each list has its own pagination controls. `key={selectedId}` resets the detail component's state when opening another request. Effect cleanup prevents older fetch responses from replacing the newly selected screen's data.

If inventory is empty, upload `seed/episodes.csv` using Import episode metadata before testing assignments. Manual checks: start work, assign an eligible episode, remove it, verify delivery stays disabled below the required count, deliver, reject as the client, refresh as operator, start rework, and deliver again. Check more than 50 records to verify pagination. A headless browser smoke check with mocked API responses passed these actions, including rejection/rework/acceptance. A full browser test against a real isolated database remains future work; compilation alone does not verify these actions.

## CSV upload stage

Operators and admins see Import episode metadata above the request list. Choose `seed/episodes.csv` and click Import CSV. The form uses `FormData`, a browser container for file uploads, rather than JSON. The API helper leaves Content-Type unset for FormData so the browser supplies the correct multipart boundary; it still includes the token header. Django validates the file and enforces permissions and limits independently of the UI.

The report displays imported/skipped totals and each skipped record's number, ID, and reason. A processed file may have skipped rows and is not presented as an all-rows-success result. Skipped-record tables show 20 records per page, with no truncation of the available report. The selected file remains available for a repeat import; changing it clears the old report. Import success increments an inventory version passed to the assignment component, causing its lists to reload without losing the selected request or its filters.

Manual checks: upload the supplied fixture, inspect invalid and duplicate reasons, upload it again and verify zero new imports, try an invalid header, and try an oversized file. Confirm that the same token is required for uploads and that clients do not see the import form. File-level errors show on the form without a misleading old report. The backend CSV tests cover parsing, limits, normalization, duplicate conflicts, idempotency, and rollback.

Reference: [MDN FormData uploads](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API/Using_FormData_Objects).

For one-command startup of both servers, use the [running guide](RUNNING.md). Vite reads the optional BACKEND_URL process environment value set by that launcher; normal npm run dev defaults to port 8000. CI builds the frontend on pushes and pull requests.

Final checks: 99 backend tests passed, no missing migrations, frontend build passed, the real-server startup/proxy smoke test passed, and a one-off mocked browser workflow check passed with no JavaScript errors or mobile overflow. The mocked browser check used existing local testing tools and did not seed or change the development database. It is not a CI browser test.
