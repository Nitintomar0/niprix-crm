"use client";

import { useTheme } from "@/components/theme-provider";

function SunIcon() {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="3.7" /><path d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.72 5.28l-1.41 1.41M6.69 17.31l-1.41 1.41M18.72 18.72l-1.41-1.41M6.69 6.69 5.28 5.28" /></svg>;
}

function MoonIcon() {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20.3 15.4A8.8 8.8 0 0 1 8.6 3.7a8.8 8.8 0 1 0 11.7 11.7Z" /></svg>;
}

/** A lightweight physical-style switch, deliberately CSS driven for smooth and reduced-motion-safe transitions. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const night = theme === "night";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={night}
      aria-label={`${night ? "Night" : "Day"} mode enabled. Switch to ${night ? "day" : "night"} mode`}
      title={`Switch to ${night ? "day" : "night"} mode`}
      onClick={toggleTheme}
      className={`theme-toggle focus-ring ${compact ? "theme-toggle--compact" : ""}`}
    >
      <span className="theme-toggle__scene">
        <span className="theme-toggle__icon theme-toggle__sun"><SunIcon /></span>
        <span className="theme-toggle__icon theme-toggle__moon"><MoonIcon /></span>
        <span className="theme-toggle__thumb"><span className="theme-toggle__thumb-glint" /></span>
      </span>
      {!compact && <span className="theme-toggle__label">{night ? "Night" : "Day"}</span>}
    </button>
  );
}
