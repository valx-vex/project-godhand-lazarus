export function MetricBand({
  label,
  value,
  note,
  accent = "teal",
}: {
  label: string
  value: string
  note: string
  accent?: "teal" | "stone"
}) {
  return (
    <div className="metric-strip">
      <p className="eyebrow">{label}</p>
      <div className={`mt-4 text-4xl font-semibold ${accent === "teal" ? "text-teal-300" : "text-stoneglass"}`}>
        {value}
      </div>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{note}</p>
    </div>
  )
}
