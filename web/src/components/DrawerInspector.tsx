import Markdown from "react-markdown"

import type { DrawerInspectorPayload } from "../types"


export function DrawerInspector({
  loading,
  error,
  payload,
  onClose,
  onSelectSibling,
}: {
  loading: boolean
  error: string | null
  payload: DrawerInspectorPayload | null
  onClose: () => void
  onSelectSibling: (drawerId: string) => void
}) {
  return (
    <div className="section-frame sticky top-4 flex min-h-[22rem] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p className="eyebrow">Inspector</p>
          <h3 className="mt-2 text-2xl text-stone-50">Drawer Detail</h3>
        </div>
        <button className="ghost-button" onClick={onClose} type="button">
          Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-5">
        {loading ? (
          <div className="space-y-4">
            <div className="h-5 w-28 animate-pulse rounded-full bg-white/10" />
            <div className="h-4 w-48 animate-pulse rounded-full bg-white/10" />
            <div className="space-y-2">
              <div className="h-3 animate-pulse rounded-full bg-white/5" />
              <div className="h-3 animate-pulse rounded-full bg-white/5" />
              <div className="h-3 w-4/5 animate-pulse rounded-full bg-white/5" />
            </div>
          </div>
        ) : error ? (
          <div className="rounded-[1.25rem] border border-ember/30 bg-ember/10 px-4 py-4 text-sm text-stone-200">
            {error}
          </div>
        ) : payload ? (
          <div className="space-y-6">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.24em] text-[var(--stone)]">
                <span>{payload.drawer.wing}</span>
                <span>•</span>
                <span>{payload.drawer.room}</span>
                <span>•</span>
                <span>chunk {payload.drawer.chunk_index ?? 0}</span>
              </div>
              <div className="space-y-1 text-sm text-[var(--muted)]">
                <p>{payload.drawer.source_name || "Manual entry"}</p>
                <p>{payload.drawer.filed_at ?? "Timestamp unavailable"}</p>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-white/10 bg-black/20 px-4 py-4">
              <div className="markdown-body">
                <Markdown>{payload.drawer.content}</Markdown>
              </div>
            </div>

            <div className="space-y-3">
              <p className="eyebrow">Same source chunks</p>
              <div className="space-y-2">
                {payload.siblings.map((sibling) => (
                  <button
                    key={sibling.id}
                    className={`w-full rounded-[1rem] border px-4 py-3 text-left transition ${
                      sibling.is_current
                        ? "border-[var(--line-strong)] bg-[var(--teal-soft)]"
                        : "border-white/10 bg-white/[0.02] hover:border-[var(--line-strong)]"
                    }`}
                    onClick={() => onSelectSibling(sibling.id)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-sm font-medium text-white">Chunk {sibling.chunk_index ?? 0}</span>
                      <span className="text-xs uppercase tracking-[0.22em] text-[var(--stone)]">
                        {sibling.is_current ? "Active" : "Open"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{sibling.preview}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="eyebrow">No selection</p>
            <h4 className="text-2xl text-stone-50">Choose a drawer from browse, search, or dashboard.</h4>
            <p className="support-copy">
              The inspector renders the full drawer body with source-linked sibling chunks so the text stays grounded in its original filing context.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
