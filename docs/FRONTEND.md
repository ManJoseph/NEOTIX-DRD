# Frontend guide

Return to the [project overview](../README.md). Django setup, accounts, and API rules are in the [backend guide](BACKEND.md).

## Current stage

The frontend provides login/logout and a client workspace for creating requests, listing their requests with pagination, and accepting/rejecting delivered requests. Admins can also create accounts and list users. The operator workspace is the next stage. This is not yet the complete required frontend.

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

Open `http://127.0.0.1:5173`. Log in using an account created through Django's `createsuperuser` command or the admin API. There are no demo passwords. Use `npm run build` to check that the frontend compiles; it creates ignored `frontend/dist` output. Use `npm install` when intentionally changing dependencies; commit the updated lockfile.

## Files and concepts

| File | Purpose |
| --- | --- |
| `frontend/package.json` | Dependencies and dev/build commands |
| `frontend/package-lock.json` | Exact dependency versions for repeatable installs |
| `frontend/index.html` | Browser HTML with the root element |
| `frontend/vite.config.js` | React build support and development API proxy |
| `frontend/src/main.jsx` | Mounts React into the root element |
| `frontend/src/App.jsx` | Stores the current login in memory; shows login or welcome; handles logout |
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

Manual checks: create a request with valid fields; verify count/date errors and that failed input stays in the form; refresh; review a delivered request; check that no review buttons appear on other statuses. Log in as a different client and verify that the first client's requests are absent. For pagination, use more than 50 requests in a testing environment. Operator/admin users currently see a placeholder, never the client creation screen.

## Create accounts to test the client screen

1. If you have no admin account yet, run `manage.py createsuperuser` using the backend guide's Python command. This is interactive: choose your own username, email, and password. Do not put them in source code.
2. Sign in to the frontend as that admin. The account creation form is shown only to admins; Django independently enforces admin permissions.
3. Enter a client's username, email, name, optional organisation, role Client, and a strong password. A success message confirms creation and refreshes the account list. Passwords are never returned in account output or stored in browser storage. Validation errors preserve account fields but clear the password for re-entry.
4. Sign out, then sign in using that client's username/password to test request creation and listing.
5. Repeat admin creation with role Operator to prepare for the operator workspace. Account deactivation and role changes remain available through the backend admin API; their frontend controls are not implemented in this stage.

Manual checks: create a client and log in as them, try a duplicate username/email, try a weak password, and verify that a client/operator cannot see the account screen. Server-side tests cover unauthorized access and password hashing; do not infer backend security from hidden UI controls alone.

New request deadlines must be today or later using Africa/Kigali. The date picker sets its minimum to the Kigali date; Django independently validates the deadline and returns a field error for past dates. Existing requests are allowed to become overdue.
