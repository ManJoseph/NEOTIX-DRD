import { useEffect, useState } from "react";
import { apiRequest } from "./api";
import EpisodeAssignments from "./EpisodeAssignments";

export default function OperatorRequest({ requestId, token, onStatusChanged, inventoryVersion }) {
  const [request, setRequest] = useState(null);
  const [assignedCount, setAssignedCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function loadRequest() {
      setLoading(true);
      setError("");
      try {
        const result = await apiRequest(`/api/requests/${requestId}/`, "GET", null, token);
        if (active) setRequest(result);
      } catch (error) {
        if (active) setError(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadRequest();
    return () => { active = false; };
  }, [requestId, token, reload]);

  async function changeStatus(status) {
    setError("");
    setMessage("");
    setWorking(true);
    try {
      const updated = await apiRequest(`/api/requests/${requestId}/status/`, "POST", { status }, token);
      setRequest(updated);
      setMessage(`Status changed to ${status.replaceAll("_", " ")}.`);
      onStatusChanged();
    } catch (error) {
      setError(error.message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="card" aria-labelledby="selected-title">
      <div className="section-heading">
        <h2 id="selected-title">Request #{requestId}</h2>
        <button type="button" disabled={loading || working}
          onClick={() => setReload((current) => current + 1)}>Refresh request</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {loading ? <p role="status">Loading request…</p> : request && (
        <>
          <p><strong>Task:</strong> {request.task_name}</p>
          <p><strong>Status:</strong> {request.status.replaceAll("_", " ")}</p>
          <p><strong>Deadline:</strong> {request.deadline}</p>
          {request.notes && <p className="request-notes"><strong>Notes:</strong> {request.notes}</p>}
          <p><strong>Assigned:</strong> {assignedCount === null ? "Loading…" : assignedCount} / {request.episodes_requested} required</p>
          <div className="actions">
            {(request.status === "submitted" || request.status === "rejected") && (
              <button type="button" disabled={working} onClick={() => changeStatus("in_progress")}>
                {request.status === "rejected" ? "Start rework" : "Start work"}
              </button>
            )}
            {request.status === "in_progress" && (
              <button type="button" disabled={working || assignedCount === null || assignedCount < request.episodes_requested}
                onClick={() => changeStatus("delivered")}>Deliver request</button>
            )}
            {working && <span role="status">Saving…</span>}
          </div>
          {request.status === "delivered" && <p>Waiting for the client to accept or reject this delivery.</p>}
          {request.status === "accepted" && <p>The client accepted this delivery.</p>}
          <EpisodeAssignments inventoryVersion={inventoryVersion} token={token} request={request} busy={working} onBusy={setWorking} onCount={setAssignedCount} />
        </>
      )}
    </section>
  );
}
