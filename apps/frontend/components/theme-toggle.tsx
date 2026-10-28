
"use client";

import { useTheme } from "@/components/theme-provider";
import { useEffect, useRef } from "react";
import gsap from "gsap";

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3.7" />
      <path d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.72 5.28l-1.41 1.41M6.69 17.31l-1.41 1.41M18.72 18.72l-1.41-1.41M6.69 6.69 5.28 5.28" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M20.315.4A8.8 8.8 0 0 1 8.6 3.7a8.8 8.8 0 1 0 11.7 11.7Z" />
    </svg>
  );
}

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const night = theme === "night";
  const buttonRef = useRef<HTMLButtonElement>(null);
  const knobRef = useRef<HTMLSpanElement>(null);
  const phaseRef = useRef<SVGPathElement>(null);
  const busyRef = useRef(false);

  useEffect(() => {
    const button = buttonRef.current;
    const knob = knobRef.current;
    const phase = phaseRef.current;

    if (!button || !knob || !phase) return;

    const updateKnob = () => {
      gsap.set(knob, { x: night ? 26 : 0, rotation: night ? 7 : -4 });
    };

    updateKnob();

    return () => {
      gsap.killTweensOf(knob);
      gsap.killTweensOf(phase);
    };
  }, [night]);

  function handleToggle() {
    if (busyRef.current) return;

    const button = buttonRef.current;
    const knob = knobRef.current;
    const phase = phaseRef.current;

    if (!button || !knob || !phase) {
      toggleTheme();
      return;
    }

    const nextNight = !night;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (reducedMotion) {
      toggleTheme();
      return;
    }

    busyRef.current = true;

    const rect = button.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    const reveal = document.createElement("div");
reveal.className = "theme-reveal";
reveal.dataset.target = nextNight ? "night" : "day";

const rootStyles = getComputedStyle(document.documentElement);
const currentCanvas = rootStyles.getPropertyValue("--canvas").trim();
const nextCanvas = nextNight ? "#000000" : "#ffffff";

reveal.style.setProperty("--reveal-x", `${x}px`);
reveal.style.setProperty("--reveal-y", `${y}px`);
reveal.style.backgroundColor = nextCanvas;
reveal.style.setProperty("--reveal-current", currentCanvas || "transparent");

document.body.appendChild(reveal);

    const startX = nextNight ? 0 : 26;
    const endX = nextNight ? 26 : 0;

    const state = { progress: 0 };

    const radius = 19;
    const darkPhase = 0.16;

    const drawMoon = (fraction: number) => {
      const f = Math.max(0.001, Math.min(1, fraction));
      const k = Math.abs(2 * f - 1) * radius;
      const sweepFlag = f >= 0.5 ? 1 : 0;
      phase.setAttribute(
        "d",
        `M0 ${-radius} A${radius} ${radius} 0 0 1 0 ${radius} A${k.toFixed(3)} ${radius} 0 0 ${sweepFlag} 0 ${-radius}Z`
      );
    };

    gsap.set(knob, { x: startX });
    drawMoon(nextNight ? 1 : darkPhase);

    gsap.timeline({
      onUpdate: () => {
        drawMoon(
          nextNight
            ? 1 - state.progress * (1 - darkPhase)
            : darkPhase + state.progress * (1 - darkPhase)
        );
      },
      onComplete: () => {
        toggleTheme();
        
        gsap.set(knob, { x: endX });
        reveal.remove();
        busyRef.current = false;
      },
    })
      .to(knob, {
        x: endX,
        rotation: nextNight ? 7 : -4,
        duration: 0.72,
        ease: "back.out(1.3)",
      }, 0)
      .to(state, {
        progress: 1,
        duration: 0.72,
        ease: "power2.inOut",
      }, 0)
      .fromTo(
        reveal,
        { clipPath: `ellipse(0px 0px at ${x}px ${y}px)` },
        {
          clipPath: `ellipse(160vmax 160vmax at ${x}px ${y}px)`,
          duration: 0.95,
          ease: "power3.in",
        },
        0.04
      );
  }

  return (
    <button
      ref={buttonRef}
      type="button"
      role="switch"
      aria-checked={night}
      aria-label={`${night ? "Night" : "Day"} mode enabled. Switch to ${night ? "day" : "night"} mode`}
      title={`Switch to ${night ? "day" : "night"} mode`}
      onClick={handleToggle}
      className={`theme-toggle focus-ring ${compact ? "theme-toggle--compact" : ""}`}
    >
      <span className="theme-toggle__scene">
        <span className="theme-toggle__icon theme-toggle__sun">
          <SunIcon />
        </span>
        <span className="theme-toggle__icon theme-toggle__moon">
          <MoonIcon />
        </span>
        <span ref={knobRef} className="theme-toggle__thumb">
          <svg
            viewBox="-20 -20 40 40"
            aria-hidden="true"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              overflow: "visible",
            }}
          >
            <path
              ref={phaseRef}
              fill="currentColor"
              d="M0 -19 A19 19 0 0 1 0 19 A19 19 0 0 1 0 -19Z"
            />
          </svg>
          <span className="theme-toggle__thumb-glint" />
        </span>
      </span>
      {!compact && (
        <span className="theme-toggle__label">{night ? "Night" : "Day"}</span>
      )}
    </button>
  );
}
