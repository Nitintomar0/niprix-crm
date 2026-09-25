import {
  ApiError,
  type AttendanceRecord,
  type CurrentAttendance,
  type Paginated,
  type Tokens,
  type User,
} from "@/lib/types";

const TOKEN_KEY = "niprix.auth.tokens";
let refreshInFlight: Promise<boolean> | null = null;

function getTokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(TOKEN_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    window.sessionStorage.removeItem(TOKEN_KEY);
    return null;
  }
}

export function hasStoredSession() {
  return Boolean(getTokens());
}

export function saveTokens(tokens: Tokens) {
  window.sessionStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

export function clearTokens() {
  window.sessionStorage.removeItem(TOKEN_KEY);
}

async function errorFrom(response: Response): Promise<ApiError> {
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    // Proxies and development error pages are not necessarily JSON.
  }

  const detail =
    typeof data === "object" && data && "detail" in data
      ? String(data.detail)
      : typeof data === "object" && data
        ? Object.values(data as Record<string, unknown>).flat().join(" ")
        : "The request could not be completed.";

  return new ApiError(detail || "The request could not be completed.", response.status, data);
}

async function fetchApi(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init);
  } catch {
    throw new ApiError(
      "We could not reach the local API. Check that the backend server is running.",
      0,
    );
  }
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const tokens = getTokens();
    if (!tokens?.refresh) return false;

    const response = await fetchApi("/api/auth/token/refresh/", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const refreshed = (await response.json()) as Partial<Tokens>;
    if (!refreshed.access) {
      clearTokens();
      return false;
    }

    saveTokens({ access: refreshed.access, refresh: refreshed.refresh ?? tokens.refresh });
    return true;
  })();

  try {
    return await refreshInFlight;
  } catch {
    clearTokens();
    return false;
  } finally {
    refreshInFlight = null;
  }
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const tokens = getTokens();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (tokens?.access) headers.set("Authorization", `Bearer ${tokens.access}`);

  const response = await fetchApi(path, { ...init, headers });
  if (response.status === 401 && retry && (await refreshAccessToken())) {
    return request<T>(path, init, false);
  }

  if (!response.ok) {
    const error = await errorFrom(response);
    if (error.status === 401) {
      clearTokens();
      window.dispatchEvent(new Event("niprix:unauthorized"));
    }
    throw error;
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string) {
    const response = await fetchApi("/api/auth/token/", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw await errorFrom(response);
    return response.json() as Promise<Tokens>;
  },
  me: () => request<User>("/api/auth/me/"),
  currentAttendance: () => request<CurrentAttendance>("/api/attendance/current/"),
  checkIn: () => request<AttendanceRecord>("/api/attendance/check-in/", { method: "POST" }),
  checkOut: () => request<AttendanceRecord>("/api/attendance/check-out/", { method: "POST" }),
  attendanceHistory: (page = 1) =>
    request<Paginated<AttendanceRecord> | AttendanceRecord[]>(
      `/api/attendance/?page=${page}&page_size=6`,
    ),
  correctAttendance: (
    id: number,
    body: { check_in_at?: string; check_out_at?: string | null; reason: string },
  ) =>
    request<AttendanceRecord>(`/api/attendance/${id}/correct/`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  async logout() {
    const tokens = getTokens();
    try {
      if (tokens?.refresh) {
        await request("/api/auth/logout/", {
          method: "POST",
          body: JSON.stringify({ refresh: tokens.refresh }),
        });
      }
    } finally {
      clearTokens();
    }
  },
};
