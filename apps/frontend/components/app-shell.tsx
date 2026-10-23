"use client";

import Link from "next/link";
import { FormEvent, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand";
import { Icon } from "@/components/icons";
import { NotificationCenter } from "@/components/notification-center";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Role, User } from "@/lib/types";

const roleLabels: Record<Role, string> = { CEO: "CEO / Administrator", MANAGER: "Team manager", EMPLOYEE: "Employee workspace" };
type NavItem = { icon: "home" | "chart" | "users" | "building" | "clock" | "calendar" | "check" | "alert"; label: string; href: string; group: "Workspace" | "Sales" | "Operations" | "Tools" };

function titleFor(pathname: string | null) {
  if (pathname === "/inventory") return "Inventory";
  if (pathname === "/raw-data") return "Raw Data";
  if (pathname?.startsWith("/hr")) return "HR Command Center";
  if (pathname?.startsWith("/leave-") || pathname === "/holidays" || pathname === "/employee-documents") return "HR management";
  if (pathname === "/attendance") return "Attendance";
  if (pathname?.startsWith("/leads")) return "Leads";
  if (pathname === "/lead-recovery") return "Lead Recovery";
  if (pathname === "/site-visits") return "Site Visits";
  if (pathname === "/follow-ups") return "Follow-ups";
  if (pathname === "/tasks") return "Tasks";
  if (pathname === "/reminders") return "Reminders";
  if (pathname?.startsWith("/employees")) return "People";
  if (pathname === "/integrations") return "Integrations";
  return "Dashboard";
}

