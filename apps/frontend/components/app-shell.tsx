"use client";

import Link from "next/link";
import { FormEvent, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand";
import { Icon } from "@/components/icons";
import { NotificationCenter } from "@/components/notification-center";
import type { Role, User } from "@/lib/types";

const roleLabels: Record<Role, string> = { CEO: "CEO / Administrator", MANAGER: "Team manager", EMPLOYEE: "Employee workspace" };
type NavItem = { icon: "home" | "chart" | "users" | "building" | "clock" | "check" | "alert"; label: string; href: string; group: "Workspace" | "Sales" | "Operations" | "Tools" };

function titleFor(pathname: string | null) {
  if (pathname === "/inventory") return "Inventory";
  if (pathname === "/raw-data") return "Raw Data";
  if (pathname?.startsWith("/hr")) return "HR Command Center";
  if (pathname?.startsWith("/leave-") || pathname === "/holidays" || pathname === "/employee-documents") return "HR management";
  if (pathname === "/attendance") return "Attendance";
  if (pathname?.startsWith("/leads")) return "Leads";
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
    { icon: "users", label: "Leads", href: "/leads", group: "Sales" }, { icon: "clock", label: "Follow-ups", href: "/follow-ups", group: "Sales" }, { icon: "check", label: "Tasks", href: "/tasks", group: "Sales" },
    ...(user.role === "CEO" ? [{ icon: "users" as const, label: "Raw Data", href: "/raw-data", group: "Sales" as const }] : []),
    { icon: "building", label: "Inventory", href: "/inventory", group: "Operations" }, { icon: "users", label: "People", href: "/employees", group: "Operations" }, { icon: "clock", label: "My attendance", href: "/attendance", group: "Operations" },
    { icon: "alert", label: "Reminders", href: "/reminders", group: "Tools" }, ...(user.role === "CEO" ? [{ icon: "building" as const, label: "Integrations", href: "/integrations", group: "Tools" as const }] : []),
  ];
  const mobileNavigation = user.role === "EMPLOYEE" ? navigation.filter((item) => ["/", "/leads", "/follow-ups", "/tasks"].includes(item.href)) : user.role === "MANAGER" ? navigation.filter((item) => ["/", "/leads", "/employees", "/follow-ups"].includes(item.href)) : navigation.filter((item) => ["/", "/leads", "/employees", "/hr"].includes(item.href));
  const active = (item: NavItem) => item.href === "/" ? pathname === "/" : pathname === item.href || pathname?.startsWith(`${item.href}/`);
  function globalSearch(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const query = String(new FormData(event.currentTarget).get("search") || "").trim(); router.push(query ? `/leads?search=${encodeURIComponent(query)}` : "/leads"); }

  return <div className="min-h-screen bg-[#f5f8fc] text-[#10233f]">
    <aside onMouseEnter={() => setDesktopExpanded(true)} onMouseLeave={() => setDesktopExpanded(false)} className={`fixed inset-y-0 left-0 z-40 hidden w-[76px] flex-col border-r border-[#e4eaf2] bg-white px-3 py-4 shadow-[12px_0_36px_rgba(20,43,75,.025)] transition-[width,padding] duration-200 lg:flex ${desktopExpanded ? "lg:w-[248px] lg:px-4" : ""}`}>
      <div className="flex h-12 items-center gap-3 px-1"><div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#e3e9f1] bg-white shadow-sm"><BrandMark className="h-9 w-9" /></div><div className={`min-w-0 transition-all ${desktopExpanded ? "opacity-100" : "pointer-events-none w-0 -translate-x-2 overflow-hidden opacity-0"}`}><p className="truncate text-[15px] font-bold tracking-[.15em]">NIPRIX</p><p className="mt-0.5 truncate text-[9px] font-bold tracking-[.16em] text-[#7d8da3]">ENTERPRISE CRM</p></div></div>
      <nav aria-label="Main navigation" className="mt-8 min-h-0 flex-1 overflow-y-auto">{(["Workspace", "Sales", "Operations", "Tools"] as const).map((group) => <section key={group} className="mb-5"><p className={`mb-2 px-3 text-[10px] font-bold uppercase tracking-[.14em] text-[#98a6b7] ${desktopExpanded ? "" : "hidden"}`}>{group}</p><div className="space-y-1">{navigation.filter((item) => item.group === group).map((item) => <Link title={!desktopExpanded ? item.label : undefined} key={item.href} href={item.href} aria-current={active(item) ? "page" : undefined} className={`focus-ring flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold ${active(item) ? "bg-[#e8f3ff] text-[#0869d8] shadow-[inset_3px_0_0_#0869d8]" : "text-[#60708a] hover:bg-[#f5f8fc]"}`}><Icon name={item.icon} className="h-[19px] w-[19px] shrink-0" /><span className={`${desktopExpanded ? "opacity-100" : "pointer-events-none w-0 overflow-hidden opacity-0"}`}>{item.label}</span></Link>)}</div></section>)}</nav>
      <button title={!desktopExpanded ? "Sign out" : undefined} onClick={onLogout} className="focus-ring flex h-11 items-center gap-3 rounded-xl px-3 text-xs font-bold text-[#60708a] hover:bg-[#f5f8fc]"><Icon name="logout" className="h-4 w-4 shrink-0" /><span className={desktopExpanded ? "opacity-100" : "w-0 overflow-hidden opacity-0"}>Sign out</span></button>
    </aside>
    <div className={`transition-[padding] duration-200 ${desktopExpanded ? "lg:pl-[248px]" : "lg:pl-[76px]"}`}>
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[#e4eaf2] bg-white/90 px-3 backdrop-blur lg:hidden"><div className="flex min-w-0 items-center gap-2"><div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#e3e9f1] bg-white"><BrandMark className="h-8 w-8" /></div><div><p className="text-[10px] font-semibold uppercase tracking-[.12em] text-[#75869b]">NIPRIX</p><p className="text-[15px] font-bold text-[#203756]">{titleFor(pathname)}</p></div></div><button aria-label="Open more navigation" onClick={() => setMoreOpen(true)} className="focus-ring flex h-10 w-10 items-center justify-center rounded-xl border border-[#e2eaf4]"><Icon name="menu" className="h-5 w-5" /></button></header>
      <header className="sticky top-0 z-20 hidden h-[74px] items-center gap-6 border-b border-[#e4eaf2] bg-white/82 px-7 backdrop-blur-xl lg:flex"><div className="min-w-[190px]"><p className="text-[11px] font-bold uppercase tracking-[.13em] text-[#7b8ba1]">{roleLabels[user.role]}</p><p className="mt-0.5 text-[15px] font-bold text-[#253a59]">{titleFor(pathname)}</p></div><form onSubmit={globalSearch} className="relative mx-auto w-full max-w-[480px]"><Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8291a4]" /><input name="search" type="search" placeholder="Search leads, phone or email…" className="focus-ring h-10 w-full rounded-xl border border-[#e1e8f0] bg-[#f8fafc] py-2 pl-10 pr-4 text-sm" /></form><div className="ml-auto flex items-center gap-2"><button onClick={() => router.push("/leads?create=1")} className="focus-ring inline-flex h-10 items-center gap-1.5 rounded-xl bg-[#0869d8] px-3.5 text-sm font-bold text-white"><Icon name="plus" className="h-4 w-4" />New lead</button><NotificationCenter /><div className="relative"><button onClick={() => setProfileOpen((value) => !value)} className="focus-ring flex h-10 items-center gap-2 rounded-xl px-1.5 hover:bg-[#f5f8fc]"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#10233f] text-xs font-bold text-white">{user.username.slice(0, 1).toUpperCase()}</span><Icon name="chevron" className="h-3.5 w-3.5 rotate-90" /></button>{profileOpen && <div role="menu" className="absolute right-0 top-[calc(100%+10px)] z-50 w-52 rounded-2xl border border-[#e1e9f2] bg-white p-2 shadow-xl"><p className="border-b border-[#edf1f6] px-3 py-2 text-sm font-bold">{user.username}</p><button role="menuitem" onClick={onLogout} className="focus-ring mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#60708a] hover:bg-[#f5f8fc]"><Icon name="logout" className="h-4 w-4" />Sign out</button></div>}</div></div></header>
      <main className="mx-auto w-full max-w-[1600px] p-3 pb-28 sm:p-6 lg:p-7 lg:pb-7">{children}</main>
    </div>
    <nav aria-label="Mobile primary navigation" className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-30 flex h-[76px] items-start justify-around border-t border-[#e1e8f0] bg-white/95 px-1 pt-2 shadow-[0_-8px_28px_rgba(16,35,63,.08)] backdrop-blur lg:hidden">{mobileNavigation.map((item) => <Link key={item.href} href={item.href} aria-current={active(item) ? "page" : undefined} className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold ${active(item) ? "text-[#0869d8]" : "text-[#718198]"}`}><span className={`flex h-8 w-11 items-center justify-center rounded-xl ${active(item) ? "bg-[#e8f3ff]" : ""}`}><Icon name={item.icon} className="h-5 w-5" /></span><span className="truncate">{item.label}</span></Link>)}<button aria-label="Open more navigation" onClick={() => setMoreOpen(true)} className="focus-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl py-1 text-[10px] font-semibold text-[#718198]"><span className="flex h-8 w-11 items-center justify-center rounded-xl"><Icon name="more" className="h-5 w-5" /></span><span>More</span></button></nav>
    {moreOpen && <div role="dialog" aria-modal="true" aria-label="More navigation" className="fixed inset-0 z-50 lg:hidden"><button aria-label="Close more navigation" onClick={() => setMoreOpen(false)} className="mobile-sheet-backdrop absolute inset-0 w-full" /><section className="mobile-sheet absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-[28px] bg-white p-5 shadow-2xl"><div className="mx-auto h-1 w-10 rounded-full bg-[#d8e1ec]" /><div className="mt-4 flex items-center justify-between"><div><h2 className="text-lg font-bold">More</h2><p className="text-xs text-[#718198]">{user.username} · {roleLabels[user.role]}</p></div><button onClick={() => setMoreOpen(false)} className="focus-ring rounded-xl p-2 text-[#60708a]"><Icon name="close" className="h-5 w-5" /></button></div><div className="mt-5 space-y-5">{(["Workspace", "Sales", "Operations", "Tools"] as const).map((group) => <section key={group}><p className="mb-2 text-[10px] font-bold uppercase tracking-[.14em] text-[#98a6b7]">{group}</p><div className="grid grid-cols-2 gap-2">{navigation.filter((item) => item.group === group).map((item) => <Link key={item.href} href={item.href} onClick={() => setMoreOpen(false)} className={`focus-ring flex min-h-12 items-center gap-2 rounded-xl border px-3 text-sm font-semibold ${active(item) ? "border-[#b9dcff] bg-[#eef7ff] text-[#0869d8]" : "border-[#e5ebf3] text-[#405773]"}`}><Icon name={item.icon} className="h-4 w-4" />{item.label}</Link>)}</div></section>)}<button onClick={onLogout} className="focus-ring flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#fff4f4] text-sm font-bold text-[#b12938]"><Icon name="logout" className="h-4 w-4" />Sign out</button></div></section></div>}
  </div>;
}
