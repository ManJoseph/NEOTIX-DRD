import { useState } from "react";
import { apiRequest } from "./api";

function getTodayInKigali() {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Africa/Kigali", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year").value;
  const month = parts.find((part) => part.type === "month").value;
  const day = parts.find((part) => part.type === "day").value;
  return `${year}-${month}-${day}`;
}

export default function RequestForm({ token, onCreated }) {
  const [taskName, setTaskName] = useState("");
  const [episodeCount, setEpisodeCount] = useState("1");
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      await apiRequest("/api/requests/", "POST", {
        task_name: taskName,
        episodes_requested: Number(episodeCount),
        deadline,
        notes,
      }, token);
      setTaskName("");
      setEpisodeCount("1");
      setDeadline("");
      setNotes("");
      onCreated();
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" aria-labelledby="create-title">
      <h2 id="create-title">Create a request</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor="task-name">Task name</label>
        <input id="task-name" required maxLength={200} placeholder="e.g. pick cup"
          value={taskName} onChange={(event) => setTaskName(event.target.value)} />
        <label htmlFor="episode-count">Number of episodes</label>
        <input id="episode-count" type="number" min="1" max="2147483647" step="1" required
          value={episodeCount} onChange={(event) => setEpisodeCount(event.target.value)} />
        <label htmlFor="deadline">Deadline</label>
        <input id="deadline" type="date" min={getTodayInKigali()} required
          value={deadline} onChange={(event) => setDeadline(event.target.value)} />
        <label htmlFor="notes">Notes (optional)</label>
        <textarea id="notes" rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={saving}>{saving ? "Creating…" : "Create request"}</button>
      </form>
    </section>
  );
}
