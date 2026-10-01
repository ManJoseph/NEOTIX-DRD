import { useState } from "react";
import { apiRequest } from "./api";

export default function EpisodeImport({ token, onImported }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const [reportPage, setReportPage] = useState(1);
  const rowsPerPage = 20;

  function chooseFile(event) {
    setFile(event.target.files[0] || null);
    setError("");
    setReport(null);
    setReportPage(1);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setReport(null);
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("CSV files must be at most 5 MiB.");
      return;
    }
    setUploading(true);
    try {
      const data = new FormData();
      data.append("file", file);
      const result = await apiRequest("/api/episodes/import/", "POST", data, token);
      setReport(result);
      setReportPage(1);
      onImported();
    } catch (error) {
      setError(error.message);
    } finally {
      setUploading(false);
    }
  }

  const skippedRows = report ? report.skipped_rows.slice((reportPage - 1) * rowsPerPage, reportPage * rowsPerPage) : [];

  return (
    <section className="card" aria-labelledby="import-title">
      <h2 id="import-title">Import episode metadata</h2>
      <p>Upload a UTF-8 CSV, up to 5 MiB and 10,000 data records. Repeated imports preserve existing episodes.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="episode-file">CSV file</label>
        <input id="episode-file" type="file" accept=".csv,text/csv" required disabled={uploading} onChange={chooseFile} />
        <button type="submit" disabled={uploading || !file}>{uploading ? "Importing…" : "Import CSV"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {report && (
        <div>
          <p role="status"><strong>Imported:</strong> {report.imported} · <strong>Skipped:</strong> {report.skipped}</p>
          {report.skipped > 0 && (
            <>
              <p>The file was processed. Review the skipped records below.</p>
              <div className="table-scroll">
                <table>
                  <caption>Skipped records — Page {reportPage}</caption>
                  <thead><tr><th scope="col">Record</th><th scope="col">Episode ID</th><th scope="col">Reason</th></tr></thead>
                  <tbody>
                    {skippedRows.map((row) => (
                      <tr key={row.row}><td>{row.row}</td><td>{row.episode_id || "—"}</td><td>{row.reason}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="actions pagination">
                <button type="button" className="secondary" disabled={reportPage === 1}
                  onClick={() => setReportPage(reportPage - 1)}>Previous skipped records</button>
                <button type="button" className="secondary" disabled={reportPage * rowsPerPage >= report.skipped_rows.length}
                  onClick={() => setReportPage(reportPage + 1)}>Next skipped records</button>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
