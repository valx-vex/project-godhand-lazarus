import { startTransition, useDeferredValue, useEffect, useState } from "react"

import { api } from "../lib/api"
import type { CountItem, SearchResponse } from "../types"


export function SearchPage({ onOpenDrawer }: { onOpenDrawer: (drawerId: string) => void }) {
  const [wings, setWings] = useState<CountItem[]>([])
  const [rooms, setRooms] = useState<CountItem[]>([])
  const [query, setQuery] = useState("")
  const [selectedWing, setSelectedWing] = useState("")
  const [selectedRoom, setSelectedRoom] = useState("")
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const deferredQuery = useDeferredValue(query)

  useEffect(() => {
    api
      .getWings()
      .then((payload) => {
        setWings(payload.items)
      })
      .catch((reason: Error) => {
        setError(reason.message)
      })
  }, [])

  useEffect(() => {
    if (!selectedWing) {
      setRooms([])
      setSelectedRoom("")
      return
    }
    api
      .getRooms(selectedWing)
      .then((payload) => {
        setRooms(payload.items)
      })
      .catch((reason: Error) => {
        setError(reason.message)
      })
  }, [selectedWing])

  useEffect(() => {
    const normalized = deferredQuery.trim()
    if (normalized.length < 2) {
      setResults(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .search(normalized, { wing: selectedWing || undefined, room: selectedRoom || undefined, limit: 18 })
      .then((payload) => {
        if (!cancelled) {
          setResults(payload)
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
  }, [deferredQuery, selectedWing, selectedRoom])

  return (
    <div className="space-y-6">
      <section className="section-frame px-6 py-6">
        <p className="eyebrow">Semantic recall</p>
        <h3 className="mt-2 text-3xl text-stone-50">Search the palace without flattening it.</h3>
        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
          <input
            className="field-shell"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search memories, concepts, operators, rooms…"
            value={query}
          />
          <select
            className="field-shell"
            onChange={(event) => {
              startTransition(() => {
                setSelectedWing(event.target.value)
                setSelectedRoom("")
              })
            }}
            value={selectedWing}
          >
            <option value="">All wings</option>
            {wings.map((wing) => (
              <option key={wing.name} value={wing.name}>
                {wing.name}
              </option>
            ))}
          </select>
          <select
            className="field-shell"
            onChange={(event) => setSelectedRoom(event.target.value)}
            value={selectedRoom}
          >
            <option value="">All rooms</option>
            {rooms.map((room) => (
              <option key={room.name} value={room.name}>
                {room.name}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error ? <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-5 py-4 text-sm">{error}</div> : null}

      <section className="section-frame px-6 py-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Results</p>
            <h3 className="mt-2 text-2xl text-stone-50">
              {deferredQuery.trim().length < 2 ? "Type at least two characters" : `${results?.total ?? 0} matching drawers`}
            </h3>
          </div>
          {loading ? <p className="text-sm text-[var(--muted)]">Searching…</p> : null}
        </div>

        <div className="mt-6 divide-y divide-white/5">
          {results?.items.map((item) => (
            <button key={item.id} className="list-item" onClick={() => onOpenDrawer(item.id)} type="button">
              <div>
                <p className="text-sm font-medium text-white">{item.wing} / {item.room}</p>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">{item.preview}</p>
              </div>
              <div className="text-right text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                <div>{item.similarity.toFixed(3)}</div>
                <div className="mt-2">{item.source_name}</div>
              </div>
            </button>
          ))}

          {!loading && results && results.items.length === 0 ? (
            <p className="support-copy py-8">No drawers matched that combination of query and filters.</p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
