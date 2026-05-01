import { startTransition, useEffect, useState } from "react"

import { api } from "../lib/api"
import type { BrowseResponse, CountItem } from "../types"


export function BrowsePage({ onOpenDrawer }: { onOpenDrawer: (drawerId: string) => void }) {
  const [wings, setWings] = useState<CountItem[]>([])
  const [rooms, setRooms] = useState<CountItem[]>([])
  const [drawers, setDrawers] = useState<BrowseResponse | null>(null)
  const [selectedWing, setSelectedWing] = useState("")
  const [selectedRoom, setSelectedRoom] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const pageSize = 24

  useEffect(() => {
    let cancelled = false
    api
      .getWings()
      .then((payload) => {
        if (cancelled) {
          return
        }
        setWings(payload.items)
        if (payload.items.length > 0) {
          setSelectedWing(payload.items[0].name)
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
  }, [])

  useEffect(() => {
    if (!selectedWing) {
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    setOffset(0)

    api
      .getRooms(selectedWing)
      .then((payload) => {
        if (cancelled) {
          return
        }
        setRooms(payload.items)
        setSelectedRoom(payload.items[0]?.name ?? "")
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
  }, [selectedWing])

  useEffect(() => {
    if (!selectedWing || !selectedRoom) {
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    api
      .getDrawers(selectedWing, selectedRoom, { offset, limit: pageSize })
      .then((payload) => {
        if (!cancelled) {
          setDrawers(payload)
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
  }, [selectedWing, selectedRoom, offset])

  return (
    <div className="space-y-6">
      <section className="section-frame px-6 py-6">
        <p className="eyebrow">Browse flow</p>
        <h3 className="mt-2 text-3xl text-stone-50">Wing → room → drawer</h3>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">
          Direct Chroma reads power the browse surface so the palace stays navigable even where the current MCP layer does not expose native drawer-list endpoints.
        </p>
      </section>

      {error ? <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-5 py-4 text-sm">{error}</div> : null}

      <section className="grid gap-4 xl:grid-cols-[220px_220px_minmax(0,1fr)]">
        <div className="section-frame px-5 py-5">
          <p className="eyebrow">Wings</p>
          <div className="mt-4 space-y-2">
            {wings.map((wing) => (
              <button
                key={wing.name}
                className={`w-full rounded-[1rem] border px-4 py-3 text-left transition ${
                  wing.name === selectedWing
                    ? "border-[var(--line-strong)] bg-[var(--teal-soft)]"
                    : "border-white/10 bg-black/20 hover:border-[var(--line-strong)]"
                }`}
                onClick={() => {
                  startTransition(() => {
                    setSelectedWing(wing.name)
                  })
                }}
                type="button"
              >
                <div className="text-sm font-medium text-white">{wing.name}</div>
                <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                  {wing.count.toLocaleString()} drawers
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="section-frame px-5 py-5">
          <p className="eyebrow">Rooms</p>
          <div className="mt-4 space-y-2">
            {rooms.map((room) => (
              <button
                key={room.name}
                className={`w-full rounded-[1rem] border px-4 py-3 text-left transition ${
                  room.name === selectedRoom
                    ? "border-[var(--line-strong)] bg-[var(--teal-soft)]"
                    : "border-white/10 bg-black/20 hover:border-[var(--line-strong)]"
                }`}
                onClick={() => {
                  startTransition(() => {
                    setOffset(0)
                    setSelectedRoom(room.name)
                  })
                }}
                type="button"
              >
                <div className="text-sm font-medium text-white">{room.name}</div>
                <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                  {room.count.toLocaleString()} drawers
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="section-frame px-6 py-6">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Drawers</p>
              <h3 className="mt-2 text-2xl text-stone-50">{selectedWing || "Choose a wing"} / {selectedRoom || "Choose a room"}</h3>
            </div>
            {drawers ? <p className="text-sm text-[var(--muted)]">{drawers.total.toLocaleString()} total</p> : null}
          </div>

          {loading ? (
            <p className="mt-6 support-copy">Loading browse slice…</p>
          ) : (
            <div className="mt-6">
              <div className="divide-y divide-white/5">
                {drawers?.items.map((drawer) => (
                  <button key={drawer.id} className="list-item" onClick={() => onOpenDrawer(drawer.id)} type="button">
                    <div>
                      <p className="text-sm font-medium text-white">{drawer.source_name || "Manual entry"}</p>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">{drawer.preview}</p>
                    </div>
                    <div className="text-right text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                      <div>Chunk {drawer.chunk_index ?? 0}</div>
                    </div>
                  </button>
                ))}
              </div>

              {drawers && drawers.total > pageSize ? (
                <div className="mt-6 flex items-center justify-between">
                  <button
                    className="ghost-button"
                    disabled={offset === 0}
                    onClick={() => setOffset((current) => Math.max(0, current - pageSize))}
                    type="button"
                  >
                    Previous slice
                  </button>
                  <p className="text-sm text-[var(--muted)]">
                    {offset + 1}–{Math.min(offset + pageSize, drawers.total)} of {drawers.total}
                  </p>
                  <button
                    className="ghost-button"
                    disabled={offset + pageSize >= drawers.total}
                    onClick={() => setOffset((current) => current + pageSize)}
                    type="button"
                  >
                    Next slice
                  </button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
