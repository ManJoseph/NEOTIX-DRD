import { useEffect, useState } from "react";
import { apiRequest } from "./api";

export default function EpisodeAssignments({ token, request, busy, onBusy, onCount, inventoryVersion }) {
  const [assignments, setAssignments] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [assignmentPage, setAssignmentPage] = useState(1);
  const [episodePage, setEpisodePage] = useState(1);
  const [hasMoreAssignments, setHasMoreAssignments] = useState(false);
  const [hasMoreEpisodes, setHasMoreEpisodes] = useState(false);
  const [taskInput, setTaskInput] = useState(request.task_name);
  const [qualityInput, setQualityInput] = useState("good");
  const [filters, setFilters] = useState({ task: request.task_name, quality: "good" });
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const editable = request.status === "in_progress";

  useEffect(() => {
    let active = true;
    async function loadEpisodes() {
      setLoading(true);
      setLoadFailed(false);
      setError("");
      onCount(null);
      try {
        const assignmentResult = await apiRequest(`/api/requests/${request.id}/assignments/?page=${assignmentPage}`, "GET", null, token);
        let inventoryResult = { results: [], next: null };
        if (editable) {
          const query = new URLSearchParams({ task_name: filters.task, available: "true", page: episodePage });
          if (filters.quality) query.set("quality", filters.quality);
          inventoryResult = await apiRequest(`/api/episodes/?${query}`, "GET", null, token);
        }
        if (active) {
          setAssignments(assignmentResult.results);
          setHasMoreAssignments(assignmentResult.next !== null);
          onCount(assignmentResult.count);
          setEpisodes(inventoryResult.results);
          setHasMoreEpisodes(inventoryResult.next !== null);
        }
      } catch (error) {
        if (active) {
          setError(error.message);
          setLoadFailed(true);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    loadEpisodes();
    return () => { active = false; };
  }, [token, request.id, editable, assignmentPage, episodePage, filters, reload, onCount, inventoryVersion]);

  function applyFilters(event) {
    event.preventDefault();
    setEpisodePage(1);
    setFilters({ task: taskInput, quality: qualityInput });
  }

  async function assignEpisode(episodeId) {
    setError("");
    setMessage("");
    onBusy(true);
    try {
      await apiRequest(`/api/requests/${request.id}/assignments/`, "POST", { episode: episodeId }, token);
      setMessage("Episode assigned.");
      setEpisodePage(1);
      setReload((current) => current + 1);
    } catch (error) {
      setError(error.message);
    } finally {
      onBusy(false);
    }
  }

  async function removeAssignment(assignmentId) {
    setError("");
    setMessage("");
    onBusy(true);
    try {
      await apiRequest(`/api/requests/${request.id}/assignments/${assignmentId}/`, "DELETE", null, token);
      setMessage("Assignment removed. The episode is available again.");
      setAssignmentPage(1);
      setEpisodePage(1);
      setReload((current) => current + 1);
    } catch (error) {
      setError(error.message);
    } finally {
      onBusy(false);
    }
  }

  return (
    <div className="assignment-workspace">
      <div className="section-heading">
        <h3>Episode assignments</h3>
        <button type="button" className="secondary" disabled={busy || loading}
          onClick={() => {
            setAssignmentPage(1);
            setEpisodePage(1);
            setReload((current) => current + 1);
          }}>Refresh episodes</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {editable && (
        <form className="filter-form" onSubmit={applyFilters}>
          <label htmlFor="episode-task">Task filter</label>
          <input id="episode-task" required maxLength={200} value={taskInput}
            onChange={(event) => setTaskInput(event.target.value)} />
          <label htmlFor="episode-quality">Quality</label>
          <select id="episode-quality" value={qualityInput} onChange={(event) => setQualityInput(event.target.value)}>
            <option value="good">Good</option>
            <option value="usable">Usable</option>
            <option value="">All qualities</option>
          </select>
          <button type="submit" disabled={busy || loading}>Apply filters</button>
        </form>
      )}
      {loading ? <p role="status">Loading episodes…</p> : !loadFailed && (
        <>
          <h4>Assigned episodes · Page {assignmentPage}</h4>
          {assignments.length === 0 && <p>No episodes assigned yet.</p>}
          <div className="request-list">
            {assignments.map((assignment) => (
              <article className="request-item" key={assignment.id}>
                <strong>{assignment.episode_id}</strong>
                <p>{assignment.episode_details.task_name} · {assignment.episode_details.robot_id} · {assignment.episode_details.quality}</p>
                <p>{assignment.episode_details.duration_seconds} seconds</p>
                {editable && <button type="button" className="secondary" disabled={busy}
                  onClick={() => removeAssignment(assignment.id)}>Remove assignment</button>}
              </article>
            ))}
          </div>
          <div className="actions pagination">
            <button type="button" className="secondary" disabled={busy || assignmentPage === 1}
              onClick={() => setAssignmentPage(assignmentPage - 1)}>Previous assignments</button>
            <button type="button" className="secondary" disabled={busy || !hasMoreAssignments}
              onClick={() => setAssignmentPage(assignmentPage + 1)}>Next assignments</button>
          </div>
          {editable && (
            <>
              <h4>Available episodes · Page {episodePage}</h4>
              {episodes.length === 0 && <p>No available episodes match these filters. Import recordings or change the quality filter.</p>}
              <div className="request-list">
                {episodes.map((episode) => (
                  <article className="request-item" key={episode.id}>
                    <strong>{episode.episode_id}</strong>
                    <p>{episode.task_name} · {episode.robot_id} · {episode.quality}</p>
                    <p>{episode.duration_seconds} seconds</p>
                    <button type="button" disabled={busy || episode.quality === "bad" || episode.task_name !== request.task_name}
                      onClick={() => assignEpisode(episode.id)}>Assign episode</button>
                  </article>
                ))}
              </div>
              <div className="actions pagination">
                <button type="button" className="secondary" disabled={busy || episodePage === 1}
                  onClick={() => setEpisodePage(episodePage - 1)}>Previous episodes</button>
                <button type="button" className="secondary" disabled={busy || !hasMoreEpisodes}
                  onClick={() => setEpisodePage(episodePage + 1)}>Next episodes</button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
