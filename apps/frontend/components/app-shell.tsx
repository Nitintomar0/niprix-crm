"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { BrandMark } from "@/components/brand";
import { Icon } from "@/components/icons";
import type { Role, User } from "@/lib/types";

const labels: Record<Role, string> = { CEO: "CEO / Administrator", MANAGER: "Team manager", EMPLOYEE: "Employee workspace" };


export function AppShell({ user, children, onLogout }: { user: User; children: React.ReactNode; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const navigation = [
  { icon: "home" as const, label: "Overview", href: "/" },
  ...(user.role !== "EMPLOYEE"
    ? [
        {
          icon: "chart" as const,
          label: "HR Dashboard",
          href: "/hr",
        },
      ]
    : []),
  { icon: "users" as const, label: "Leads", href: "/leads" },
  ...(user.role === "CEO" ? [{ icon: "users" as const, label: "Raw Data", href: "/raw-data" }] : []),
  { icon: "building" as const, label: "Inventory", href: "/inventory" },
  { icon: "users" as const, label: "People", href: "/employees" },
  { icon: "clock" as const, label: "My attendance", href: "/attendance" },
  { icon: "users" as const, label: "Follow-ups", href: "/follow-ups" },
  { icon: "check" as const, label: "Tasks", href: "/tasks" },
  { icon: "alert" as const, label: "Reminders", href: "/reminders" },
  ...(user.role === "CEO"
    ? [
        {
          icon: "building" as const,
          label: "Integrations",
          href: "/integrations",
        },
      ]
    : []),
];
  const pageTitle = pathname === "/inventory" ? "Inventory" : pathname === "/raw-data" ? "Raw Data" : pathname?.startsWith("/hr") ? "HR dashboard" : pathname?.startsWith("/leave-") || pathname === "/holidays" || pathname === "/employee-documents" ? "HR management" : pathname === "/attendance" ? "Attendance" : pathname?.startsWith("/leads") ? "Leads" : pathname === "/follow-ups" ? "Follow-ups" : pathname === "/tasks" ? "Tasks" : pathname === "/reminders" ? "Reminders" : pathname?.startsWith("/employees") ? "People" : "Home";
  const isNested = Boolean(pathname?.match(/^\/(leads|employees)\/\d+/));
  const mobileNavigation = user.role === "EMPLOYEE"
    ? [
        { icon: "home" as const, label: "Home", href: "/" },
        { icon: "users" as const, label: "Leads", href: "/leads" },
        { icon: "clock" as const, label: "Follow-ups", href: "/follow-ups" },
        { icon: "check" as const, label: "Tasks", href: "/tasks" },
      ]
    : user.role === "MANAGER"
      ? [
          { icon: "home" as const, label: "Home", href: "/" },
          { icon: "users" as const, label: "Leads", href: "/leads" },
          { icon: "users" as const, label: "Team", href: "/employees" },
          { icon: "clock" as const, label: "Follow-ups", href: "/follow-ups" },
        ]
      : [
          { icon: "home" as const, label: "Home", href: "/" },
          { icon: "users" as const, label: "Leads", href: "/leads" },
          { icon: "users" as const, label: "People", href: "/employees" },
          { icon: "chart" as const, label: "Reports", href: "/hr" },
        ];
  return (
    <div className="min-h-screen bg-[#f5f8fc] text-[#10233f]">
      {open && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-[#10233f]/35 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col border-r border-[#e4eaf2] bg-white px-4 py-5 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-3 px-2"><div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl border border-[#e3e9f1] bg-white"><BrandMark className="h-10 w-10" /></div><div><p className="text-[17px] font-bold tracking-[.12em] text-[#10233f]">NIPRIX</p><p className="text-[10px] font-medium tracking-[.16em] text-[#7d8da3]">ENTERPRISE CRM</p></div><button aria-label="Close navigation" onClick={() => setOpen(false)} className="focus-ring ml-auto rounded-lg p-2 text-[#60708a] lg:hidden"><Icon name="close" className="h-5 w-5" /></button></div>
        <div className="mt-10"><p className="px-3 text-[10px] font-bold tracking-[.15em] text-[#99a6b7]">WORKSPACE</p><nav aria-label="Main navigation" className="mt-3 space-y-1">{navigation.map((item) => { const active = pathname === item.href; return <Link key={item.label} href={item.href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined} className={`focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${active ? "bg-[#eaf4ff] text-[#0869d8]" : "text-[#60708a] hover:bg-[#f5f8fc] hover:text-[#10233f]"}`}><Icon name={item.icon} className="h-[19px] w-[19px]" />{item.label}</Link>; })}</nav></div>
        <div className="mt-8"><p className="px-3 text-[10px] font-bold tracking-[.15em] text-[#99a6b7]">COMING NEXT</p><div className="mt-3 space-y-1 text-sm text-[#98a5b5]"><p className="flex items-center gap-3 px-3 py-2.5"><Icon name="users" className="h-[18px] w-[18px]" />People & teams</p><p className="flex items-center gap-3 px-3 py-2.5"><Icon name="chart" className="h-[18px] w-[18px]" />Insights & reports</p></div></div>
        <div className="mt-auto rounded-2xl border border-[#e2eaf4] bg-[#f8fbff] p-3"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#dceeff] text-sm font-bold text-[#0869d8]">{user.username.slice(0, 1).toUpperCase()}</div><div className="min-w-0"><p className="truncate text-sm font-semibold text-[#253a59]">{user.username}</p><p className="truncate text-xs text-[#718198]">{labels[user.role]}</p></div></div><button onClick={onLogout} className="focus-ring mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-[#60708a] transition hover:bg-white hover:text-[#10233f]"><Icon name="logout" className="h-4 w-4" />Sign out</button></div>
      </aside>
      <div className="lg:pl-[272px]">
        <header className="mobile-header sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[#e4eaf2] bg-white/90 px-3 backdrop-blur lg:hidden">
          <div className="flex min-w-0 items-center gap-2">
            {isNested ? <button aria-label="Go back" onClick={() => router.back()} className="focus-ring -ml-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[#203756]"><Icon name="back" className="h-5 w-5" /></button> : <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#e3e9f1] bg-white"><BrandMark className="h-8 w-8" /></div>}
            <div className="min-w-0"><p className="truncate text-[10px] font-semibold uppercase tracking-[.12em] text-[#75869b]">NIPRIX</p><p className="truncate text-[15px] font-bold text-[#203756]">{pageTitle}</p></div>
          </div>
          <button aria-label="Open more navigation" onClick={() => setOpen(true)} className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl border border-[#e2eaf4] text-[#405773]"><Icon name="menu" className="h-5 w-5" /></button>
        </header>
        <header className="sticky top-0 z-20 hidden h-[73px] items-center justify-between border-b border-[#e4eaf2] bg-white/90 px-7 backdrop-blur lg:flex"><div><p className="text-xs font-medium text-[#7b8ba1]">{labels[user.role]}</p><p className="text-sm font-semibold text-[#253a59]">{pageTitle}</p></div><div className="flex items-center gap-3"><span className="h-2 w-2 rounded-full bg-[#24a47f]" /><span className="text-xs font-medium text-[#60708a]">Secure session</span><div className="ml-1 flex h-9 w-9 items-center justify-center rounded-full bg-[#10233f] text-sm font-semibold text-white">{user.username.slice(0, 1).toUpperCase()}</div></div></header>
        <main className="mx-auto w-full max-w-[1480px] p-3 pb-28 sm:p-7 lg:pb-7">{children}</main>
      </div>
      <nav aria-label="Mobile primary navigation" className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-30 flex h-[76px] items-start justify-around border-t border-[#e1e8f0] bg-white/95 px-1 pt-2 shadow-[0_-8px_28px_rgba(16,35,63,.08)] backdrop-blur lg:hidden">
        {mobileNavigation.map((item) => { const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname?.startsWith(`${item.href}/`); return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold transition ${active ? "text-[#0869d8]" : "text-[#718198]"}`}><span className={`flex h-8 w-11 items-center justify-center rounded-xl transition ${active ? "bg-[#e8f3ff]" : ""}`}><Icon name={item.icon} className="h-5 w-5" /></span><span className="truncate">{item.label}</span></Link>; })}
        <button aria-label="Open more navigation" onClick={() => setOpen(true)} className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold transition ${!mobileNavigation.some((item) => pathname === item.href || pathname?.startsWith(`${item.href}/`)) ? "text-[#0869d8]" : "text-[#718198]"}`}><span className="flex h-8 w-11 items-center justify-center rounded-xl"><Icon name="more" className="h-5 w-5" /></span><span>More</span></button>
      </nav>
    </div>
  );
}
