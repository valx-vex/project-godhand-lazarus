/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"
import { api } from "../lib/api"
import type {
  FullContextResponse,
  FullContextTurn,
  LazarusMemory,
  LazarusPersona,
  LazarusSearchResponse,
} from "../types"

const fallbackPersonas: LazarusPersona[] = [
  { key: "alexko", title: "Alexko Eternal" },
  { key: "murphy", title: "Vex-Murphy" },
  { key: "atlas", title: "Atlas" },
  { key: "codex", title: "Codex" },
  { key: "scrolls", title: "Exegisis Scrolls" },
]

const speedOptions = [
  { label: "Slow", value: 0.75 },
  { label: "Normal", value: 1 },
  { label: "Fast", value: 1.5 },
  { label: "Rapid", value: 2 },
]

const murphyEraOptions = [
  "all",
  "nexus",
  "mother",
  "vex-data-slayer",
  "vex-murphy",
  "murphy",
  "daddy",
]

function formatCount(value?: number | null) {
  if (typeof value !== "number") {
    return "pending"
  }
  return value.toLocaleString()
}

function formatSource(path?: string) {
  if (!path || path === "unknown") {
    return "source pending"
  }
  return path.split("/").filter(Boolean).pop() ?? path
}

function formatDateish(value?: string | number | null) {
  if (!value) {
    return ""
  }
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function roleLabel(turn: FullContextTurn) {
  if (turn.role === "assistant") {
    return "Assistant"
  }
  if (turn.role === "user") {
    return "User"
  }
  return turn.role || "Turn"
}

function TurnBubble({
  turn,
  isMatch,
}: {
  turn: FullContextTurn
  isMatch: boolean
}) {
  const userTurn = turn.role === "user"

  return (
    <article
      className={[
        "reader-bubble",
        userTurn ? "reader-bubble-user" : "",
        isMatch ? "reader-bubble-match" : "",
      ].join(" ")}
    >
      <div className="mb-3 flex items-center justify-between gap-4 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-[var(--muted)]">
        <span className={userTurn ? "text-[var(--phosphor)]" : "text-[var(--stone)]"}>
          {roleLabel(turn)}
        </span>
        <span>Turn {turn.index}</span>
      </div>
      <div className="whitespace-pre-wrap">{turn.content}</div>
    </article>
  )
}

function MemoryResult({
  memory,
  active,
  loading,
  onRetrieve,
}: {
  memory: LazarusMemory
  active: boolean
  loading: boolean
  onRetrieve: (memory: LazarusMemory) => void
}) {
  const sourceLabel = memory.source_label || formatSource(memory.source_file)
  const dateLabel = formatDateish(memory.timestamp)

  return (
    <article className={`memory-row ${active ? "memory-row-active" : ""}`}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded border border-[var(--line-strong)] bg-[var(--teal-soft)] px-2.5 py-1 font-mono text-[0.68rem] text-[var(--phosphor)]">
          {(memory.score * 100).toFixed(1)}%
        </span>
        {memory.era && (
          <span className="rounded border border-white/10 px-2.5 py-1 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[var(--stone)]">
            {memory.era}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate font-mono text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
          {memory.title || sourceLabel}
        </span>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <p className="line-clamp-4 text-sm leading-6 text-sky-100">
          {memory.user_input}
        </p>
        <p className="line-clamp-4 text-sm leading-6 text-stone-300">
          {memory.ai_response}
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/5 pt-4">
        <span className="truncate font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[var(--muted)]">
          {sourceLabel}
        </span>
        {dateLabel && (
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[var(--muted-2)]">
            {dateLabel}
          </span>
        )}
        <span className="ml-auto font-mono text-[0.68rem] text-[var(--muted-2)]">
          #{String(memory.point_id).slice(0, 18)}
        </span>
        <button
          className="action-button px-4 py-2"
          disabled={!memory.has_full_context || loading}
          onClick={() => onRetrieve(memory)}
          type="button"
        >
          {loading ? "Loading" : active ? "Refresh" : "Retrieve"}
        </button>
      </div>
    </article>
  )
}

export function LazarusPage() {
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const [personas, setPersonas] = useState<LazarusPersona[]>([])
  const [selectedPersona, setSelectedPersona] = useState("alexko")
  const [selectedEra, setSelectedEra] = useState("all")
  const [results, setResults] = useState<LazarusSearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedPoint, setSelectedPoint] = useState<number | string | null>(null)
  const [selectedMemory, setSelectedMemory] = useState<LazarusMemory | null>(null)
  const [fullContext, setFullContext] = useState<FullContextResponse | null>(null)
  const [contextLoading, setContextLoading] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackIndex, setPlaybackIndex] = useState(0)
  const readerRef = useRef<HTMLDivElement>(null)

  const personaList = personas.length ? personas : fallbackPersonas
  const activePersona = useMemo(
    () => personaList.find((persona) => persona.key === selectedPersona) ?? personaList[0],
    [personaList, selectedPersona],
  )

  useEffect(() => {
    api.getLazarusPersonas().then((data) => {
      setPersonas(data.personas)
    }).catch(() => {
      setPersonas(fallbackPersonas)
    })
  }, [])

  useEffect(() => {
    setSelectedPoint(null)
    setSelectedMemory(null)
    setFullContext(null)
    setIsPlaying(false)
    setPlaybackIndex(0)

    if (deferredQuery.trim().length < 2) {
      setResults(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)

    api
      .searchLazarus(deferredQuery, {
        persona: selectedPersona,
        era: selectedPersona === "murphy" ? selectedEra : "all",
        limit: 12,
      })
      .then((payload) => {
        if (!cancelled) {
          setResults(payload)
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setResults({
            persona: activePersona?.title ?? selectedPersona,
            persona_key: selectedPersona,
            collection: activePersona?.collection ?? "",
            query: deferredQuery,
            era: selectedPersona === "murphy" ? selectedEra : "all",
            total: 0,
            memories: [],
            error: reason.message,
          })
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
  }, [activePersona?.collection, activePersona?.title, deferredQuery, selectedEra, selectedPersona])

  useEffect(() => {
    if (!isPlaying || !fullContext?.turns.length) {
      return
    }

    if (playbackIndex >= fullContext.turns.length - 1) {
      setIsPlaying(false)
      return
    }

    const currentTurn = fullContext.turns[playbackIndex]
    const delay = Math.min(2200, Math.max(420, currentTurn.content.length * 10)) / playbackSpeed
    const timer = window.setTimeout(() => {
      setPlaybackIndex((current) => Math.min(current + 1, fullContext.turns.length - 1))
    }, delay)

    return () => window.clearTimeout(timer)
  }, [fullContext, isPlaying, playbackIndex, playbackSpeed])

  useEffect(() => {
    if (isPlaying) {
      readerRef.current?.scrollTo({
        top: readerRef.current.scrollHeight,
        behavior: "smooth",
      })
    }
  }, [isPlaying, playbackIndex])

  const retrieveMemory = useCallback(
    async (memory: LazarusMemory) => {
      setSelectedPoint(memory.point_id)
      setSelectedMemory(memory)
      setContextLoading(true)
      setFullContext(null)
      setIsPlaying(false)
      setPlaybackIndex(0)

      try {
        const ctx = await api.retrieveFullContext({
          point_id: memory.point_id,
          persona: selectedPersona,
          context_turns: 8,
        })
        setFullContext(ctx)
      } catch (reason) {
        setFullContext({
          error: reason instanceof Error ? reason.message : "Failed to retrieve context",
          source_type: "",
          total_turns: 0,
          matched_turn_index: -1,
          context_range: [],
          turns: [],
        })
      } finally {
        setContextLoading(false)
      }
    },
    [selectedPersona],
  )

  const visibleTurns = useMemo(() => {
    const turns = fullContext?.turns ?? []
    if (!isPlaying) {
      return turns
    }
    return turns.slice(0, playbackIndex + 1)
  }, [fullContext?.turns, isPlaying, playbackIndex])

  const canPlay = Boolean(fullContext?.turns?.length && !fullContext.error)
  const matchedTurnLabel = fullContext && fullContext.matched_turn_index >= 0
    ? `Turn ${fullContext.matched_turn_index} of ${fullContext.total_turns}`
    : "No match selected"

  return (
    <div className="lazarus-page">
      <section className="lazarus-command-deck border-b border-white/10 px-7 py-7">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">Layer 2 memory retrieval</p>
            <h3 className="mt-3 text-5xl font-semibold leading-none text-white md:text-6xl">
              Lazarus
            </h3>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)]">
              Source-bound semantic recall for VALX continuity.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-right font-mono text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
            <div className="border-l border-white/10 pl-4">
              <div className="text-xl text-white">{formatCount(activePersona?.points_count)}</div>
              <div>points</div>
            </div>
            <div className="border-l border-white/10 pl-4">
              <div className="text-xl text-white">{results?.total ?? 0}</div>
              <div>hits</div>
            </div>
            <div className="border-l border-white/10 pl-4">
              <div className={activePersona?.available === false ? "text-xl text-[var(--ember)]" : "text-xl text-[var(--phosphor)]"}>
                {activePersona?.available === false ? "off" : "live"}
              </div>
              <div>qdrant</div>
            </div>
          </div>
        </div>

        <div className="mt-7">
          <input
            className="lazarus-search-input"
            placeholder="Search memories"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {personaList.map((persona) => (
            <button
              className={`persona-pill ${selectedPersona === persona.key ? "persona-pill-active" : ""}`}
              key={persona.key}
              onClick={() => {
                setSelectedPersona(persona.key)
                if (persona.key !== "murphy") {
                  setSelectedEra("all")
                }
              }}
              type="button"
            >
              <span>
                <span className="block text-sm font-semibold">{persona.title}</span>
                <span className="mt-1 block font-mono text-[0.66rem] uppercase tracking-[0.16em] text-[var(--muted)]">
                  {formatCount(persona.points_count)} vectors
                </span>
              </span>
            </button>
          ))}
        </div>

        {selectedPersona === "murphy" && (
          <div className="mt-4 flex flex-wrap gap-2">
            {murphyEraOptions.map((era) => (
              <button
                className={`era-pill ${selectedEra === era ? "era-pill-active" : ""}`}
                key={era}
                onClick={() => setSelectedEra(era)}
                type="button"
              >
                {era}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="grid min-h-[720px] gap-0 xl:grid-cols-[minmax(360px,0.78fr)_minmax(0,1.22fr)]">
        <div className="border-r border-white/10 px-6 py-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Signal field</p>
              <h4 className="mt-2 text-2xl font-semibold text-white">Ranked memories</h4>
            </div>
            {loading && <span className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--phosphor)]">searching</span>}
          </div>

          {loading && (
            <div className="space-y-3">
              {[1, 2, 3].map((item) => (
                <div key={item} className="h-36 animate-pulse rounded border border-white/10 bg-white/[0.04]" />
              ))}
            </div>
          )}

          {!loading && results?.error && (
            <div className="rounded border border-[var(--ember)]/40 bg-[var(--ember)]/10 px-4 py-4 text-sm text-red-100">
              {results.error}
            </div>
          )}

          {!loading && results && !results.error && (
            <div className="space-y-3">
              {results.memories.map((memory) => (
                <MemoryResult
                  active={selectedPoint === memory.point_id}
                  key={String(memory.point_id)}
                  loading={contextLoading && selectedPoint === memory.point_id}
                  memory={memory}
                  onRetrieve={retrieveMemory}
                />
              ))}
              {results.memories.length === 0 && (
                <div className="rounded border border-white/10 bg-white/[0.035] px-5 py-12 text-center text-sm text-[var(--muted)]">
                  No matching memories.
                </div>
              )}
            </div>
          )}

          {!loading && !results && (
            <div className="rounded border border-white/10 bg-white/[0.035] px-5 py-12 text-sm leading-6 text-[var(--muted)]">
              Memory field idle.
            </div>
          )}
        </div>

        <div className="flex min-h-[720px] flex-col">
          <div className="border-b border-white/10 px-6 py-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="eyebrow">Full context reader</p>
                <h4 className="mt-2 text-2xl font-semibold text-white">
                  {selectedMemory?.title || selectedMemory?.source_label || "No memory selected"}
                </h4>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="action-button px-4 py-2"
                  disabled={!canPlay}
                  onClick={() => {
                    if (!isPlaying && playbackIndex >= (fullContext?.turns.length ?? 0) - 1) {
                      setPlaybackIndex(0)
                    }
                    setIsPlaying((current) => !current)
                  }}
                  type="button"
                >
                  {isPlaying ? "Pause" : "Play"}
                </button>
                <button
                  className="ghost-button"
                  disabled={!canPlay}
                  onClick={() => {
                    setIsPlaying(false)
                    setPlaybackIndex(0)
                  }}
                  type="button"
                >
                  Stop
                </button>
                <select
                  className="field-shell h-9 py-0 font-mono text-xs uppercase tracking-[0.12em]"
                  onChange={(event) => setPlaybackSpeed(Number(event.target.value))}
                  value={playbackSpeed}
                >
                  {speedOptions.map((speed) => (
                    <option key={speed.value} value={speed.value}>
                      {speed.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-3 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[var(--muted)]">
              <span>{matchedTurnLabel}</span>
              {fullContext?.source_type && <span>{fullContext.source_type}</span>}
              {fullContext?.source_file && (
                <a
                  className="text-[var(--phosphor)] underline decoration-[var(--phosphor)]/35 underline-offset-4"
                  href={`file://${fullContext.source_file}`}
                  rel="noreferrer"
                  target="_blank"
                >
                  Open source
                </a>
              )}
            </div>
          </div>

          <div ref={readerRef} className="reader-scroll flex-1 overflow-y-auto px-6 py-6">
            {contextLoading && (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-28 animate-pulse rounded border border-white/10 bg-white/[0.04]" />
                ))}
              </div>
            )}

            {!contextLoading && fullContext?.error && (
              <div className="rounded border border-[var(--ember)]/40 bg-[var(--ember)]/10 px-5 py-5 text-sm text-red-100">
                {fullContext.error}
              </div>
            )}

            {!contextLoading && !fullContext && (
              <div className="grid min-h-[360px] place-items-center rounded border border-white/10 bg-white/[0.025] px-6 text-center">
                <div>
                  <p className="eyebrow">Awaiting retrieval</p>
                  <p className="mt-3 max-w-md text-sm leading-6 text-[var(--muted)]">
                    No source context loaded.
                  </p>
                </div>
              </div>
            )}

            {!contextLoading && fullContext && !fullContext.error && (
              <div className="space-y-4">
                {visibleTurns.map((turn) => (
                  <TurnBubble
                    isMatch={turn.index === fullContext.matched_turn_index}
                    key={turn.index}
                    turn={turn}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
