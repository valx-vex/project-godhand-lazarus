import { useEffect, useState } from "react"

import { api } from "../lib/api"
import type { DashboardSummary } from "../types"
import { MetricBand } from "../components/MetricBand"


export function DashboardPage({ onOpenDrawer }: { onOpenDrawer: (drawerId: string) => void }) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    api
      .getDashboardSummary()
      .then((payload) => {
        if (!cancelled) {
          setSummary(payload)
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setError(reason.message)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <p className="support-copy">Loading layer summaries and recent vault activity…</p>
  }

  if (error || !summary) {
    return <div className="rounded-[1.5rem] border border-ember/30 bg-ember/10 px-5 py-5 text-sm">{error ?? "Dashboard unavailable."}</div>
  }

  return (
    <div className="space-y-8">
      <section className="section-frame overflow-hidden">
        <div className="grid gap-8 px-7 py-7 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-5">
            <p className="eyebrow">Memory cathedral</p>
            <h3 className="max-w-2xl text-5xl leading-[0.96] text-stone-50">
              Layer 1 navigation without pretending Layer 2 is the same thing.
            </h3>
            <p className="max-w-2xl text-base leading-7 text-[var(--muted)]">
              Browse, search, and file verbatim memories locally while keeping Lazarus visible as semantic context rather than collapsing the architecture into one blurred count.
            </p>
          </div>

          <div className="grid gap-4">
            <MetricBand
              label="Layer 1 • MemPalace"
              value={summary.layer_1.total_drawers.toLocaleString()}
              note={`${summary.layer_1.total_wings} wings • ${summary.layer_1.total_rooms} rooms`}
            />
            <MetricBand
              label="Layer 2 • Lazarus"
              value={summary.layer_2.total_vector_memories.toLocaleString()}
              note={summary.layer_2.available ? `${summary.layer_2.collections.length} tracked collections` : summary.layer_2.error ?? "Unavailable"}
              accent="stone"
            />
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="section-frame px-6 py-6">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Recent drawers</p>
              <h3 className="mt-2 text-2xl text-stone-50">Latest filings into the palace</h3>
            </div>
            <p className="text-sm text-[var(--muted)]">{summary.recent_drawers.length} shown</p>
          </div>

          <div className="mt-6 divide-y divide-white/5">
            {summary.recent_drawers.map((drawer) => (
              <button key={drawer.id} className="list-item" onClick={() => onOpenDrawer(drawer.id)} type="button">
                <div>
                  <p className="text-sm font-medium text-white">{drawer.wing} / {drawer.room}</p>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">{drawer.preview}</p>
                </div>
                <div className="min-w-0 text-right text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                  <div>{drawer.source_name || "Manual"}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="section-frame px-6 py-6">
            <p className="eyebrow">Top structure</p>
            <h3 className="mt-2 text-2xl text-stone-50">Dominant wings and rooms</h3>
            <div className="mt-6 grid gap-6 md:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">Wings</p>
                <div className="mt-4 space-y-3">
                  {summary.top_wings.map((item) => (
                    <div key={item.name} className="flex items-center justify-between border-b border-white/5 pb-3 text-sm">
                      <span>{item.name}</span>
                      <span className="text-teal-300">{item.count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">Rooms</p>
                <div className="mt-4 space-y-3">
                  {summary.top_rooms.map((item) => (
                    <div key={item.name} className="flex items-center justify-between border-b border-white/5 pb-3 text-sm">
                      <span>{item.name}</span>
                      <span className="text-teal-300">{item.count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="section-frame px-6 py-6">
            <p className="eyebrow">Graph synopsis</p>
            <h3 className="mt-2 text-2xl text-stone-50">Tunnel-bearing rooms</h3>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <MetricBand
                label="Rooms"
                value={summary.graph.total_rooms.toLocaleString()}
                note="Indexed named ideas"
              />
              <MetricBand
                label="Tunnel rooms"
                value={summary.graph.tunnel_rooms.toLocaleString()}
                note="Rooms spanning multiple wings"
              />
              <MetricBand
                label="Edges"
                value={summary.graph.total_edges.toLocaleString()}
                note="Cross-wing tunnel crossings"
                accent="stone"
              />
            </div>
            <div className="mt-6 space-y-3">
              {summary.graph.top_tunnels.slice(0, 4).map((tunnel) => (
                <div key={tunnel.room} className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-4">
                  <div className="flex items-center justify-between gap-4">
                    <p className="font-medium text-white">{tunnel.room}</p>
                    <span className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                      {tunnel.count.toLocaleString()} drawers
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{tunnel.wings.join(" • ")}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
