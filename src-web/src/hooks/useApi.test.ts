import { renderHook, act } from "@testing-library/react";
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
  it("exposes a request function", () => {
    const { result } = renderHook(() => useApi());
    expect(typeof result.current.request).toBe("function");
  });

  it("calls fetch when request is invoked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok" }),
    });

    const { result } = renderHook(() => useApi());
    await act(async () => { await result.current.request("/api/system/status"); });
    expect(mockFetch).toHaveBeenCalledOnce();
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

  it("throws on HTTP error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
    });

    const { result } = renderHook(() => useApi());
    await act(async () => {
      await expect(result.current.request("/api/system/status")).rejects.toThrow("401");
    });
  });

  it("resolves after request completes", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useApi());
    await act(async () => {
      await expect(result.current.request("/path")).resolves.toBeDefined();
    });
  });
});
