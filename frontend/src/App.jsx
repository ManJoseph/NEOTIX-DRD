import { useState } from "react";
import LoginForm from "./LoginForm";
import ClientRequests from "./ClientRequests";
import AdminUsers from "./AdminUsers";
import OperatorRequests from "./OperatorRequests";
import { apiRequest } from "./api";

export default function App() {
  // Keep credentials in React memory. Refreshing the page clears them.
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setError("");
    setLoggingOut(true);
    try {
      await apiRequest("/api/auth/logout/", "POST", null, session.token);
      setSession(null);
    } catch (error) {
      // Keep the session visible if the server could not revoke the token.
      setError(error.message);
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <main className="container">
      <header>
        <p className="brand">NEOTIX</p>
        <h1>Dataset Request Desk</h1>
        <p>Request, prepare, and review robot recording datasets.</p>
      </header>
      {!session ? <LoginForm onLogin={setSession} /> : (
        <>
        <section className="card account-card">
          <h2>Welcome, {session.user.name || session.user.username}</h2>
          <p>Signed in as <strong>{session.user.role}</strong>.</p>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="button" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? "Signing out…" : "Sign out"}
          </button>
        </section>
        {session.user.role === "admin" && <AdminUsers token={session.token} />}
        {session.user.role === "client" ? <ClientRequests token={session.token} /> : (
          <OperatorRequests token={session.token} />
        )}
        </>
      )}
    </main>
  );
}
