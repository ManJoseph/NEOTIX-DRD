# Frontend guide

Return to the [project overview](../README.md). Django setup, accounts, and API rules are in the [backend guide](BACKEND.md).

## Current stage

The first frontend stage provides login, a signed-in welcome screen showing the user's business role, and logout. Client requests and operator assignment screens are the next stages. This is not yet the complete required frontend.

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
| `frontend/src/LoginForm.jsx` | Username/password fields, submission, loading, and errors |
| `frontend/src/api.js` | Ordinary fetch requests, JSON, token header, and error messages |
| `frontend/src/styles.css` | Plain CSS for the page and form |

`useState` stores values that can change and cause React to redraw the screen. `onChange` updates form values. `onSubmit` calls our handler; `preventDefault` prevents a browser page reload. `async`/`await` waits for the API response. `onLogin` is a function passed from App to LoginForm so the form can report a successful login.

The browser sends `/api/auth/login/` to Vite on port 5173. Vite forwards `/api` requests to Django on port 8000. Django returns a token and safe user details; App stores them in memory. Protected API calls include `Authorization: Token <token>`. No token or password is written to browser storage. Refresh clears the local login but does not revoke the server token; successful logout calls Django to revoke it. A failed logout keeps the session visible and displays the error.

The development proxy avoids cross-origin browser requests without changing Django permissions. It does not enforce authorization: Django remains responsible for that. The proxy is a development feature; production hosting and API routing remain to be configured. No frontend environment secrets are needed.

## Manual checks

Try valid login, invalid login, an empty form, logout, and login while Django is stopped. Password input is hidden, fields have labels, submission buttons disable while waiting, and errors are shown on the page. After refreshing, the sign-in form should return. Backend authentication tests already cover server-side account/permission behavior; a build alone does not verify browser behavior.

Reference documentation: [React useState](https://react.dev/reference/react/useState), [Vite guide](https://vite.dev/guide/), [Vite development proxy](https://vite.dev/config/server-options.html#server-proxy).
