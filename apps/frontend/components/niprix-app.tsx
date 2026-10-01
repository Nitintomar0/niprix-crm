"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { AttendanceDashboard } from "@/components/attendance-dashboard";
import { LoginScreen } from "@/components/login-screen";
import { Overview } from "@/components/overview";
import { ReminderPreferences } from "@/components/reminder-preferences";
import { WorkDashboard } from "@/components/workspace-dashboard";
import { LeadsDashboard } from "@/components/leads-dashboard";
import { IntegrationsDashboard } from "@/components/integrations-dashboard";
import { Employee360 } from "@/components/employee-360";
import { EmployeeDirectory } from "@/components/employee-directory";
import { HRDashboardPage } from "@/components/hr-dashboard";
import { DocumentsPage, HolidaysPage, LeaveBalancesPage, LeaveRequestsPage, LeaveTypesPage } from "@/components/hr-management";
import { api, clearTokens, hasStoredSession, saveTokens } from "@/lib/api";
import type { User } from "@/lib/types";

export function NiprixApp({ page, leadId, employeeId }: { page: "overview" | "attendance" | "followups" | "tasks" | "reminders" | "leads" | "integrations" | "employees" | "employee" | "hr" | "leaveRequests" | "leaveTypes" | "leaveBalances" | "holidays" | "documents"; leadId?: number; employeeId?: number }) {
  const [user, setUser] = useState<User | null>(null); const [checking, setChecking] = useState(true); const [error, setError] = useState("");
  const restore = useCallback(async () => { if (!hasStoredSession()) { setChecking(false); return; } try { setUser(await api.me()); } catch (caught) { clearTokens(); setError(caught instanceof Error ? `Your saved session could not be restored. ${caught.message}` : "Your saved session could not be restored. Please sign in again."); } finally { setChecking(false); } }, []);
  useEffect(() => { const timer = window.setTimeout(() => { void restore(); }, 0); const unauthorized = () => { clearTokens(); setUser(null); setError("Your session has ended. Please sign in again."); }; window.addEventListener("niprix:unauthorized", unauthorized); return () => { window.clearTimeout(timer); window.removeEventListener("niprix:unauthorized", unauthorized); }; }, [restore]);
  async function login(username: string, password: string) { setError(""); try { saveTokens(await api.login(username, password)); setUser(await api.me()); } catch (caught) { clearTokens(); setError(caught instanceof Error ? caught.message : "Unable to sign in. Please try again."); throw caught; } }
  async function logout() { try { await api.logout(); setError(""); } catch (caught) { setError(caught instanceof Error ? `You have been signed out locally. ${caught.message}` : "You have been signed out locally, but the server could not be reached."); } finally { setUser(null); } }
  if (checking) return <main className="soft-grid flex min-h-screen items-center justify-center"><div className="app-card rounded-2xl px-8 py-7 text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[#d9eafa] border-t-[#0869d8]" /><p className="mt-4 text-sm font-medium text-[#60708a]">Preparing your secure workspace…</p></div></main>;
  if (!user) return <LoginScreen onSubmit={login} error={error} />;
  return <AppShell user={user} onLogout={() => void logout()}>{page === "hr" ? <HRDashboardPage role={user.role} /> : page === "leaveRequests" ? <LeaveRequestsPage role={user.role} /> : page === "leaveTypes" ? <LeaveTypesPage role={user.role} /> : page === "leaveBalances" ? <LeaveBalancesPage /> : page === "holidays" ? <HolidaysPage role={user.role} /> : page === "documents" ? <DocumentsPage role={user.role} /> : page === "employees" ? <EmployeeDirectory role={user.role} /> : page === "employee" && employeeId ? <Employee360 employeeId={employeeId} role={user.role} /> : page === "attendance" ? <AttendanceDashboard role={user.role} /> : page === "leads" ? <LeadsDashboard role={user.role} leadId={leadId} /> : page === "integrations" ? <IntegrationsDashboard /> : page === "followups" ? <WorkDashboard kind="followups" role={user.role} /> : page === "tasks" ? <WorkDashboard kind="tasks" role={user.role} /> : page === "reminders" ? <ReminderPreferences /> : <Overview user={user} />}</AppShell>;
}
