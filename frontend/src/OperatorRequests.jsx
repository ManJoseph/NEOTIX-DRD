import { useEffect, useState } from "react";
import { apiRequest } from "./api";
import OperatorRequest from "./OperatorRequest";
import EpisodeImport from "./EpisodeImport";

export default function OperatorRequests({ token }) {
  const [requests, setRequests] = useState([]);
  const [inventoryVersion, setInventoryVersion] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadRequests() {
      setLoading(true);
      setError("");
      try {
        const result = await apiRequest(`/api/requests/?page=${page}`, "GET", null, token);
        if (active) {
          setRequests(result.results);
          setCount(result.count);
          setHasNext(result.next !== null);
        }
      } catch (error) {
        if (active) setError(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadRequests();
    return () => { active = false; };
  }, [token, page, reload]);

  return (
    <section className="operator-workspace">
      <EpisodeImport token={token} onImported={() => setInventoryVersion((current) => current + 1)} />
      <section className="card" aria-labelledby="operator-title">
        <div className="section-heading">
          <h2 id="operator-title">All requests</h2>
          <button type="button" disabled={loading}
            onClick={() => setReload((current) => current + 1)}>Refresh list</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {loading ? <p role="status">Loading requests…</p> : !error && (
          <>
            <p>{count} requests · Page {page}</p>
            {requests.length === 0 && <p>No client requests yet.</p>}
            <div className="request-list">
              {requests.map((request) => (
                <article className="request-item" key={request.id}>
                  <h3>#{request.id} — {request.task_name}</h3>
                  <p>Client #{request.client} · {request.status.replaceAll("_", " ")}</p>
                  <p>{request.episodes_requested} episodes · Deadline: {request.deadline}</p>
                  <button type="button" onClick={() => setSelectedId(request.id)}
                    aria-pressed={selectedId === request.id}>
                    {selectedId === request.id ? "Selected" : "Open request"}
                  </button>
                </article>
              ))}
            </div>
            <div className="actions pagination">
              <button type="button" className="secondary" disabled={page === 1}
                onClick={() => setPage(page - 1)}>Previous</button>
              <button type="button" className="secondary" disabled={!hasNext}
                onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </>
        )}
      </section>
      {selectedId !== null && (
        <OperatorRequest key={selectedId} requestId={selectedId} token={token} inventoryVersion={inventoryVersion}
          onStatusChanged={() => setReload((current) => current + 1)} />
      )}
    </section>
  );
}
