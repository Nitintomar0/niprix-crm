function label(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function tone(value: string) {
  if (value === "HOT") return "border-rose-200 bg-rose-50 text-rose-700";
  if (value === "WARM") return "border-amber-200 bg-amber-50 text-amber-800";
  if (value === "COLD") return "border-slate-200 bg-slate-100 text-slate-700";
  if (value === "NOT_INTERESTED" || value === "INVALID_PHONE") return "border-slate-200 bg-slate-100 text-slate-700";
  if (value === "NOT_PICK_CALL") return "border-blue-200 bg-blue-50 text-blue-800";
  if (value.includes("FOLLOW")) return "border-violet-200 bg-violet-50 text-violet-700";
  if (value.includes("SITE")) return "border-cyan-200 bg-cyan-50 text-cyan-800";
  if (value === "CLOSED") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  return "border-blue-200 bg-[#eef6ff] text-[#0869d8]";
}

export function LeadBadge({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-[11px] font-bold leading-none tracking-[.01em] ${tone(value)} ${className}`}>
      <span className="truncate">{label(value)}</span>
    </span>
  );
}

