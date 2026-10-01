import { useState } from "react";
import { apiRequest } from "./api";

export default function UserForm({ token, onCreated }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [role, setRole] = useState("client");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const user = await apiRequest("/api/users/", "POST", {
        username, email, name, organisation, role, password,
      }, token);
      setUsername("");
      setEmail("");
      setName("");
      setOrganisation("");
      setRole("client");
      setPassword("");
      onCreated(user);
    } catch (error) {
      setError(error.message);
      setPassword("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" aria-labelledby="create-user-title">
      <h2 id="create-user-title">Create an account</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor="new-username">Username</label>
        <input id="new-username" required maxLength={150} autoComplete="off"
          value={username} onChange={(event) => setUsername(event.target.value)} />
        <label htmlFor="new-email">Email</label>
        <input id="new-email" type="email" required maxLength={254}
          value={email} onChange={(event) => setEmail(event.target.value)} />
        <label htmlFor="new-name">Name</label>
        <input id="new-name" required maxLength={150}
          value={name} onChange={(event) => setName(event.target.value)} />
        <label htmlFor="new-organisation">Organisation (optional)</label>
        <input id="new-organisation" maxLength={150}
          value={organisation} onChange={(event) => setOrganisation(event.target.value)} />
        <label htmlFor="new-role">Role</label>
        <select id="new-role" value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="client">Client</option>
          <option value="operator">Operator</option>
          <option value="admin">Admin</option>
        </select>
        <label htmlFor="new-password">Password</label>
        <input id="new-password" type="password" required minLength={5} maxLength={128} autoComplete="new-password"
          value={password} onChange={(event) => setPassword(event.target.value)} />
        <p className="hint">Choose a unique password with at least 8 characters. Avoid common passwords or account details.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={saving}>{saving ? "Creating…" : "Create account"}</button>
      </form>
    </section>
  );
}
