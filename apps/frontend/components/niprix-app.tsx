"use client";

import dynamic from "next/dynamic";
import { Overview } from "@/components/overview";
import { useNiprixAuth } from "@/components/niprix-auth-provider";

function PageSectionLoader() {
  return <div aria-label="Loading section" className="space-y-4"><div className="shimmer h-12 rounded-2xl" /><div className="shimmer h-64 rounded-2xl" /></div>;
}

const AttendanceDashboard = dynamic(() => import("@/components/attendance-dashboard").then((module) => module.AttendanceDashboard), { loading: PageSectionLoader });
const ReminderPreferences = dynamic(() => import("@/components/reminder-preferences").then((module) => module.ReminderPreferences), { loading: PageSectionLoader });
const WorkDashboard = dynamic(() => import("@/components/workspace-dashboard").then((module) => module.WorkDashboard), { loading: PageSectionLoader });
const LeadsDashboard = dynamic(() => import("@/components/leads-dashboard").then((module) => module.LeadsDashboard), { loading: PageSectionLoader });
const LeadRecoveryDashboard = dynamic(() => import("@/components/lead-recovery-dashboard").then((module) => module.LeadRecoveryDashboard), { loading: PageSectionLoader });
const IntegrationsDashboard = dynamic(() => import("@/components/integrations-dashboard").then((module) => module.IntegrationsDashboard), { loading: PageSectionLoader });
const InventoryDashboard = dynamic(() => import("@/components/inventory-dashboard").then((module) => module.InventoryDashboard), { loading: PageSectionLoader });
const AccountsLedger = dynamic(() => import("@/components/accounts-ledger").then((module) => module.AccountsLedger), { loading: PageSectionLoader });
const RawDataDashboard = dynamic(() => import("@/components/raw-data-dashboard").then((module) => module.RawDataDashboard), { loading: PageSectionLoader });
const Employee360 = dynamic(() => import("@/components/employee-360").then((module) => module.Employee360), { loading: PageSectionLoader });
const EmployeeDirectory = dynamic(() => import("@/components/employee-directory").then((module) => module.EmployeeDirectory), { loading: PageSectionLoader });
const HRDashboardPage = dynamic(
  () => import("@/components/hr-dashboard").then((module) => module.HRDashboardPage),
  { loading: PageSectionLoader }
);
const SiteVisitsDashboard = dynamic(() => import("@/components/site-visits-dashboard").then((module) => module.SiteVisitsDashboard), { loading: PageSectionLoader });
const DocumentsPage = dynamic(() => import("@/components/hr-management").then((module) => module.DocumentsPage), { loading: PageSectionLoader });
const HolidaysPage = dynamic(() => import("@/components/hr-management").then((module) => module.HolidaysPage), { loading: PageSectionLoader });
const LeaveBalancesPage = dynamic(() => import("@/components/hr-management").then((module) => module.LeaveBalancesPage), { loading: PageSectionLoader });
const LeaveRequestsPage = dynamic(() => import("@/components/hr-management").then((module) => module.LeaveRequestsPage), { loading: PageSectionLoader });
const LeaveTypesPage = dynamic(() => import("@/components/hr-management").then((module) => module.LeaveTypesPage), { loading: PageSectionLoader });

export function NiprixApp({ page, leadId, employeeId, customerId }: { page: "overview" | "attendance" | "followups" | "tasks" | "reminders" | "leads" | "leadRecovery" | "siteVisits" | "rawData" | "integrations" | "inventory" | "accounts" | "employees" | "employee" | "hr" | "leaveRequests" | "leaveTypes" | "leaveBalances" | "holidays" | "documents"; leadId?: number; employeeId?: number; customerId?: number }) {
  const { user } = useNiprixAuth();

  return page === "hr" ? <HRDashboardPage role={user.role} /> : page === "leaveRequests" ? <LeaveRequestsPage role={user.role} /> : page === "leaveTypes" ? <LeaveTypesPage role={user.role} /> : page === "leaveBalances" ? <LeaveBalancesPage /> : page === "holidays" ? <HolidaysPage role={user.role} /> : page === "documents" ? <DocumentsPage role={user.role} /> : page === "employees" ? <EmployeeDirectory role={user.role} /> : page === "employee" && employeeId ? <Employee360 employeeId={employeeId} role={user.role} /> : page === "attendance" ? <AttendanceDashboard role={user.role} /> : page === "leads" ? <LeadsDashboard role={user.role} leadId={leadId} /> : page === "leadRecovery" ? <LeadRecoveryDashboard role={user.role} /> : page === "siteVisits" ? <SiteVisitsDashboard /> : page === "rawData" ? <RawDataDashboard role={user.role} /> : page === "integrations" ? <IntegrationsDashboard /> : page === "inventory" ? <InventoryDashboard role={user.role} /> : page === "accounts" ? <AccountsLedger role={user.role} customerId={customerId} /> : page === "followups" ? <WorkDashboard kind="followups" role={user.role} /> : page === "tasks" ? <WorkDashboard kind="tasks" role={user.role} /> : page === "reminders" ? <ReminderPreferences /> : <Overview user={user} />;
}
