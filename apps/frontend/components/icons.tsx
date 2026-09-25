type IconName = "home" | "clock" | "users" | "chart" | "calendar" | "logout" | "menu" | "close" | "check" | "arrow" | "shield" | "alert" | "refresh" | "edit" | "building" | "sparkle" | "chevron";

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<IconName, React.ReactNode> = {
    home: <><path {...common} d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1Z" /></>,
    clock: <><circle {...common} cx="12" cy="12" r="9" /><path {...common} d="M12 7v5l3.5 2" /></>,
    users: <><path {...common} d="M16 20v-1.5a4.5 4.5 0 0 0-4.5-4.5h-4A4.5 4.5 0 0 0 3 18.5V20" /><circle {...common} cx="9.5" cy="7" r="3.5" /><path {...common} d="M17 11a3 3 0 1 0-1.7-5.5M21 20v-1.5a4.5 4.5 0 0 0-2.5-4" /></>,
    chart: <><path {...common} d="M4 19V5M4 19h16" /><path {...common} d="m7 15 4-4 3 2 5-6" /></>,
    calendar: <><rect {...common} x="3" y="5" width="18" height="16" rx="2" /><path {...common} d="M7 3v4M17 3v4M3 10h18" /></>,
    logout: <><path {...common} d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5" /><path {...common} d="m14 16 4-4-4-4M18 12H9" /></>,
    menu: <><path {...common} d="M4 7h16M4 12h16M4 17h16" /></>,
    close: <><path {...common} d="m6 6 12 12M18 6 6 18" /></>,
    check: <><path {...common} d="m5 12 4.2 4.2L19 6.5" /></>,
    arrow: <><path {...common} d="M5 12h13M13 6l6 6-6 6" /></>,
    shield: <><path {...common} d="M12 3 19 6v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6Z" /><path {...common} d="m9 12 2 2 4-4" /></>,
    alert: <><path {...common} d="M10.2 4.3 2.8 18a2 2 0 0 0 1.8 3h14.8a2 2 0 0 0 1.8-3L13.8 4.3a2 2 0 0 0-3.6 0Z" /><path {...common} d="M12 9v4M12 17h.01" /></>,
    refresh: <><path {...common} d="M20 11a8.1 8.1 0 0 0-15-3L3 10M4 5v5h5M4 13a8.1 8.1 0 0 0 15 3l2-2M20 19v-5h-5" /></>,
    edit: <><path {...common} d="M12 20h8" /><path {...common} d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    building: <><path {...common} d="M4 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17M2 21h20M8 7h4M8 11h4M8 15h4M17 8h3M17 12h3M17 16h3" /></>,
    sparkle: <><path {...common} d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7ZM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7Z" /></>,
    chevron: <><path {...common} d="m9 18 6-6-6-6" /></>,
  };
  return <svg aria-hidden="true" className={className} viewBox="0 0 24 24">{paths[name]}</svg>;
}
