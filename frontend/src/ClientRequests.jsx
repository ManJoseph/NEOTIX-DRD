import { useEffect, useState } from "react";
import RequestForm from "./RequestForm";
import { apiRequest } from "./api";

export default function ClientRequests({ token }) {
  const [requests, setRequests] = useState([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [reviewing, setReviewing] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    // Ignore a response if the user leaves this screen or changes pages.
    let active = true;
    async function loadRequests() {
      setLoading(true);
      setLoadFailed(false);
      setError("");
      try {
        const result = await apiRequest(`/api/requests/?page=${page}`, "GET", null, token);
        if (active) {
          setRequests(result.results);
          setCount(result.count);
          setHasNext(result.next !== null);
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
    loadRequests();
    return () => { active = false; };
  }, [token, page, reload]);

  function handleCreated() {
    setMessage("Request created.");
    setPage(1);
    setReload((current) => current + 1);
  }

  async function reviewRequest(requestId, status) {
    setError("");
    setMessage("");
    setReviewing(requestId);
    try {
      const updated = await apiRequest(`/api/requests/${requestId}/status/`, "POST", { status }, token);
      setRequests((current) => current.map((request) => request.id === updated.id ? updated : request));
      setMessage(`Request #${requestId} ${status}.`);
    } catch (error) {
      setError(error.message);
    } finally {
      setReviewing(null);
    }
  }

  return (
    <div className="workspace">
      <RequestForm token={token} onCreated={handleCreated} />
      <section className="card" aria-labelledby="requests-title">
        <div className="section-heading">
          <h2 id="requests-title">My requests</h2>
          <button type="button" disabled={loading || reviewing !== null}
            onClick={() => setReload((current) => current + 1)}>Refresh</button>
        </div>
        {message && <p role="status">{message}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {loading ? <p role="status">Loading requests…</p> : !loadFailed && (
          <>
            <p>{count} request{count === 1 ? "" : "s"} · Page {page}</p>
            {requests.length === 0 && <p>You have no requests yet. Create your first one using the form.</p>}
            <div className="request-list">
              {requests.map((request) => (
                <article className="request-item" key={request.id}>
                  <h3>#{request.id} — {request.task_name}</h3>
                  <p><strong>Status:</strong> {request.status.replaceAll("_", " ")}</p>
                  <p><strong>Episodes requested:</strong> {request.episodes_requested}</p>
                  <p><strong>Deadline:</strong> {request.deadline}</p>
                  {request.notes && <p className="request-notes"><strong>Notes:</strong> {request.notes}</p>}
                  {request.status === "delivered" && (
                    <div className="actions">
                      <button type="button" disabled={reviewing !== null}
                        onClick={() => reviewRequest(request.id, "accepted")}>Accept delivery</button>
                      <button type="button" className="secondary" disabled={reviewing !== null}
                        onClick={() => reviewRequest(request.id, "rejected")}>Reject delivery</button>
                      {reviewing === request.id && <span role="status">Saving review…</span>}
                    </div>
                  )}
                </article>
              ))}
            </div>
            <div className="actions pagination">
              <button type="button" className="secondary" disabled={page === 1 || reviewing !== null}
                onClick={() => setPage(page - 1)}>Previous</button>
              <button type="button" className="secondary" disabled={!hasNext || reviewing !== null}
                onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
