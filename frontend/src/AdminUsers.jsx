import { useEffect, useState } from "react";
import UserForm from "./UserForm";
import { apiRequest } from "./api";

export default function AdminUsers({ token }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    async function loadUsers() {
      setLoading(true);
      setError("");
      try {
        const result = await apiRequest("/api/users/", "GET", null, token);
        if (active) setUsers(result);
      } catch (error) {
        if (active) setError(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadUsers();
    return () => { active = false; };
  }, [token, reload]);

  function handleCreated(user) {
    setMessage(`Account created for ${user.username}. They can now sign in.`);
    setReload((current) => current + 1);
  }

  return (
    <div className="workspace">
      <UserForm token={token} onCreated={handleCreated} />
      <section className="card" aria-labelledby="accounts-title">
        <div className="section-heading">
          <h2 id="accounts-title">Accounts</h2>
          <button type="button" disabled={loading}
            onClick={() => setReload((current) => current + 1)}>Refresh</button>
        </div>
        {message && <p role="status">{message}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {loading ? <p role="status">Loading accounts…</p> : !error && (
          <div className="request-list">
            {users.map((user) => (
              <article className="request-item" key={user.id}>
                <h3>{user.name || user.username}</h3>
                <p><strong>Username:</strong> {user.username}</p>
                <p><strong>Email:</strong> {user.email}</p>
                <p><strong>Role:</strong> {user.role}</p>
                <p><strong>Account:</strong> {user.is_active ? "Active" : "Inactive"}</p>
                {user.organisation && <p><strong>Organisation:</strong> {user.organisation}</p>}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
