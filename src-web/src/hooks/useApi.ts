import { useState, useCallback } from "react";

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
  loading: boolean;
  error: string | null;
}

export function useApi(): UseApiReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(async <T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> => {
    setLoading(true);
    setError(null);
    try {
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
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return (await response.json()) as T;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { request, loading, error };
}
