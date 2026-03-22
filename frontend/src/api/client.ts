// ─── API Client ───────────────────────────────────────────────────
// Thin fetch wrapper.
// Dev: Vite proxy forwards /api → backend (VITE_API_URL unset).
// Production: VITE_API_URL is the backend origin (e.g. https://cadence-api-xxxx.onrender.com).

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail?: string,
  ) {
    super(detail ?? `${status} ${statusText}`);
    this.name = "ApiError";
  }
}

/**
 * Make a GET request to the API.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    let detail: string | undefined;
    try {
      detail = JSON.parse(body)?.detail;
    } catch {
      detail = body || undefined;
    }
    throw new ApiError(response.status, response.statusText, detail);
  }
  return response.json();
}

// ─── Retry Helpers ────────────────────────────────────────────────

function shouldRetry(err: unknown): boolean {
  if (err instanceof ApiError) {
    return err.status >= 500 || err.status === 0;
  }
  return true; // Network errors.
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * GET with exponential backoff retry for transient errors (5xx / network).
 */
export async function apiGetWithRetry<T>(
  path: string,
  maxRetries = 2,
): Promise<T> {
  let lastError: Error = new Error("Request failed");
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await apiGet<T>(path);
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (i < maxRetries && shouldRetry(err)) {
        await sleep(Math.pow(2, i) * 200);
      }
    }
  }
  throw lastError;
}

/**
 * Make a POST request to the API with a JSON body.
 */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail: string | undefined;
    try {
      detail = JSON.parse(text)?.detail;
    } catch {
      detail = text || undefined;
    }
    throw new ApiError(response.status, response.statusText, detail);
  }
  return response.json();
}

/**
 * Make a POST request with FormData (for file uploads).
 */
export async function apiPostFormData<T>(path: string, formData: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  // Do NOT set Content-Type — browser sets it with boundary for multipart
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail: string | undefined;
    try {
      detail = JSON.parse(text)?.detail;
    } catch {
      detail = text || undefined;
    }
    throw new ApiError(response.status, response.statusText, detail);
  }
  return response.json();
}
