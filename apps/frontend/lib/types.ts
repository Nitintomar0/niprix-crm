export type Role = "CEO" | "MANAGER" | "EMPLOYEE";
export interface User { id: number; username: string; email: string; role: Role; }
export interface Tokens { access: string; refresh: string; }
export interface AttendanceRecord { id: number; employee: number; employee_code: string; employee_name: string; branch: number; attendance_date: string; check_in_at: string | null; check_out_at: string | null; status: "PRESENT" | "LATE"; late_minutes: number; total_work_minutes: number; early_checkout: boolean; corrected_at: string | null; }
export interface NotCheckedIn { status: "NOT_CHECKED_IN"; }
export type CurrentAttendance = AttendanceRecord | NotCheckedIn;
export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[]; }
export class ApiError extends Error { constructor(message: string, public status: number, public data?: unknown) { super(message); this.name = "ApiError"; } }
