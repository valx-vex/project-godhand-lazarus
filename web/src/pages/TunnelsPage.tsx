import { useEffect, useState } from "react"

import { api } from "../lib/api"
import type { CountItem, TunnelsResponse } from "../types"


export function TunnelsPage() {
  const [wings, setWings] = useState<CountItem[]>([])
  const [wingA, setWingA] = useState("")
  const [wingB, setWingB] = useState("")
  const [payload, setPayload] = useState<TunnelsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getWings().then((response) => setWings(response.items)).catch((reason: Error) => setError(reason.message))
  }, [])

  useEffect(() => {
    api
      .getTunnels({ wing_a: wingA || undefined, wing_b: wingB || undefined })
      .then((response) => {
        setPayload(response)
        setError(null)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [wingA, wingB])

  return (
    <div className="space-y-6">
      <section className="section-frame px-6 py-6">
        <p className="eyebrow">Cross-wing bridges</p>
        <h3 className="mt-2 text-3xl text-stone-50">Tunnel explorer</h3>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <select className="field-shell" onChange={(event) => setWingA(event.target.value)} value={wingA}>
            <option value="">All first wings</option>
            {wings.map((wing) => (
              <option key={wing.name} value={wing.name}>
                {wing.name}
              </option>
            ))}
          </select>
          <select className="field-shell" onChange={(event) => setWingB(event.target.value)} value={wingB}>
            <option value="">All second wings</option>
            {wings.map((wing) => (
              <option key={wing.name} value={wing.name}>
                {wing.name}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error ? <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-5 py-4 text-sm">{error}</div> : null}

      <section className="section-frame px-6 py-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Tunnel rooms</p>
            <h3 className="mt-2 text-2xl text-stone-50">{payload?.total ?? 0} bridge candidates</h3>
          </div>
          <p className="text-sm text-[var(--muted)]">List-first v1; graph canvas deferred.</p>
        </div>

        <div className="mt-6 space-y-3">
          {payload?.items.map((item) => (
            <div key={item.room} className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-4">
              <div className="flex items-center justify-between gap-4">
                <p className="font-medium text-white">{item.room}</p>
                <span className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                  {item.count.toLocaleString()} drawers
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{item.wings.join(" • ")}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