export function AppShell({ user, children, onLogout }: { user: User; children: ReactNode; onLogout: () => void }) {
  const [desktopExpanded, setDesktopExpanded] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const navigation: NavItem[] = [
    { icon: "home", label: "Overview", href: "/", group: "Workspace" },
    ...(user.role !== "EMPLOYEE" ? [{ icon: "chart" as const, label: "HR Dashboard", href: "/hr", group: "Workspace" as const }] : []),
    { icon: "users", label: "Leads", href: "/leads", group: "Sales" }, { icon: "alert", label: "Lead Recovery", href: "/lead-recovery", group: "Sales" }, { icon: "calendar", label: "Site Visits", href: "/site-visits", group: "Sales" }, { icon: "clock", label: "Follow-ups", href: "/follow-ups", group: "Sales" }, { icon: "check", label: "Tasks", href: "/tasks", group: "Sales" },
    ...(user.role === "CEO" ? [{ icon: "users" as const, label: "Raw Data", href: "/raw-data", group: "Sales" as const }] : []),
    { icon: "building", label: "Inventory", href: "/inventory", group: "Operations" }, { icon: "users", label: "People", href: "/employees", group: "Operations" }, { icon: "clock", label: "My attendance", href: "/attendance", group: "Operations" },
    { icon: "alert", label: "Reminders", href: "/reminders", group: "Tools" }, ...(user.role === "CEO" ? [{ icon: "building" as const, label: "Integrations", href: "/integrations", group: "Tools" as const }] : []),
  ];
  const mobileNavigation = user.role === "EMPLOYEE" ? navigation.filter((item) => ["/", "/leads", "/follow-ups", "/tasks"].includes(item.href)) : user.role === "MANAGER" ? navigation.filter((item) => ["/", "/leads", "/employees", "/follow-ups"].includes(item.href)) : navigation.filter((item) => ["/", "/leads", "/employees", "/hr"].includes(item.href));
  const active = (item: NavItem) => item.href === "/" ? pathname === "/" : pathname === item.href || pathname?.startsWith(`${item.href}/`);
  const navClass = (item: NavItem) => `app-nav-item focus-ring flex h-[42px] items-center gap-2.5 rounded-lg px-2.5 text-[14px] font-medium transition-colors ${active(item) ? "app-nav-item--active" : ""}`;
  function globalSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = String(new FormData(event.currentTarget).get("search") || "").trim();
    router.push(query ? `/leads?search=${encodeURIComponent(query)}` : "/leads");
  }

  return <div className="app-shell">
    <aside onMouseEnter={() => setDesktopExpanded(true)} onMouseLeave={() => setDesktopExpanded(false)} className={`app-sidebar fixed inset-y-0 left-0 z-40 hidden w-[76px] flex-col border-r px-3 py-3 transition-[width,padding] duration-200 lg:flex ${desktopExpanded ? "lg:w-[248px] lg:px-3" : ""}`}>
      <div className="app-sidebar__brand flex h-11 items-center gap-2.5 px-1"><div className="app-logo-frame flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border"><BrandMark className="h-8 w-8" /></div><div className={`min-w-0 transition-all ${desktopExpanded ? "opacity-100" : "pointer-events-none w-0 -translate-x-2 overflow-hidden opacity-0"}`}><p className="app-wordmark truncate text-[14px] font-bold tracking-[.15em]">NIPRIX</p><p className="app-brand-caption mt-0.5 truncate text-[9px] font-bold tracking-[.16em]">ENTERPRISE CRM</p></div></div>
      <nav aria-label="Main navigation" className="app-sidebar__nav mt-5 min-h-0 flex-1 overflow-y-auto pr-1">{(["Workspace", "Sales", "Operations", "Tools"] as const).map((group) => <section key={group} className="app-sidebar__group mb-4"><p className={`app-nav-label mb-1.5 px-2.5 text-[9px] font-bold uppercase tracking-[.16em] ${desktopExpanded ? "" : "hidden"}`}>{group}</p><div className="space-y-0.5">{navigation.filter((item) => item.group === group).map((item) => <Link title={!desktopExpanded ? item.label : undefined} key={item.href} href={item.href} aria-current={active(item) ? "page" : undefined} className={navClass(item)}><Icon name={item.icon} className="h-[18px] w-[18px] shrink-0" /><span className={desktopExpanded ? "opacity-100" : "pointer-events-none w-0 overflow-hidden opacity-0"}>{item.label}</span></Link>)}</div></section>)}</nav>
      <div className="app-sidebar__footer mt-3 pt-3"><button title={!desktopExpanded ? "Sign out" : undefined} onClick={onLogout} className="app-sidebar__signout app-nav-item focus-ring flex h-[42px] w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-semibold transition-colors"><Icon name="logout" className="h-[18px] w-[18px] shrink-0" /><span className={desktopExpanded ? "opacity-100" : "w-0 overflow-hidden opacity-0"}>Sign out</span></button></div>
    </aside>
    <div className={`transition-[padding] duration-200 ${desktopExpanded ? "lg:pl-[248px]" : "lg:pl-[76px]"}`}>
      <header className="app-header sticky top-0 z-20 flex h-14 items-center justify-between border-b px-3 backdrop-blur lg:hidden"><div className="flex min-w-0 items-center gap-2"><div className="app-logo-frame flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border"><BrandMark className="h-8 w-8" /></div><div><p className="page-kicker text-[10px] font-semibold uppercase tracking-[.12em]">NIPRIX</p><p className="page-title text-[15px] font-bold">{titleFor(pathname)}</p></div></div><div className="flex items-center gap-1"><ThemeToggle compact /><button aria-label="Open more navigation" onClick={() => setMoreOpen(true)} className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] text-[var(--brand-strong)]"><Icon name="menu" className="h-5 w-5" /></button></div></header>
      <header className="app-header sticky top-0 z-20 hidden h-[74px] items-center gap-6 border-b px-7 backdrop-blur-xl lg:flex"><div className="min-w-[190px]"><p className="page-kicker text-[11px] font-bold uppercase tracking-[.13em]">{roleLabels[user.role]}</p><p className="page-title mt-0.5 text-[15px] font-bold">{titleFor(pathname)}</p></div><form onSubmit={globalSearch} className="relative mx-auto w-full max-w-[480px]"><Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-soft)]" /><input name="search" type="search" placeholder="Search leads, phone or email…" className="app-search focus-ring h-10 w-full rounded-xl border py-2 pl-10 pr-4 text-sm" /></form><div className="ml-auto flex items-center gap-2"><button onClick={() => router.push("/leads?create=1")} className="brand-button focus-ring inline-flex h-10 items-center gap-1.5 rounded-xl px-3.5 text-sm font-bold text-white"><Icon name="plus" className="h-4 w-4" />New lead</button><ThemeToggle /><NotificationCenter /><div className="relative"><button onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen} aria-haspopup="menu" className="app-profile focus-ring flex h-10 items-center gap-2 rounded-xl px-1.5 transition"><span className="app-avatar flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold">{user.username.slice(0, 1).toUpperCase()}</span><Icon name="chevron" className="h-3.5 w-3.5 rotate-90" /></button>{profileOpen && <div role="menu" className="app-popover absolute right-0 top-[calc(100%+10px)] z-50 w-52 rounded-2xl border p-2"><p className="border-b border-[var(--line)] px-3 py-2 text-sm font-bold">{user.username}</p><button role="menuitem" onClick={onLogout} className="app-nav-item focus-ring mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold"><Icon name="logout" className="h-4 w-4" />Sign out</button></div>}</div></div></header>
      <main className="page-enter mx-auto w-full max-w-[1600px] p-3 pb-28 sm:p-6 lg:p-7 lg:pb-7">{children}</main>
    </div>
    <nav aria-label="Mobile primary navigation" className="app-mobile-nav mobile-bottom-nav fixed inset-x-0 bottom-0 z-30 flex h-[76px] items-start justify-around border-t px-1 pt-2 backdrop-blur lg:hidden">{mobileNavigation.map((item) => <Link key={item.href} href={item.href} aria-current={active(item) ? "page" : undefined} className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold ${active(item) ? "text-[var(--brand-strong)]" : "text-[var(--ink-soft)]"}`}><span className={`flex h-8 w-11 items-center justify-center rounded-xl ${active(item) ? "bg-[var(--brand-soft)]" : ""}`}><Icon name={item.icon} className="h-5 w-5" /></span><span className="truncate">{item.label}</span></Link>)}<button aria-label="Open more navigation" onClick={() => setMoreOpen(true)} className="focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold text-[var(--ink-soft)]"><span className="flex h-8 w-11 items-center justify-center rounded-xl"><Icon name="more" className="h-5 w-5" /></span><span>More</span></button></nav>
    {moreOpen && <div role="dialog" aria-modal="true" aria-label="More navigation" className="fixed inset-0 z-50 lg:hidden"><button aria-label="Close more navigation" onClick={() => setMoreOpen(false)} className="mobile-sheet-backdrop absolute inset-0 w-full" /><section className="app-sheet mobile-sheet absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-[28px] p-5 shadow-2xl"><div className="mx-auto h-1 w-10 rounded-full bg-[var(--line)]" /><div className="mt-4 flex items-center justify-between"><div><h2 className="page-title text-lg font-bold">More</h2><p className="page-copy text-xs">{user.username} · {roleLabels[user.role]}</p></div><button onClick={() => setMoreOpen(false)} className="focus-ring rounded-xl p-2 text-[var(--ink-soft)]"><Icon name="close" className="h-5 w-5" /></button></div><div className="mt-5 space-y-5">{(["Workspace", "Sales", "Operations", "Tools"] as const).map((group) => <section key={group}><p className="app-nav-label mb-2 text-[10px] font-bold uppercase tracking-[.14em]">{group}</p><div className="grid grid-cols-2 gap-2">{navigation.filter((item) => item.group === group).map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={`focus-ring flex min-h-12 items-center gap-2 rounded-xl border border-[var(--line)] px-3 text-sm font-semibold ${active(item) ? "bg-[var(--brand-soft)] text-[var(--brand-strong)]" : "text-[var(--ink)]"}`}><Icon name={item.icon} className="h-4 w-4" />{item.label}</Link>)}</div></section>)}<button onClick={onLogout} className="focus-ring flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#fff4f4] text-sm font-bold text-[var(--danger)]"><Icon name="logout" className="h-4 w-4" />Sign out</button></div></section></div>}
  </div>;
}
