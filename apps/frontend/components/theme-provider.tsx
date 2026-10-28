"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type Theme = "day" | "night";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const storageKey = "niprix-theme";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme === "night" ? "dark" : "light";
}

function initialTheme(): Theme {
  if (typeof window === "undefined") return "day";
  let saved: string | null = null;
  try {
    saved = window.localStorage.getItem(storageKey);
  } catch {
    // Storage can be unavailable in a privacy-restricted browser context.
  }
  if (saved === "day" || saved === "night") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme);
  const transitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  
const setTheme = useCallback((nextTheme: Theme) => {
  if (typeof window === "undefined" || nextTheme === theme) return;

  const root = document.documentElement;
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  if (transitionTimer.current) {
    clearTimeout(transitionTimer.current);
    transitionTimer.current = null;
  }

  root.querySelector(".theme-reveal")?.remove();
  root.classList.remove("theme-transitioning");

  if (!reducedMotion) {
    const toggle = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

    const rect = toggle?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;

    const reveal = document.createElement("div");
    reveal.className = "theme-reveal";
    reveal.dataset.target = nextTheme;
    reveal.style.setProperty("--reveal-x", `${x}px`);
    reveal.style.setProperty("--reveal-y", `${y}px`);

    root.appendChild(reveal);
    root.classList.add("theme-transitioning");
  }

  try {
    window.localStorage.setItem(storageKey, nextTheme);
  } catch {
    // The current-session theme still changes when persistence is unavailable.
  }

  applyTheme(nextTheme);
  setThemeState(nextTheme);

  if (!reducedMotion) {
    transitionTimer.current = setTimeout(() => {
      root.querySelector(".theme-reveal")?.remove();
      root.classList.remove("theme-transitioning");
      transitionTimer.current = null;
    }, 950);
  }
}, [theme]);


  const value = useMemo(() => ({
    theme,
    setTheme,
    toggleTheme: () => setTheme(theme === "night" ? "day" : "night"),
  }), [setTheme, theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider.");
  return context;
}

