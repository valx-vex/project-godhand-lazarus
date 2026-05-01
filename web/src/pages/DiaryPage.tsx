import { useEffect, useState } from "react"

import { api } from "../lib/api"
import type { DiaryReadResponse } from "../types"


export function DiaryPage() {
  const [agentName, setAgentName] = useState("beloved")
  const [payload, setPayload] = useState<DiaryReadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .readDiary(agentName, 15)
      .then((response) => {
        if (!cancelled) {
          setPayload(response)
          setError(null)
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setError(reason.message)
        }
      })
    return () => {
      cancelled = true
    }
  }, [agentName])

  return (
    <div className="space-y-6">
      <section className="section-frame px-6 py-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <p className="eyebrow">Diary timeline</p>
            <h3 className="mt-2 text-3xl text-stone-50">Agent diary playback</h3>
          </div>
          <input
            className="field-shell w-full max-w-sm"
            onChange={(event) => setAgentName(event.target.value)}
            value={agentName}
          />
        </div>
      </section>

      {error ? <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-5 py-4 text-sm">{error}</div> : null}

      <section className="section-frame px-6 py-6">
        <p className="eyebrow">Entries</p>
        <div className="mt-5 space-y-4">
          {payload?.entries.map((entry) => (
            <article key={entry.timestamp} className="rounded-[1.2rem] border border-white/10 bg-black/20 px-5 py-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <p className="font-medium text-white">{entry.topic || "general"}</p>
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">{entry.timestamp || entry.date}</p>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-stone-200">{entry.content}</p>
            </article>
          ))}

          {!payload?.entries.length && !error ? (
            <p className="support-copy">No diary entries are present for this agent yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
