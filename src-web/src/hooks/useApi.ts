import { useCallback } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const DEV_TOKEN = import.meta.env.VITE_DEV_API_TOKEN ?? "dev-token-local-development-32x";

function isTauriEnv(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function getToken(): Promise<string> {
  if (isTauriEnv()) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<string>("get_api_token");
  }
  return DEV_TOKEN;
}

interface UseApiReturn {
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
}

export function useApi(): UseApiReturn {
  const request = useCallback(async <T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> => {
    const token = await getToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-API-Token": token,
        ...(options.headers as Record<string, string> ?? {}),
      },
    });
    if (!response.ok) {
      let message = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const body = await response.json();
        if (body?.detail) {
          message = String(body.detail);
        }
      } catch {
        // response body is not JSON — keep the status-based message
      }
      throw new Error(message);
    }
    return (await response.json()) as T;
  }, []);

  return { request };
}
