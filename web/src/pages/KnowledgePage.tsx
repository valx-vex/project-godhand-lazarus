import { useEffect, useState } from "react"

import { api } from "../lib/api"
import type { KnowledgeEntityResponse, KnowledgeStats, KnowledgeTimelineResponse } from "../types"


export function KnowledgePage() {
  const [stats, setStats] = useState<KnowledgeStats | null>(null)
  const [entity, setEntity] = useState("beloved")
  const [facts, setFacts] = useState<KnowledgeEntityResponse | null>(null)
  const [timeline, setTimeline] = useState<KnowledgeTimelineResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getKnowledgeStats().then(setStats).catch((reason: Error) => setError(reason.message))
  }, [])

  const loadEntity = async () => {
    try {
      setError(null)
      const [factPayload, timelinePayload] = await Promise.all([
        api.getKnowledgeEntity(entity),
        api.getKnowledgeTimeline(entity),
      ])
      setFacts(factPayload)
      setTimeline(timelinePayload)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load knowledge graph.")
    }
  }

  useEffect(() => {
    void loadEntity()
  }, [])

  return (
    <div className="space-y-6">
      <section className="section-frame px-6 py-6">
        <p className="eyebrow">Temporal graph</p>
        <h3 className="mt-2 text-3xl text-stone-50">Facts first, visuals later.</h3>
        <div className="mt-6 flex flex-col gap-4 md:flex-row">
          <input
            className="field-shell flex-1"
            onChange={(event) => setEntity(event.target.value)}
            placeholder="Entity name"
            value={entity}
          />
          <button className="action-button" onClick={() => void loadEntity()} type="button">
            Query entity
          </button>
        </div>
      </section>

      {stats ? (
        <section className="grid gap-4 md:grid-cols-4">
          <div className="metric-strip">
            <p className="eyebrow">Entities</p>
            <p className="mt-4 text-4xl text-teal-300">{stats.entities.toLocaleString()}</p>
          </div>
          <div className="metric-strip">
            <p className="eyebrow">Triples</p>
            <p className="mt-4 text-4xl text-teal-300">{stats.triples.toLocaleString()}</p>
          </div>
          <div className="metric-strip">
            <p className="eyebrow">Current</p>
            <p className="mt-4 text-4xl text-stoneglass">{stats.current_facts.toLocaleString()}</p>
          </div>
          <div className="metric-strip">
            <p className="eyebrow">Predicates</p>
            <p className="mt-4 text-4xl text-stoneglass">{stats.relationship_types.length.toLocaleString()}</p>
          </div>
        </section>
      ) : null}

      {error ? <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-5 py-4 text-sm">{error}</div> : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="section-frame px-6 py-6">
          <p className="eyebrow">Entity facts</p>
          <div className="mt-5 space-y-3">
            {facts?.facts.map((fact, index) => (
              <div key={`${fact.subject}-${fact.predicate}-${fact.object}-${index}`} className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-4">
                <p className="font-medium text-white">
                  {fact.subject} → {fact.predicate} → {fact.object}
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                  {fact.current ? "Current" : "Historical"} • {fact.direction}
                  {fact.valid_from ? ` • from ${fact.valid_from}` : ""}
                  {fact.valid_to ? ` • until ${fact.valid_to}` : ""}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="section-frame px-6 py-6">
          <p className="eyebrow">Timeline</p>
          <div className="mt-5 space-y-3">
            {timeline?.timeline.map((entry, index) => (
              <div key={`${entry.subject}-${entry.predicate}-${entry.object}-${index}`} className="rounded-[1rem] border border-white/10 bg-black/20 px-4 py-4">
                <p className="font-medium text-white">
                  {entry.subject} → {entry.predicate} → {entry.object}
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                  {entry.valid_from ?? "Unknown start"}
                  {entry.valid_to ? ` → ${entry.valid_to}` : " → current"}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
