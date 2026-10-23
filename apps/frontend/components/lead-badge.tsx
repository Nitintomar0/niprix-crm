function label(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function tone(value: string) {
  const tones: Record<string, "success" | "warning" | "danger" | "info" | "purple" | "neutral"> = {
    NEW: "info", CONTACTED: "info", SITE_VISIT_REQUESTED: "purple", SITE_VISIT_DONE: "success",
    POSTPONED: "warning", DIFFERENT_REQUIREMENT: "purple", NOT_INTERESTED: "danger", CLOSED: "success",
    INVALID_PHONE: "danger", NOT_LOOKING_PROPERTY: "neutral", USER_IS_AGENT: "danger", FOLLOW_UP_NEEDED: "purple",
    FOLLOW_UP_DONE: "purple", HOT: "danger", WARM: "warning", COLD: "neutral", NOT_PICK_CALL: "info",
  };
  return tones[value] || (value.includes("SITE") ? "purple" : "info");
}


export function LeadBadge({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span className={`status-badge status-badge--${tone(value)} inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-[11px] font-bold leading-none tracking-[.01em] ${className}`}>
      <span className="truncate">{label(value)}</span>
    </span>
  );
}

