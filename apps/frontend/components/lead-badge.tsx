function label(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function tone(value: string) {
  const tones: Record<string, string> = {
    // Lead statuses — each has its own distinct color
    NEW: "border-blue-200 bg-blue-50 text-blue-800",
    CONTACTED: "border-sky-200 bg-sky-50 text-sky-800",
    SITE_VISIT_REQUESTED:
      "border-violet-200 bg-violet-50 text-violet-800",
    SITE_VISIT_DONE:
      "border-teal-200 bg-teal-50 text-teal-800",
    POSTPONED:
      "border-orange-200 bg-orange-50 text-orange-800",
    DIFFERENT_REQUIREMENT:
      "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-800",
    NOT_INTERESTED:
      "border-rose-200 bg-rose-50 text-rose-800",
    CLOSED:
      "border-emerald-200 bg-emerald-50 text-emerald-800",
    INVALID_PHONE:
      "border-red-200 bg-red-50 text-red-800",
    NOT_LOOKING_PROPERTY:
      "border-indigo-200 bg-indigo-50 text-indigo-800",
    USER_IS_AGENT:
      "border-pink-200 bg-pink-50 text-pink-800",

    // Preserve existing follow-up status styling
    FOLLOW_UP_NEEDED:
      "border-violet-200 bg-violet-50 text-violet-700",
    FOLLOW_UP_DONE:
      "border-violet-200 bg-violet-50 text-violet-700",

    // Preserve other existing badge categories
    HOT: "border-rose-200 bg-rose-50 text-rose-700",
    WARM: "border-amber-200 bg-amber-50 text-amber-800",
    COLD: "border-slate-200 bg-slate-100 text-slate-700",
    NOT_PICK_CALL: "border-blue-200 bg-blue-50 text-blue-800",
  };

  if (tones[value]) return tones[value];

  // Keep the existing SITE matching behavior for other values.
  if (value.includes("SITE")) {
    return "border-cyan-200 bg-cyan-50 text-cyan-800";
  }

  return "border-blue-200 bg-[#eef6ff] text-[#0869d8]";
}


export function LeadBadge({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-[11px] font-bold leading-none tracking-[.01em] ${tone(value)} ${className}`}>
      <span className="truncate">{label(value)}</span>
    </span>
  );
}

