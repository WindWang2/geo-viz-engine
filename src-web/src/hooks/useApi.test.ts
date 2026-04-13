import { renderHook, act, waitFor } from "@testing-library/react";
import { vi, beforeEach, afterEach } from "vitest";
import { useApi } from "./useApi";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubEnv("VITE_DEV_API_TOKEN", "test-vite-token");
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("useApi", () => {
  it("starts with loading=false and error=null", () => {
    const { result } = renderHook(() => useApi());
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("sets loading=true during request", async () => {
    mockFetch.mockImplementationOnce(
      () => new Promise((resolve) => setTimeout(() => resolve({
        ok: true,
        json: async () => ({ status: "ok" }),
      }), 50))
    );

    const { result } = renderHook(() => useApi());
    act(() => { result.current.request("/api/system/status"); });
    expect(result.current.loading).toBe(true);
  });

  it("sends X-API-Token header", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok" }),
    });

    const { result } = renderHook(() => useApi());
    await act(async () => { await result.current.request("/api/system/status"); });

    const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers["X-API-Token"]).toBeDefined();
  });

  it("returns parsed JSON on success", async () => {
    const payload = { status: "ok", version: "0.1.0" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => payload,
    });

    const { result } = renderHook(() => useApi());
    let data: unknown;
    await act(async () => {
      data = await result.current.request("/api/system/status");
    });
    expect(data).toEqual(payload);
  });

  it("sets error state on HTTP error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
    });

    const { result } = renderHook(() => useApi());
    await act(async () => {
      try { await result.current.request("/api/system/status"); }
      catch { /* expected */ }
    });
    await waitFor(() => expect(result.current.error).toContain("401"));
  });

  it("sets loading=false after request completes", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useApi());
    await act(async () => { await result.current.request("/path"); });
    expect(result.current.loading).toBe(false);
  });
});
