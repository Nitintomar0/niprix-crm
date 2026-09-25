"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BrandMark } from "@/components/brand";
import { Icon } from "@/components/icons";
import type { Role, User } from "@/lib/types";

const labels: Record<Role, string> = { CEO: "CEO / Administrator", MANAGER: "Team manager", EMPLOYEE: "Employee workspace" };

export function AppShell({ user, children, onLogout }: { user: User; children: React.ReactNode; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const navigation = [{ icon: "home" as const, label: "Overview", href: "/" }, { icon: "clock" as const, label: "My attendance", href: "/attendance" }];
  return (
    <div className="min-h-screen bg-[#f5f8fc] text-[#10233f]">
      {open && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-[#10233f]/35 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col border-r border-[#e4eaf2] bg-white px-4 py-5 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-3 px-2"><div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl border border-[#e3e9f1] bg-white"><BrandMark className="h-10 w-10" /></div><div><p className="text-[17px] font-bold tracking-[.12em] text-[#10233f]">NIPRIX</p><p className="text-[10px] font-medium tracking-[.16em] text-[#7d8da3]">ENTERPRISE CRM</p></div><button aria-label="Close navigation" onClick={() => setOpen(false)} className="focus-ring ml-auto rounded-lg p-2 text-[#60708a] lg:hidden"><Icon name="close" className="h-5 w-5" /></button></div>
        <div className="mt-10"><p className="px-3 text-[10px] font-bold tracking-[.15em] text-[#99a6b7]">WORKSPACE</p><nav aria-label="Main navigation" className="mt-3 space-y-1">{navigation.map((item) => { const active = pathname === item.href; return <Link key={item.label} href={item.href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined} className={`focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${active ? "bg-[#eaf4ff] text-[#0869d8]" : "text-[#60708a] hover:bg-[#f5f8fc] hover:text-[#10233f]"}`}><Icon name={item.icon} className="h-[19px] w-[19px]" />{item.label}</Link>; })}</nav></div>
        <div className="mt-8"><p className="px-3 text-[10px] font-bold tracking-[.15em] text-[#99a6b7]">COMING NEXT</p><div className="mt-3 space-y-1 text-sm text-[#98a5b5]"><p className="flex items-center gap-3 px-3 py-2.5"><Icon name="users" className="h-[18px] w-[18px]" />People & teams</p><p className="flex items-center gap-3 px-3 py-2.5"><Icon name="chart" className="h-[18px] w-[18px]" />Insights & reports</p></div></div>
        <div className="mt-auto rounded-2xl border border-[#e2eaf4] bg-[#f8fbff] p-3"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#dceeff] text-sm font-bold text-[#0869d8]">{user.username.slice(0, 1).toUpperCase()}</div><div className="min-w-0"><p className="truncate text-sm font-semibold text-[#253a59]">{user.username}</p><p className="truncate text-xs text-[#718198]">{labels[user.role]}</p></div></div><button onClick={onLogout} className="focus-ring mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-[#60708a] transition hover:bg-white hover:text-[#10233f]"><Icon name="logout" className="h-4 w-4" />Sign out</button></div>
      </aside>
      <div className="lg:pl-[272px]"><header className="sticky top-0 z-20 flex h-[73px] items-center justify-between border-b border-[#e4eaf2] bg-white/90 px-4 backdrop-blur sm:px-7"><div className="flex items-center gap-3"><button aria-label="Open navigation" onClick={() => setOpen(true)} className="focus-ring rounded-lg p-2 text-[#253a59] lg:hidden"><Icon name="menu" className="h-5 w-5" /></button><div><p className="text-xs font-medium text-[#7b8ba1]">{labels[user.role]}</p><p className="text-sm font-semibold text-[#253a59]">{pathname === "/attendance" ? "Attendance workspace" : "NIPRIX workspace"}</p></div></div><div className="hidden items-center gap-3 sm:flex"><span className="h-2 w-2 rounded-full bg-[#24a47f]" /><span className="text-xs font-medium text-[#60708a]">Secure session</span><div className="ml-1 flex h-9 w-9 items-center justify-center rounded-full bg-[#10233f] text-sm font-semibold text-white">{user.username.slice(0, 1).toUpperCase()}</div></div></header><main className="mx-auto w-full max-w-[1480px] p-4 sm:p-7">{children}</main></div>
    </div>
  );
}
