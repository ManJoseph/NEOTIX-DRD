import { useState } from "react";
import { apiRequest } from "./api";

export default function LoginForm({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await apiRequest("/api/auth/login/", "POST", { username, password });
      setPassword("");
      onLogin(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card login-card" aria-labelledby="login-title">
      <h2 id="login-title">Sign in</h2>
      <p>Use the account created by your administrator.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Username</label>
        <input id="username" autoComplete="username" maxLength={150} required
          value={username} onChange={(event) => setUsername(event.target.value)} />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" maxLength={128} required
          value={password} onChange={(event) => setPassword(event.target.value)} />
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
      </form>
    </section>
  );
}
