"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import {
  ApiError,
  type EmployeeOption,
  type FollowUp,
  type FollowUpActivity,
  type Role,
  type Task,
  type WorkspaceSummary,
} from "@/lib/types";

const priorities = ["LOW", "MEDIUM", "HIGH", "URGENT"] as const;
const followUpTypes = [
  "CALL",
  "WHATSAPP",
  "EMAIL",
  "SITE_VISIT",
  "MEETING",
  "OTHER",
] as const;
const followUpStatuses = [
  "NEW",
  "CONTACTED",
  "SITE_VISIT_REQUESTED",
  "SITE_VISIT_DONE",
  "FOLLOW_UP_NEEDED",
  "FOLLOW_UP_DONE",
  "POSTPONED",
  "DIFFERENT_REQUIREMENT",
  "NOT_INTERESTED",
  "CLOSED",
  "INVALID_PHONE",
  "NOT_LOOKING_PROPERTY",
  "USER_IS_AGENT",
] as const;
const taskStatuses = ["TODO", "IN_PROGRESS", "BLOCKED", "CANCELLED"] as const;

function message(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
const contactNumber = (phone?: string) => (phone || "").replace(/\D/g, "").replace(/^00/, "");
const hasUsablePhone = (phone?: string) => /^\d{7,15}$/.test(contactNumber(phone));
function whatsappUrl(phone: string, employeeName?: string) {
  const text = `Hello Sir, this is ${employeeName || "our team"} from Paramshiv Real Estate. You had shown interest in property. Please share your property requirement, preferred location, budget and other details so we can assist you with suitable options.`;
  return `https://wa.me/${contactNumber(phone)}?text=${encodeURIComponent(text)}`;
}
function localDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const two = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}T${two(date.getHours())}:${two(date.getMinutes())}`;
}
function label(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function badge(value: string) {
  const tone =
    value === "COMPLETED"
      ? "bg-[#e9f6f1] text-[#168460]"
      : value === "URGENT" || value === "HIGH" || value === "MISSED"
        ? "bg-[#fff0f1] text-[#b12938]"
        : value === "POSTPONED" || value === "BLOCKED"
          ? "bg-[#fff4e5] text-[#a96908]"
          : "bg-[#eaf4ff] text-[#0869d8]";
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}
    >
      {label(value)}
    </span>
  );
}

function Card({
  label: caption,
  value,
  alert = false,
}: {
  label: string;
  value: number;
  alert?: boolean;
}) {
  return (
    <div className="app-card rounded-2xl p-4">
      <p className="text-xs font-semibold tracking-[.08em] text-[#75869b]">
        {caption.toUpperCase()}
      </p>
      <p
        className={`mt-2 text-2xl font-semibold ${alert && value ? "text-[#c43d4b]" : "text-[#203756]"}`}
      >
        {value}
      </p>
    </div>
  );
}

function Dialog({
  title,
  children,
  close,
}: {
  title: string;
  children: React.ReactNode;
  close: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"
    >
      <button
        aria-label="Close dialog"
        onClick={close}
        className="mobile-sheet-backdrop absolute inset-0"
      />
      <div className="mobile-sheet relative max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-[24px] bg-white p-5 shadow-2xl sm:rounded-2xl sm:p-6">
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[#d8e1ec] sm:hidden" />
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-[#203756]">{title}</h2>
          <button
            onClick={close}
            className="focus-ring rounded-lg px-2 py-1 text-xl text-[#60708a]"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Select({
  name,
  value,
  onChange,
  children,
}: {
  name: string;
  value?: string | number;
  onChange?: (value: string) => void;
  children: ReactNode;
}) {
  return onChange ? (
    <select
      name={name}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"
    >
      {children}
    </select>
  ) : (
    <select
      name={name}
      defaultValue={value}
      className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] bg-white px-3 py-2.5 text-sm"
    >
      {children}
    </select>
  );
}
function Input({
  name,
  label: caption,
  defaultValue,
  type = "text",
  required = false,
}: {
  name: string;
  label: string;
  defaultValue?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm font-medium text-[#405773]">
      {caption}
      <input
        name={name}
        type={type}
        defaultValue={defaultValue}
        required={required}
        className="focus-ring mt-1 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
      />
    </label>
  );
}

export function WorkDashboard({
  kind,
  role,
}: {
  kind: "followups" | "tasks";
  role: Role;
}) {
  const isFollowUp = kind === "followups";
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [rows, setRows] = useState<(FollowUp | Task)[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState<FollowUp | Task | null | "new">(null);
  const [action, setAction] = useState<FollowUp | null>(null);
  const [activities, setActivities] = useState<FollowUpActivity[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) query.set("search", search);
    if (status) query.set("status", status);
    if (priority) query.set("priority", priority);
    if (assignedTo) query.set("assigned_to", assignedTo);
    try {
      const [nextSummary, listed, people] = await Promise.all([
        api.workspaceSummary(),
        isFollowUp
          ? api.followUps(query.toString())
          : api.tasks(query.toString()),
        api.employees(),
      ]);
      setSummary(nextSummary);
      setRows(listed.results);
      setTotal(listed.count);
      setEmployees(Array.isArray(people) ? people : people.results);
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 403
          ? `Workspace access is restricted. ${message(caught, "")}`
          : message(caught, "Workspace data could not be loaded."),
      );
    } finally {
      setLoading(false);
    }
  }, [assignedTo, isFollowUp, page, priority, search, status]);
  useEffect(() => {
    // Search and filter state can change in quick succession; coalesce them
    // into one request instead of competing stale responses.
    const id = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(id);
  }, [load]);
  const metrics = summary
    ? isFollowUp
      ? [
          ["Today", summary.follow_ups.today],
          ["Pending", summary.follow_ups.pending],
          ["Upcoming", summary.follow_ups.upcoming],
          ["Overdue", summary.follow_ups.overdue],
        ]
      : [
          ["Assigned", summary.tasks.assigned],
          ["Due today", summary.tasks.due_today],
          ["Completed", summary.tasks.completed],
          ["Overdue", summary.tasks.overdue],
        ]
    : [];
  async function complete(item: FollowUp | Task) {
    setBusy(true);
    try {
      if (isFollowUp) await api.completeFollowUp(item.id);
      else await api.completeTask(item.id);
      await load();
    } catch (caught) {
      setError(message(caught, "Unable to complete this item."));
    } finally {
      setBusy(false);
    }
  }
  async function showActivities(item: FollowUp) {
    try {
      const result = await api.followUpActivities(item.id);
      setActivities(result.results);
      setAction(item);
    } catch (caught) {
      setError(message(caught, "Activity history could not be loaded."));
    }
  }
  async function removeFollowUp(item: FollowUp) {
    if (!window.confirm(`Delete the follow-up “${item.title}”? The associated lead will be preserved.`)) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteFollowUp(item.id);
      setRows((current) => current.filter((row) => row.id !== item.id));
      setTotal((current) => Math.max(0, current - 1));
    } catch (caught) {
      setError(message(caught, "Unable to delete the follow-up."));
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      if (isFollowUp) {
        const payload = {
          title: String(data.get("title") || ""),
          description: String(data.get("description") || ""),
          assigned_to: Number(data.get("assigned_to")),
          follow_up_type: String(data.get("follow_up_type")),
          scheduled_at: new Date(
            String(data.get("scheduled_at")),
          ).toISOString(),
          priority: String(data.get("priority")),
          status: String(data.get("status")),
        };
        if (form && form !== "new") await api.updateFollowUp(form.id, payload);
        else await api.createFollowUp(payload);
      } else {
        const payload = {
          title: String(data.get("title") || ""),
          description: String(data.get("description") || ""),
          assigned_to: Number(data.get("assigned_to")),
          due_date: String(data.get("due_date")),
          due_time: String(data.get("due_time") || "") || null,
          priority: String(data.get("priority")),
          status: String(data.get("status")),
        };
        if (form && form !== "new") await api.updateTask(form.id, payload);
        else await api.createTask(payload);
      }
      setForm(null);
      await load();
    } catch (caught) {
      setError(message(caught, "Unable to save the item."));
    } finally {
      setBusy(false);
    }
  }
  async function postpone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api.postponeFollowUp(
        action.id,
        new Date(String(data.get("scheduled_at"))).toISOString(),
        String(data.get("note") || ""),
      );
      setAction(null);
      await load();
    } catch (caught) {
      setError(message(caught, "Unable to postpone the follow-up."));
    } finally {
      setBusy(false);
    }
  }
  const canAssign = role !== "EMPLOYEE";
  return (
    <section>
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="text-sm font-medium text-[#0869d8]">
            {isFollowUp ? "FOLLOW-UP WORKSPACE" : "TASK WORKSPACE"}
          </p>
          <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-[#10233f] sm:text-3xl">
            {isFollowUp
              ? "Keep every conversation moving."
              : "Plan work. Finish with clarity."}
          </h1>
          <p className="mt-2 text-sm text-[#60708a]">
            {summary
              ? `${label(summary.scope)} scope · live CRM records only`
              : "Loading your assigned work"}
          </p>
        </div>
        <button
          onClick={() => setForm("new")}
          className="focus-ring inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white shadow-sm"
        >
          <Icon name="plus" className="h-4 w-4" /> Create {isFollowUp ? "follow-up" : "task"}
        </button>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([caption, value]) => (
          <Card
            key={String(caption)}
            label={String(caption)}
            value={Number(value)}
            alert={caption === "Overdue"}
          />
        ))}
      </div>
      {error && (
        <div
          role="alert"
          className="mt-5 flex items-center justify-between gap-3 rounded-xl border border-[#f0c7cd] bg-[#fffafb] p-4 text-sm text-[#9a5860]"
        >
          <span>{error}</span>
          <button
            onClick={() => void load()}
            className="focus-ring rounded-lg bg-white px-3 py-1.5 font-semibold text-[#9b3040]"
          >
            Retry
          </button>
        </div>
      )}
      <div className="app-card mt-6 rounded-2xl p-4 sm:p-5">
        <div className="flex gap-2 md:hidden"><label className="relative min-w-0 flex-1"><span className="sr-only">Search work</span><Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#75869b]" /><input value={search} onChange={(event) => { setPage(1); setSearch(event.target.value); }} placeholder={`Search ${isFollowUp ? "follow-ups" : "tasks"}`} className="focus-ring w-full rounded-xl border border-[#dce4ee] py-2.5 pl-9 pr-3 text-sm" /></label><button onClick={() => setFiltersOpen(true)} className="focus-ring inline-flex min-h-11 items-center gap-1 rounded-xl border border-[#dce4ee] px-3 text-sm font-semibold text-[#405773]"><Icon name="filter" className="h-4 w-4" />Filter</button></div>
        <div className="hidden gap-3 md:grid md:grid-cols-4">
          <input
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
            placeholder={`Search ${isFollowUp ? "follow-ups" : "tasks"}`}
            className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
          />
          <Select
            name="filter-status"
            value={status}
            onChange={(value) => {
              setPage(1);
              setStatus(value);
            }}
          >
            <option value="">All statuses</option>
            {(isFollowUp
              ? [...followUpStatuses, "COMPLETED"]
              : [...taskStatuses, "COMPLETED"]
            ).map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </Select>
          <Select
            name="filter-priority"
            value={priority}
            onChange={(value) => {
              setPage(1);
              setPriority(value);
            }}
          >
            <option value="">All priorities</option>
            {priorities.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </Select>
          <Select
            name="filter-assignee"
            value={assignedTo}
            onChange={(value) => {
              setPage(1);
              setAssignedTo(value);
            }}
          >
            <option value="">All permitted owners</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.display_name || employee.username}
              </option>
            ))}
          </Select>
        </div>
        {isFollowUp ? (
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            {(rows as FollowUp[]).map((followUp) => {
              const done = followUp.status === "COMPLETED";
              const owner = followUp.assigned_to_detail.display_name || followUp.assigned_to_detail.username;
              return <article key={followUp.id} className="rounded-2xl border border-[#e5ebf3] bg-[#fbfdff] p-5 shadow-sm transition-shadow hover:shadow-md">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-xs font-semibold tracking-[.1em] text-[#0869d8]">FOLLOW-UP #{followUp.id}</p><h3 className="mt-1 text-lg font-semibold text-[#203756]">{followUp.lead_name || followUp.title}</h3><p className="mt-1 text-sm text-[#60708a]">{followUp.lead_phone || "No linked customer number"}</p></div>
                  <div className="flex flex-wrap gap-2">{badge(followUp.status)}{badge(followUp.priority)}</div>
                </div>
                <div className="mt-4 grid gap-3 border-y border-[#edf1f5] py-4 text-sm sm:grid-cols-2">
                  <div><p className="text-xs font-semibold uppercase tracking-[.08em] text-[#8291a4]">Scheduled</p><p className="mt-1 font-medium text-[#405773]">{new Date(followUp.scheduled_at).toLocaleString()}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-[.08em] text-[#8291a4]">Owner</p><p className="mt-1 font-medium text-[#405773]">{owner}</p></div>
                  <div className="sm:col-span-2"><p className="text-xs font-semibold uppercase tracking-[.08em] text-[#8291a4]">Follow-up</p><p className="mt-1 text-[#60708a]">{followUp.title}{followUp.description ? ` · ${followUp.description}` : ""}</p></div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {hasUsablePhone(followUp.lead_phone) && <a href={`tel:${contactNumber(followUp.lead_phone)}`} className="focus-ring inline-flex min-h-10 items-center gap-1 rounded-xl bg-[#e9f6f1] px-3 py-2 text-xs font-semibold text-[#168460]"><Icon name="phone" className="h-3.5 w-3.5" />Call</a>}
                  {hasUsablePhone(followUp.lead_phone) && <a target="_blank" rel="noreferrer" href={whatsappUrl(followUp.lead_phone, owner)} className="focus-ring inline-flex min-h-10 items-center gap-1 rounded-xl bg-[#e9f6f1] px-3 py-2 text-xs font-semibold text-[#168460]"><Icon name="message" className="h-3.5 w-3.5" />WhatsApp</a>}
                  <button onClick={() => setForm(followUp)} className="focus-ring rounded-lg border border-[#dce4ee] px-3 py-2 text-xs font-semibold text-[#0869d8]">Edit</button>
                  {!done && <button disabled={busy} onClick={() => void complete(followUp)} className="focus-ring rounded-lg border border-[#b9e5d5] px-3 py-2 text-xs font-semibold text-[#168460] disabled:opacity-50">Complete</button>}
                  <button onClick={() => { setAction(followUp); setActivities(null); }} className="focus-ring rounded-lg border border-[#f5d9a6] px-3 py-2 text-xs font-semibold text-[#a96908]">Postpone</button>
                  {!done && <button disabled={busy} onClick={() => void removeFollowUp(followUp)} className="focus-ring rounded-lg border border-[#f0c7cd] px-3 py-2 text-xs font-semibold text-[#b12938] disabled:opacity-50">Delete</button>}
                  <button onClick={() => void showActivities(followUp)} className="focus-ring rounded-lg px-3 py-2 text-xs font-semibold text-[#60708a]">History</button>
                </div>
              </article>;
            })}
          </div>
        ) : <><div className="mt-5 grid gap-3 md:hidden">{loading ? [0, 1, 2].map((item) => <div key={item} className="shimmer h-32 rounded-2xl" />) : (rows as Task[]).map((task) => { const done = task.status === "COMPLETED"; return <article key={task.id} className={`rounded-2xl border p-4 ${done ? "border-[#dbe9e2] bg-[#f7fbf9]" : "border-[#e5ebf3] bg-white"}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className={`truncate text-[16px] font-bold ${done ? "text-[#607a6e] line-through" : "text-[#203756]"}`}>{task.title}</h2><p className="mt-1 text-xs text-[#75869b]">Due {task.due_date}{task.due_time ? ` · ${task.due_time}` : ""}</p></div>{badge(task.priority)}</div>{task.description && <p className="mt-3 line-clamp-2 text-sm text-[#60708a]">{task.description}</p>}<div className="mt-3 flex items-center justify-between gap-2 border-t border-[#edf1f5] pt-3"><div className="flex gap-1.5">{badge(task.status)}</div><div className="flex gap-2"><button onClick={() => setForm(task)} className="focus-ring min-h-10 rounded-xl px-3 text-xs font-bold text-[#0869d8]">Edit</button>{!done && <button disabled={busy} onClick={() => void complete(task)} className="focus-ring min-h-10 rounded-xl bg-[#e9f6f1] px-3 text-xs font-bold text-[#168460] disabled:opacity-50">Complete</button>}</div></div></article>; })}</div><div className="mt-5 hidden overflow-x-auto md:block">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-[#e5ebf3] text-xs uppercase tracking-[.08em] text-[#8291a4]">
              <tr>
                <th className="pb-3 font-semibold">
                  Task
                </th>
                <th className="pb-3 font-semibold">Owner</th>
                <th className="pb-3 font-semibold">When</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 font-semibold">Priority</th>
                <th className="pb-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => {
                const due = isFollowUp
  ? new Date((item as FollowUp).scheduled_at).toLocaleString()
  : `${(item as Task).due_date}${(item as Task).due_time ? ` · ${(item as Task).due_time}` : ""}`;
                const done = item.status === "COMPLETED";
                return (
                  <tr
                    key={item.id}
                    className="border-b border-[#edf1f5] last:border-0"
                  >
                    <td className="py-4">
                      <p className="font-semibold text-[#2a405f]">
                        {item.title}
                      </p>
                      <p className="mt-1 max-w-xs truncate text-xs text-[#7b8ba1]">
                        {item.description || "No description"}
                      </p>
                    </td>
                    <td className="py-4 text-[#526984]">
                      {item.assigned_to_detail.display_name ||
                        item.assigned_to_detail.username}
                    </td>
                    <td className="py-4 text-[#526984]">{due}</td>
                    <td className="py-4">{badge(item.status)}</td>
                    <td className="py-4">{badge(item.priority)}</td>
                    <td className="py-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => setForm(item)}
                        className="focus-ring mr-2 rounded-lg px-2 py-1 text-xs font-semibold text-[#0869d8]"
                      >
                        Edit
                      </button>
                      {!done && (
                        <button
                          disabled={busy}
                          onClick={() => void complete(item)}
                          className="focus-ring mr-2 rounded-lg px-2 py-1 text-xs font-semibold text-[#168460]"
                        >
                          Complete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div></>}
        {!loading && rows.length === 0 && (
          <div className="py-12 text-center">
            <p className="font-semibold text-[#405773]">
              No {isFollowUp ? "follow-ups" : "tasks"} found
            </p>
            <p className="mt-1 text-sm text-[#7b8ba1]">
              Adjust the filters or create the first record.
            </p>
          </div>
        )}
        <div className="mt-4 flex items-center justify-between text-sm text-[#60708a]">
          <span>
            {loading ? "Loading…" : `${total} record${total === 1 ? "" : "s"}`}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 1 || loading}
              onClick={() => setPage(page - 1)}
              className="focus-ring rounded-lg border px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={rows.length < 20 || loading}
              onClick={() => setPage(page + 1)}
              className="focus-ring rounded-lg border px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
      {form && (
        <Dialog
          title={
            form === "new"
              ? `Create ${isFollowUp ? "follow-up" : "task"}`
              : `Edit ${isFollowUp ? "follow-up" : "task"}`
          }
          close={() => setForm(null)}
        >
          <form onSubmit={submit} className="mt-5 grid gap-4 sm:grid-cols-2">
            <Input
              name="title"
              label="Title"
              required
              defaultValue={form === "new" ? "" : form.title}
            />
            <label className="block text-sm font-medium text-[#405773]">
              Assigned to
              <Select
                name="assigned_to"
                value={form === "new" ? employees[0]?.id : form.assigned_to}
              >
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.display_name || employee.username} ·{" "}
                    {employee.employee_code}
                  </option>
                ))}
              </Select>
            </label>
            {isFollowUp ? (
              <>
                <label className="block text-sm font-medium text-[#405773]">
                  Follow-up type
                  <Select
                    name="follow_up_type"
                    value={
                      form === "new"
                        ? "CALL"
                        : (form as FollowUp).follow_up_type
                    }
                  >
                    {followUpTypes.map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </Select>
                </label>
                <Input
                  name="scheduled_at"
                  label="Scheduled date & time"
                  type="datetime-local"
                  required
                  defaultValue={
                    form === "new"
                      ? ""
                      : localDateTime((form as FollowUp).scheduled_at)
                  }
                />
              </>
            ) : (
              <>
                <Input
                  name="due_date"
                  label="Due date"
                  type="date"
                  required
                  defaultValue={form === "new" ? "" : (form as Task).due_date}
                />
                <Input
                  name="due_time"
                  label="Due time"
                  type="time"
                  defaultValue={
                    form === "new" ? "" : (form as Task).due_time || ""
                  }
                />
              </>
            )}
            <label className="block text-sm font-medium text-[#405773]">
              Priority
              <Select
                name="priority"
                value={form === "new" ? "MEDIUM" : form.priority}
              >
                {priorities.map((value) => (
                  <option key={value} value={value}>
                    {label(value)}
                  </option>
                ))}
              </Select>
            </label>
            <label className="block text-sm font-medium text-[#405773]">
              Status
              <Select
                name="status"
                value={
                  form === "new"
                    ? isFollowUp
                      ? "PENDING"
                      : "TODO"
                    : form.status
                }
              >
                {(isFollowUp ? followUpStatuses : taskStatuses).map((value) => (
                  <option key={value} value={value}>
                    {label(value)}
                  </option>
                ))}
              </Select>
            </label>
            <label className="sm:col-span-2 block text-sm font-medium text-[#405773]">
              Description
              <textarea
                name="description"
                defaultValue={form === "new" ? "" : form.description}
                className="focus-ring mt-1 min-h-24 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
              />
            </label>
            <div className="sm:col-span-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setForm(null)}
                className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]"
              >
                Cancel
              </button>
              <button
                disabled={busy || employees.length === 0}
                className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
            {!canAssign && (
              <p className="sm:col-span-2 text-xs text-[#7b8ba1]">
                You can only assign work to yourself.
              </p>
            )}
          </form>
        </Dialog>
      )}
      {filtersOpen && <Dialog title={`Filter ${isFollowUp ? "follow-ups" : "tasks"}`} close={() => setFiltersOpen(false)}><div className="mt-4 grid gap-3"><label className="text-sm font-medium text-[#405773]">Status<Select name="filter-status-mobile" value={status} onChange={(value) => { setPage(1); setStatus(value); }}><option value="">All statuses</option>{(isFollowUp ? [...followUpStatuses, "COMPLETED"] : [...taskStatuses, "COMPLETED"]).map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label><label className="text-sm font-medium text-[#405773]">Priority<Select name="filter-priority-mobile" value={priority} onChange={(value) => { setPage(1); setPriority(value); }}><option value="">All priorities</option>{priorities.map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label><label className="text-sm font-medium text-[#405773]">Owner<Select name="filter-owner-mobile" value={assignedTo} onChange={(value) => { setPage(1); setAssignedTo(value); }}><option value="">All permitted owners</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.display_name || employee.username}</option>)}</Select></label></div><div className="mt-5 grid grid-cols-2 gap-3"><button onClick={() => { setPage(1); setStatus(""); setPriority(""); setAssignedTo(""); }} className="focus-ring rounded-xl border border-[#dce4ee] px-4 py-2.5 text-sm font-bold text-[#405773]">Reset</button><button onClick={() => setFiltersOpen(false)} className="focus-ring rounded-xl bg-[#0869d8] px-4 py-2.5 text-sm font-bold text-white">Apply filters</button></div></Dialog>}
      {action && (
        <Dialog
          title={activities ? "Follow-up history" : "Postpone follow-up"}
          close={() => {
            setAction(null);
            setActivities(null);
          }}
        >
          {activities ? (
            <div className="mt-5 space-y-3">
              {activities.map((entry) => (
                <article
                  key={entry.id}
                  className="rounded-xl border border-[#e5ebf3] p-3"
                >
                  <div className="flex justify-between gap-3">
                    <span className="font-semibold text-[#405773]">
                      {label(entry.activity_type)}
                    </span>
                    <span className="text-xs text-[#7b8ba1]">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-[#60708a]">
                    {entry.note ||
                      `${entry.performed_by_name} updated this follow-up.`}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <form onSubmit={postpone} className="mt-5 space-y-4">
              <Input
                name="scheduled_at"
                label="New scheduled date & time"
                type="datetime-local"
                required
                defaultValue={localDateTime(action.scheduled_at)}
              />
              <label className="block text-sm font-medium text-[#405773]">
                Reason
                <textarea
                  name="note"
                  className="focus-ring mt-1 min-h-24 w-full rounded-lg border border-[#dce4ee] px-3 py-2.5 text-sm"
                />
              </label>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setAction(null)}
                  className="focus-ring rounded-lg px-4 py-2.5 text-sm font-semibold text-[#60708a]"
                >
                  Cancel
                </button>
                <button
                  disabled={busy}
                  className="focus-ring rounded-lg bg-[#0869d8] px-4 py-2.5 text-sm font-semibold text-white"
                >
                  {busy ? "Saving…" : "Postpone"}
                </button>
              </div>
            </form>
          )}
        </Dialog>
      )}
    </section>
  );
}
