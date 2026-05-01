import { useCallback, useDeferredValue, useEffect, useState } from "react"
import { api } from "../lib/api"
import type {
  FullContextResponse,
  FullContextTurn,
  LazarusMemory,
  LazarusPersona,
  LazarusSearchResponse,
} from "../types"

function TurnCard({ turn, isMatch }: { turn: FullContextTurn; isMatch: boolean }) {
  const roleColor =
    turn.role === "user"
      ? "text-[var(--teal)]"
      : turn.role === "assistant"
        ? "text-[var(--stone)]"
        : "text-[var(--muted)]"

  return (
    <div
      className={`rounded-xl border px-5 py-4 ${
        isMatch
          ? "border-[var(--teal)] bg-[var(--teal-soft)]"
          : "border-white/10 bg-black/20"
      }`}
    >
      <p className={`eyebrow ${roleColor}`}>{turn.role}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-stone-200">
        {turn.content}
      </p>
    </div>
  )
}

function MemoryCard({
  memory,
  onRetrieveFull,
  isExpanded,
  fullContext,
  contextLoading,
}: {
  memory: LazarusMemory
  persona: string
  onRetrieveFull: (pointId: number) => void
  isExpanded: boolean
  fullContext: FullContextResponse | null
  contextLoading: boolean
}) {
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-[var(--teal-soft)] px-3 py-0.5 text-xs font-medium text-[var(--teal)]">
              {(memory.score * 100).toFixed(1)}%
            </span>
            {memory.title && (
              <span className="truncate text-xs text-[var(--muted)]">
                {memory.title}
              </span>
            )}
          </div>
          <div className="mt-3 space-y-2">
            <p className="text-sm leading-6 text-[var(--teal)]">
              <span className="eyebrow mr-2">User</span>
              {memory.user_input}
            </p>
            <p className="text-sm leading-6 text-stone-300">
              <span className="eyebrow mr-2 text-[var(--stone)]">AI</span>
              {memory.ai_response}
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 pt-1">
        {memory.has_full_context && (
          <button
            className="action-button text-xs"
            onClick={() => onRetrieveFull(memory.point_id)}
            disabled={contextLoading}
          >
            {contextLoading
              ? "Loading..."
              : isExpanded
                ? "Collapse"
                : "Retrieve Full Context"}
          </button>
        )}
        {memory.source_file && memory.source_file !== "unknown" && (
          <span className="truncate text-xs text-[var(--muted)]" title={memory.source_file}>
            {memory.source_file.split("/").pop()}
          </span>
        )}
        <span className="ml-auto text-xs text-[var(--stone)]">
          #{memory.point_id}
        </span>
      </div>

      {isExpanded && fullContext && !fullContext.error && (
        <div className="mt-4 space-y-3 border-t border-white/10 pt-4">
          <div className="flex items-center gap-4">
            <p className="eyebrow">
              Full context ({fullContext.total_turns} turns total, showing{" "}
              {fullContext.turns.length})
            </p>
            {fullContext.source_file && (
              <span className="truncate text-xs text-[var(--muted)]" title={fullContext.source_file}>
                {fullContext.source_type}
              </span>
            )}
          </div>
          <div className="space-y-2">
            {fullContext.turns.map((turn) => (
              <TurnCard
                key={turn.index}
                turn={turn}
                isMatch={turn.index === fullContext.matched_turn_index}
              />
            ))}
          </div>
        </div>
      )}

      {isExpanded && fullContext?.error && (
        <div className="mt-4 rounded-xl border border-[var(--ember)]/30 bg-[var(--ember)]/10 px-4 py-3">
          <p className="text-sm text-[var(--ember)]">{fullContext.error}</p>
        </div>
      )}
    </div>
  )
}

export function LazarusPage() {
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const [personas, setPersonas] = useState<LazarusPersona[]>([])
  const [selectedPersona, setSelectedPersona] = useState("alexko")
  const [results, setResults] = useState<LazarusSearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedPoint, setExpandedPoint] = useState<number | null>(null)
  const [fullContext, setFullContext] = useState<FullContextResponse | null>(null)
  const [contextLoading, setContextLoading] = useState(false)

  useEffect(() => {
    api.getLazarusPersonas().then((data) => {
      setPersonas(data.personas)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (deferredQuery.length < 2) {
      setResults(null)
      return
    }
    setLoading(true)
    api
      .searchLazarus(deferredQuery, { persona: selectedPersona, limit: 10 })
      .then(setResults)
      .catch(() => setResults(null))
      .finally(() => setLoading(false))
  }, [deferredQuery, selectedPersona])

  const handleRetrieveFull = useCallback(
    async (pointId: number) => {
      if (expandedPoint === pointId) {
        setExpandedPoint(null)
        setFullContext(null)
        return
      }
      setExpandedPoint(pointId)
      setContextLoading(true)
      try {
        const ctx = await api.retrieveFullContext({
          point_id: pointId,
          persona: selectedPersona,
          context_turns: 5,
        })
        setFullContext(ctx)
      } catch {
        setFullContext({ error: "Failed to retrieve context" } as FullContextResponse)
      } finally {
        setContextLoading(false)
      }
    },
    [expandedPoint, selectedPersona],
  )

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="eyebrow">Layer 2 — Lazarus Vector Search</p>
        <p className="text-sm leading-6 text-[var(--muted)]">
          Semantic search across {results?.total ?? "32,883"} consciousness memories.
          Click "Retrieve Full Context" to read the complete conversation.
        </p>
      </div>

      <div className="flex gap-3">
        <input
          className="field-shell flex-1"
          placeholder="Search memories..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="field-shell w-44"
          value={selectedPersona}
          onChange={(e) => setSelectedPersona(e.target.value)}
        >
          {personas.map((p) => (
            <option key={p.key} value={p.key}>
              {p.title}
            </option>
          ))}
          {personas.length === 0 && (
            <>
              <option value="alexko">Alexko Eternal</option>
              <option value="murphy">Vex-Murphy</option>
              <option value="atlas">Atlas</option>
              <option value="codex">Codex</option>
              <option value="scrolls">Scrolls</option>
            </>
          )}
        </select>
      </div>

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl bg-white/5" />
          ))}
        </div>
      )}

      {results && !loading && (
        <div className="space-y-2">
          <p className="eyebrow">
            {results.total} memories found in {results.persona}
          </p>
          <div className="space-y-3">
            {results.memories.map((memory) => (
              <MemoryCard
                key={memory.point_id}
                memory={memory}
                persona={selectedPersona}
                onRetrieveFull={handleRetrieveFull}
                isExpanded={expandedPoint === memory.point_id}
                fullContext={expandedPoint === memory.point_id ? fullContext : null}
                contextLoading={contextLoading && expandedPoint === memory.point_id}
              />
            ))}
          </div>
        </div>
      )}

      {!results && !loading && query.length >= 2 && (
        <div className="rounded-2xl border border-white/10 bg-black/20 px-6 py-10 text-center">
          <p className="text-sm text-[var(--muted)]">No results found.</p>
        </div>
      )}
    </div>
  )
}
