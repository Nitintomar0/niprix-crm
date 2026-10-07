import {
  ApiError,
  type AttendanceRecord,
  type CurrentAttendance,
  type EmployeeOption,
  type FollowUp,
  type FollowUpActivity,
  type Paginated,
  type ReminderPreference,
  type Task,
  type Tokens,
  type User,
  type WorkspaceSummary,
  type Lead,
  type LeadActivity,
  type LeadAssignment,
  type LeadSource,
  type LeadSummary,
  type IntegrationConfiguration,
  type IntegrationEvent,
  type EmployeeProfile,
  type EmployeeOverview,
  type EmployeePerformance,
  type LeaveRequest,
  type LeaveType,
  type EmployeeWork,
  type LiveLocation,
  type InventoryItem,
  type InventorySummary,
  type RawLead,
  type RawDataSummary,
  type RawPreview,
  type RawEligibleEmployee,
  type RawDistributionPreview,
} from "@/lib/types";

const TOKEN_KEY = "niprix.auth.tokens";
let refreshInFlight: Promise<boolean> | null = null;
let employeesCache: { value: Paginated<EmployeeOption> | EmployeeOption[]; expiresAt: number } | null = null;
let employeesInFlight: Promise<Paginated<EmployeeOption> | EmployeeOption[]> | null = null;

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
  employeesCache = null;
}

