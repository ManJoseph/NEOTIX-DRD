// Send one request to Django. A token is supplied for protected endpoints.
export async function apiRequest(path, method = "GET", data = null, token = "") {
  const headers = {};
  if (token) {
    headers.Authorization = `Token ${token}`;
  }
  let body;
  if (data instanceof FormData) {
    // The browser supplies the multipart Content-Type and boundary for uploads.
    body = data;
  } else if (data !== null) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(data);
  }

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body,
    });
  } catch {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }

  if (response.status === 204) {
    return null;
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The server returned an unexpected response. Check that Backend is running.");
  }

  if (!response.ok) {
    if (result.detail) {
      throw new Error(result.detail);
    }
    // DRF validation responses contain field names and error messages.
    const messages = Object.entries(result).map(([field, errors]) => {
      return `${field}: ${Array.isArray(errors) ? errors.join(" ") : errors}`;
    });
    throw new Error(messages.join(" ") || "The request failed.");
  }
  return result;
}
