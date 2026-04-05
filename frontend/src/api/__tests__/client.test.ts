// ─── API client error parsing tests ───────────────────────────────
// Covers parseErrorDetail behavior through the public apiPost/apiGet
// functions. Tests the error message formatting for Pydantic arrays,
// string details, and empty/missing response bodies.

import { apiPost, apiGet, ApiError } from "@/api/client";

describe("API client error handling", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function mockFetchResponse(status: number, body: unknown, statusText = "") {
    const response = {
      ok: false,
      status,
      statusText,
      text: () => Promise.resolve(typeof body === "string" ? body : JSON.stringify(body)),
      json: () => Promise.resolve(body),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(response);
  }

  it("formats Pydantic validation error array into semicolon-separated string", async () => {
    mockFetchResponse(422, {
      detail: [
        { loc: ["body", "method"], msg: "Field required" },
        { loc: ["body", "rationale"], msg: "Field required" },
      ],
    }, "Unprocessable Entity");

    await expect(apiPost("/test", {})).rejects.toThrow(ApiError);
    try {
      await apiPost("/test", {});
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.message).toBe("body.method: Field required; body.rationale: Field required");
    }
  });

  it("passes through string detail as-is", async () => {
    mockFetchResponse(400, { detail: "Some error message" }, "Bad Request");

    await expect(apiPost("/test", {})).rejects.toThrow("Some error message");
  });

  it("falls back to status code + text when no parseable body", async () => {
    const response = {
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: () => Promise.resolve(""),
      json: () => Promise.reject(new Error("no json")),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(response);

    await expect(apiGet("/test")).rejects.toThrow("500 Internal Server Error");
  });

  it("JSON-stringifies non-string, non-array detail objects", async () => {
    mockFetchResponse(400, { detail: { code: "ERR_01", info: "bad" } }, "Bad Request");

    try {
      await apiPost("/test", {});
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.message).toContain("ERR_01");
    }
  });

  it("handles response.text() throwing gracefully", async () => {
    const response = {
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      text: () => Promise.reject(new Error("network error")),
      json: () => Promise.reject(new Error("network error")),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(response);

    await expect(apiGet("/test")).rejects.toThrow("502 Bad Gateway");
  });
});