async function errorFrom(response: Response): Promise<ApiError> {
  let data: unknown;

  try {
    data = await response.json();
  } catch {
    return new ApiError(
      "The request could not be completed.",
      response.status,
      data,
    );
  }

  function extractMessage(value: unknown): string {
    if (typeof value === "string") {
      return value;
    }

    if (Array.isArray(value)) {
      return value
        .map(extractMessage)
        .filter(Boolean)
        .join(" ");
    }

    if (value && typeof value === "object") {
      return Object.values(value)
        .map(extractMessage)
        .filter(Boolean)
        .join(" ");
    }

    return "";
  }

  const detail =
    data && typeof data === "object" && "detail" in data
      ? extractMessage((data as Record<string, unknown>).detail)
      : extractMessage(data);

  return new ApiError(
    detail || "The request could not be completed.",
    response.status,
    data,
  );
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
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
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
  submitLiveLocation: (position: { latitude: number; longitude: number; accuracy: number }) => request<LiveLocation>("/api/attendance/live-location/", { method: "POST", body: JSON.stringify(position) }),
  reportLiveLocationStatus: (status: "permission_denied" | "position_unavailable" | "timeout" | "missing_coordinates") => request<LiveLocation>("/api/attendance/live-location/", { method: "POST", body: JSON.stringify({ status }) }),
  employeeLiveLocation: (id: number) => request<LiveLocation>(`/api/employees/${id}/live-location/`),
  attendanceHistory: (page = 1, date?: string) =>
  request<Paginated<AttendanceRecord> | AttendanceRecord[]>(
    `/api/attendance/?page=${page}&page_size=6${
      date ? `&date_from=${date}&date_to=${date}` : ""
    }`,
  ),
  attendanceSummary: (date?: string) => request<import("@/lib/types").AttendanceWorkspace>(`/api/attendance/summary/${date ? `?date=${date}` : ""}`),
  correctAttendance: (
    id: number,
    body: { check_in_at?: string; check_out_at?: string | null; reason: string },
  ) =>
    request<AttendanceRecord>(`/api/attendance/${id}/correct/`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  employees: async () => {
    // Employee options change infrequently, while lead/work filters change on
    // every selection. A short in-memory reuse removes redundant requests
    // without persisting stale CRM data across sessions.
    if (employeesCache && employeesCache.expiresAt > Date.now()) return employeesCache.value;
    if (!employeesInFlight) {
      employeesInFlight = request<Paginated<EmployeeOption> | EmployeeOption[]>("/api/employees/?page=1&page_size=100")
        .then((value) => {
          employeesCache = { value, expiresAt: Date.now() + 15_000 };
          return value;
        })
        .finally(() => { employeesInFlight = null; });
    }
    return employeesInFlight;
  },
  employeeDirectory: (query = "") => request<Paginated<EmployeeProfile> | EmployeeProfile[]>(`/api/employees/?page=1&page_size=100${query ? `&${query}` : ""}`),
  createEmployee: (body: Record<string, unknown>) => request<EmployeeProfile>("/api/employees/create/", { method: "POST", body: JSON.stringify(body) }),
  employee: (id: number) => request<EmployeeProfile>(`/api/employees/${id}/`),
  employeeOverview: (id: number) => request<EmployeeOverview>(`/api/employees/${id}/overview/`),
  employeePerformance: (id: number) => request<EmployeePerformance>(`/api/employees/${id}/performance/`),
  employeeAttendance: (id: number) => request<AttendanceRecord[]>(`/api/employees/${id}/attendance/`),
  employeeLeads: (id: number) => request<Lead[]>(`/api/employees/${id}/leads/`),
  employeeWork: (id: number) => request<EmployeeWork>(`/api/employees/${id}/work/`),
  employeeActivity: (id: number) => request<Array<{ id: number; action: string; actor: string; created_at: string; reason: string }>>(`/api/employees/${id}/activity/`),
  deactivateEmployee: (id: number) => request<{ already_deactivated: boolean; leads_reassigned: number; follow_ups_reassigned: number }>(`/api/employees/${id}/deactivate/`, { method: "POST" }),
  deleteEmployee: (id: number) => request<void>(`/api/employees/${id}/delete/`, { method: "DELETE" }),
  updateEmployeeSelf: (id: number, body: FormData) => request<EmployeeProfile>(`/api/employees/${id}/`, { method: "PATCH", body }),
  leaveTypes: () => request<LeaveType[]>("/api/hrms/leave-types/"),
  createLeaveType: (body: Partial<LeaveType>) => request<LeaveType>("/api/hrms/leave-types/", { method: "POST", body: JSON.stringify(body) }),
  updateLeaveType: (id: number, body: Partial<LeaveType>) => request<LeaveType>(`/api/hrms/leave-types/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteLeaveType: (id: number) => request<void>(`/api/hrms/leave-types/${id}/`, { method: "DELETE" }),
  leaveBalances: () => request<import("@/lib/types").LeaveBalance[]>("/api/hrms/leave-balances/"),
  updateLeaveBalance: (id: number, allocated_days: string) => request<import("@/lib/types").LeaveBalance>(`/api/hrms/leave-balances/${id}/`, { method: "PATCH", body: JSON.stringify({ allocated_days }) }),
  leaveRequests: () => request<LeaveRequest[]>("/api/hrms/leave-requests/"),
  createLeaveRequest: (body: { leave_type: number; start_date: string; end_date: string; reason: string }) => request<LeaveRequest>("/api/hrms/leave-requests/", { method: "POST", body: JSON.stringify(body) }),
  leaveAction: (id: number, action: "cancel" | "approve" | "reject", comment = "") => request<LeaveRequest>(`/api/hrms/leave-requests/${id}/${action}/`, { method: "POST", body: JSON.stringify({ comment }) }),
  holidays: () => request<import("@/lib/types").Holiday[]>("/api/hrms/holidays/"),
  createHoliday: (body: { name: string; holiday_date: string; description?: string }) => request<import("@/lib/types").Holiday>("/api/hrms/holidays/", { method: "POST", body: JSON.stringify(body) }),
  deleteHoliday: (id: number) => request<void>(`/api/hrms/holidays/${id}/`, { method: "DELETE" }),
  hrDashboard: () => request<import("@/lib/types").HRDashboard>("/api/hrms/dashboard/"),
  employeeDocuments: () => request<import("@/lib/types").EmployeeDocument[]>("/api/hrms/documents/"),
  uploadEmployeeDocument: (employeeId: number, body: FormData) => request<import("@/lib/types").EmployeeDocument>(`/api/hrms/employees/${employeeId}/documents/`, { method: "POST", body }),
  async downloadEmployeeDocument(id: number) {
    const tokens = getTokens();
    const response = await fetchApi(`/api/hrms/documents/${id}/download/`, { headers: tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {} });
    if (!response.ok) throw await errorFrom(response);
    return response.blob();
  },
  deleteEmployeeDocument: (id: number) => request<void>(`/api/hrms/documents/${id}/`, { method: "DELETE" }),
  workspaceSummary: () => request<WorkspaceSummary>("/api/workspace/summary/"),
  followUps: (query = "") => request<Paginated<FollowUp>>(`/api/follow-ups/?${query}`),
  createFollowUp: (body: { title: string; description?: string; assigned_to: number; lead?: number; scheduled_at: string; follow_up_type?: string; priority?: string; status?: string }) => request<FollowUp>("/api/follow-ups/", { method: "POST", body: JSON.stringify(body) }),
  updateFollowUp: (id: number, body: { title?: string; description?: string; assigned_to?: number; scheduled_at?: string; follow_up_type?: string; priority?: string; status?: string; activity_note?: string }) => request<FollowUp>(`/api/follow-ups/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  completeFollowUp: (id: number, note = "") => request<FollowUp>(`/api/follow-ups/${id}/complete/`, { method: "POST", body: JSON.stringify({ note }) }),
  postponeFollowUp: (id: number, scheduled_at: string, note = "") => request<FollowUp>(`/api/follow-ups/${id}/postpone/`, { method: "POST", body: JSON.stringify({ scheduled_at, note }) }),
  reassignFollowUp: (id: number, assigned_to: number, note = "") => request<FollowUp>(`/api/follow-ups/${id}/reassign/`, { method: "POST", body: JSON.stringify({ assigned_to, note }) }),
  followUpActivities: (id: number) => request<Paginated<FollowUpActivity>>(`/api/follow-ups/${id}/activities/`),
  deleteFollowUp: (id: number) => request<void>(`/api/follow-ups/${id}/`, { method: "DELETE" }),
  tasks: (query = "") => request<Paginated<Task>>(`/api/tasks/?${query}`),
  createTask: (body: { title: string; description?: string; assigned_to: number; lead?: number; due_date: string; due_time?: string | null; priority?: string; status?: string }) => request<Task>("/api/tasks/", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: number, body: { title?: string; description?: string; assigned_to?: number; due_date?: string; due_time?: string | null; priority?: string; status?: string }) => request<Task>(`/api/tasks/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  completeTask: (id: number) => request<Task>(`/api/tasks/${id}/complete/`, { method: "POST", body: "{}" }),
  reassignTask: (id: number, assigned_to: number) => request<Task>(`/api/tasks/${id}/reassign/`, { method: "POST", body: JSON.stringify({ assigned_to }) }),
  reminderPreferences: () => request<ReminderPreference>("/api/reminder-preferences/"),
  updateReminderPreferences: (body: Partial<ReminderPreference>) => request<ReminderPreference>("/api/reminder-preferences/", { method: "PATCH", body: JSON.stringify(body) }),
  leads: (query = "") => request<Paginated<Lead>>(`/api/leads/?${query}`),
  lead: (id: number) => request<Lead>(`/api/leads/${id}/`),
  leadSummary: () => request<LeadSummary>("/api/leads/summary/"),
  createLead: (body: Record<string, unknown>) => request<Lead>("/api/leads/", { method: "POST", body: JSON.stringify(body) }),
  updateLead: (id: number, body: Record<string, unknown>) => request<Lead>(`/api/leads/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  assignLead: (id: number, assigned_to: number, note = "") => request<Lead>(`/api/leads/${id}/assign/`, { method: "POST", body: JSON.stringify({ assigned_to, note }) }),
  leadActivities: (id: number) => request<Paginated<LeadActivity>>(`/api/leads/${id}/activities/`),
  addLeadNote: (id: number, note: string) => request<LeadActivity>(`/api/leads/${id}/activities/`, { method: "POST", body: JSON.stringify({ note }) }),
  leadSources: (id: number) => request<Paginated<LeadSource>>(`/api/leads/${id}/sources/`),
  leadAssignments: (id: number) => request<Paginated<LeadAssignment>>(`/api/leads/${id}/assignments/`),
  deleteLead: (id: number) => request<void>(`/api/leads/${id}/`, { method: "DELETE" }),
  rawLeads: (query = "") => request<Paginated<RawLead>>(`/api/raw-data/?${query}`),
  rawDataSummary: () => request<RawDataSummary>("/api/raw-data/summary/"),
  createRawLead: (body: Record<string, unknown>) => request<RawLead>("/api/raw-data/", { method: "POST", body: JSON.stringify(body) }),
  updateRawLead: (id: number, body: Record<string, unknown>) => request<RawLead>(`/api/raw-data/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRawLead: (id: number) => request<void>(`/api/raw-data/${id}/`, { method: "DELETE" }),
  previewRawData: (body: FormData | { rows: object[] }) => request<RawPreview>("/api/raw-data/preview/", { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
  saveRawPreview: (rows: object[]) => request<{ created: number }>("/api/raw-data/save-preview/", { method: "POST", body: JSON.stringify({ rows }) }),
  rawEligibleEmployees: () => request<RawEligibleEmployee[]>("/api/raw-data/eligible-employees/"),
  previewRawDistribution: (body: Record<string, unknown>) => request<RawDistributionPreview>("/api/raw-data/distribution-preview/", { method: "POST", body: JSON.stringify(body) }),
  distributeRawData: (body: Record<string, unknown>) => request<{ distributed: number }>("/api/raw-data/distribute/", { method: "POST", body: JSON.stringify(body) }),
  inventory: (query = "") => request<Paginated<InventoryItem>>(`/api/inventory/?${query}`),
  inventorySummary: () => request<InventorySummary>("/api/inventory/summary/"),
  createInventory: (body: Record<string, unknown>) => request<InventoryItem>("/api/inventory/", { method: "POST", body: JSON.stringify(body) }),
  bulkCreateInventory: (items: Record<string, unknown>[]) => request<InventoryItem[]>("/api/inventory/bulk/", { method: "POST", body: JSON.stringify({ items }) }),
  updateInventory: (id: number, body: Record<string, unknown>) => request<InventoryItem>(`/api/inventory/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteInventory: (id: number) => request<void>(`/api/inventory/${id}/`, { method: "DELETE" }),
  integrations: () => request<Paginated<IntegrationConfiguration>>("/api/integrations/?page=1&page_size=100"),
  createIntegration: (body: Pick<IntegrationConfiguration, "provider" | "branch" | "external_account_id" | "is_enabled">) => request<IntegrationConfiguration>("/api/integrations/", { method: "POST", body: JSON.stringify(body) }),
  updateIntegration: (id: number, body: Partial<Pick<IntegrationConfiguration, "branch" | "external_account_id" | "is_enabled">>) => request<IntegrationConfiguration>(`/api/integrations/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  integrationEvents: () => request<Paginated<IntegrationEvent>>("/api/integrations/events/?page=1&page_size=100"),
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

/** Browser WebSockets cannot carry an Authorization header, so the short-lived
 * access token is supplied only to the TLS WebSocket endpoint for authentication. */
export function liveLocationSocketUrl(employeeId: number) {
  const tokens = getTokens();
  if (!tokens?.access || typeof window === "undefined") return null;
  const configured = process.env.NEXT_PUBLIC_BACKEND_WS_URL?.replace(/\/$/, "");
  const origin = configured || `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000`;
  return `${origin}/ws/attendance/live-location/${employeeId}/?token=${encodeURIComponent(tokens.access)}`;
}
