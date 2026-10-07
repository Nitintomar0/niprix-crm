"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { EmployeeProfile, Paginated, Role } from "@/lib/types";

const unpack = (data: Paginated<EmployeeProfile> | EmployeeProfile[]) =>
  Array.isArray(data) ? data : data.results;
const initials = (employee: EmployeeProfile) =>
  (employee.full_name || employee.username).slice(0, 2).toUpperCase();

export function EmployeeDirectory({ role }: { role: Role }) {
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    const query = new URLSearchParams({
      ...(search ? { search } : {}),
      ...(status ? { employment_status: status } : {}),
    }).toString();
    try {
      setEmployees(unpack(await api.employeeDirectory(query)));
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Employees could not be loaded. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }, [search, status]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 200);
    return () => window.clearTimeout(timer);
  }, [load]);
  const stats = useMemo(
    () => ({
      active: employees.filter((item) => item.employment_status === "ACTIVE")
        .length,
      onboarding: employees.filter(
        (item) => item.employment_status === "ONBOARDING",
      ).length,
      inactive: employees.filter((item) =>
        ["INACTIVE", "OFFBOARDED"].includes(item.employment_status),
      ).length,
    }),
    [employees],
  );
  const organizationOptions = useMemo(() => {
    const branches = new Map<number, string>();
    const departments = new Map<number, string>();
    employees.forEach((employee) => {
      branches.set(
        employee.branch,
        employee.branch_name || `Branch #${employee.branch}`,
      );
      departments.set(
        employee.department,
        employee.department_name || `Department #${employee.department}`,
      );
    });
    return { branches: [...branches], departments: [...departments] };
  }, [employees]);
  async function createEmployee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {
      username: data.get("username"),
      email: data.get("email"),
      password: data.get("password"),
      first_name: data.get("first_name"),
      last_name: data.get("last_name"),
      employee_code: data.get("employee_code"),
      branch: Number(data.get("branch")),
      department: Number(data.get("department")),
      role: "EMPLOYEE",
    };
    try {
      await api.createEmployee(body);
      setCreating(false);
      setNotice(
        "Employee account created. They can now sign in with the credentials you set.",
      );
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Employee could not be created.",
      );
    }
  }
  async function deactivate(employee: EmployeeProfile) {
    if (
      !window.confirm(
        `Deactivate ${employee.full_name || employee.username}? Their active leads and pending follow-ups will be reassigned.`,
      )
    )
      return;
    try {
      const result = await api.deactivateEmployee(employee.id);
      setNotice(
        result.already_deactivated
          ? "Employee is already inactive."
          : `Employee deactivated. ${result.leads_reassigned} leads and ${result.follow_ups_reassigned} follow-ups were reassigned.`,
      );
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Employee could not be deactivated.",
      );
    }
  }
  async function remove(employee: EmployeeProfile) {
    if (
      !window.confirm(
        `Permanently delete ${employee.full_name || employee.username}? This is only allowed when retained CRM and attendance history can be preserved safely.`,
      )
    )
      return;
    try {
      await api.deleteEmployee(employee.id);
      setNotice("Inactive employee deleted.");
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Employee could not be deleted safely.",
      );
    }
  }
  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="text-xs font-semibold tracking-[.14em] text-[#0869d8]">
            PEOPLE & ORGANIZATION
          </p>
          <h1 className="mt-1 text-3xl font-bold text-[#10233f]">Employees</h1>
          <p className="mt-2 text-sm text-[#60708a]">
            Manage your organization and open an authorized employee workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2 text-sm"
            placeholder="Search employees"
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="focus-ring rounded-lg border border-[#dce4ee] bg-white px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ONBOARDING">Onboarding</option>
            <option value="NOTICE_PERIOD">Notice period</option>
            <option value="INACTIVE">Inactive</option>
            <option value="OFFBOARDED">Offboarded</option>
          </select>
          {role === "CEO" && (
            <button
              onClick={() => setCreating(true)}
              className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2 text-sm font-semibold text-white"
            >
              Create employee
            </button>
          )}
        </div>
      </section>
      {error && (
        <section
          role="alert"
          className="border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </section>
      )}
      {notice && (
        <section className="border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {notice}
        </section>
      )}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Total employees", employees.length],
          ["Active", stats.active],
          ["Onboarding", stats.onboarding],
          ["Inactive / offboarded", stats.inactive],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            className="border-l-4 border-[#0869d8] bg-white px-4 py-4 shadow-sm"
          >
            <p className="text-xs text-[#718198]">{label}</p>
            <p className="mt-1 text-2xl font-bold text-[#10233f]">{value}</p>
          </div>
        ))}
      </section>
      {loading ? (
        <section className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-16 animate-pulse bg-white" />
          ))}
        </section>
      ) : employees.length === 0 ? (
        <section className="bg-white p-10 text-center">
          <h2 className="font-semibold">No employees found</h2>
          <p className="mt-2 text-sm text-[#60708a]">
            Change the search or status filter.
          </p>
        </section>
      ) : (
        <>
          <section className="hidden overflow-x-auto bg-white shadow-sm md:block">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="border-b bg-[#f8fbff] text-xs uppercase text-[#718198]">
                <tr>
                  <th className="px-5 py-3">Employee</th>
                  <th>Designation</th>
                  <th>Department</th>
                  <th>Team</th>
                  <th>Manager</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {employees.map((employee) => (
                  <tr
                    key={employee.id}
                    className="border-b border-[#edf1f6] hover:bg-[#f8fbff]"
                  >
                    <td className="px-5 py-4">
                      <Link
                        href={`/employees/${employee.id}`}
                        className="flex items-center gap-3"
                      >
                        <span
                          style={
                            employee.profile_photo
                              ? {
                                  backgroundImage: `url(${employee.profile_photo})`,
                                }
                              : undefined
                          }
                          className="flex h-10 w-10 items-center justify-center rounded-full bg-[#dceeff] bg-cover bg-center text-xs font-bold text-[#0869d8]"
                        >
                          {employee.profile_photo ? null : initials(employee)}
                        </span>
                        <span>
                          <strong className="block text-[#10233f]">
                            {employee.full_name || employee.username}
                          </strong>
                          <small className="text-[#718198]">
                            {employee.employee_code}
                          </small>
                        </span>
                      </Link>
                    </td>
                    <td>{employee.designation || "-"}</td>
                    <td>{employee.department_name || "-"}</td>
                    <td>{employee.team || "-"}</td>
                    <td>{employee.reporting_manager_name || "-"}</td>
                    <td>
                      <span className="rounded-full bg-[#eaf7f1] px-2 py-1 text-xs font-semibold text-[#18795b]">
                        {employee.employment_status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>{employee.joining_date || "-"}</td>
                    <td className="pr-5 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <Link
                          className="font-semibold text-[#0869d8]"
                          href={`/employees/${employee.id}`}
                        >
                          Open
                        </Link>
                        {role === "CEO" && employee.is_active && (
                          <button
                            onClick={() => void deactivate(employee)}
                            className="font-semibold text-[#b12938]"
                          >
                            Deactivate
                          </button>
                        )}
                        {role === "CEO" && !employee.is_active && ["INACTIVE", "OFFBOARDED"].includes(employee.employment_status) && (
                          <button onClick={() => void remove(employee)} className="font-semibold text-[#b12938]">Delete</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className="grid gap-3 md:hidden">
            {employees.map((employee) => (
              <Link
                href={`/employees/${employee.id}`}
                key={employee.id}
                className="bg-white p-4 shadow-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[#dceeff] font-bold text-[#0869d8]">
                    {initials(employee)}
                  </span>
                  <div>
                    <strong className="block text-[#10233f]">
                      {employee.full_name || employee.username}
                    </strong>
                    <p className="text-sm text-[#60708a]">
                      {employee.designation || employee.employee_code}
                    </p>
                    <p className="mt-1 text-xs text-[#718198]">
                      {employee.employment_status.replaceAll("_", " ")}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </section>
        </>
      )}
      {creating && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"
        >
          <button
            aria-label="Close"
            onClick={() => setCreating(false)}
            className="mobile-sheet-backdrop absolute inset-0"
          />
          <form
            onSubmit={createEmployee}
            className="mobile-sheet relative max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6"
          >
            <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#d8e1ec] sm:hidden" />
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-[#10233f]">
                  Create employee
                </h2>
                <p className="mt-1 text-sm text-[#60708a]">
                  This creates an employee login. Only CEOs can perform this
                  action.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="text-xl text-[#60708a]"
              >
                ×
              </button>
            </div>
            {organizationOptions.branches.length === 0 ? (
              <p className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                Create a branch and department before creating the first
                employee.
              </p>
            ) : (
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-medium text-[#405773]">
                  First name
                  <input
                    name="first_name"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Last name
                  <input
                    name="last_name"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Username
                  <input
                    required
                    name="username"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Email
                  <input
                    required
                    type="email"
                    name="email"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Temporary password
                  <input
                    required
                    minLength={8}
                    type="password"
                    name="password"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Employee code
                  <input
                    required
                    name="employee_code"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  />
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Branch
                  <select
                    required
                    name="branch"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  >
                    {organizationOptions.branches.map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium text-[#405773]">
                  Department
                  <select
                    required
                    name="department"
                    className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2"
                  >
                    {organizationOptions.departments.map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]"
              >
                Cancel
              </button>
              {organizationOptions.branches.length > 0 && (
                <button className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white">
                  Create employee
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
