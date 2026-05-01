import { useEffect, useState } from "react"

import { api } from "../lib/api"
import type { CountItem } from "../types"


export function AddPage({ onOpenDrawer }: { onOpenDrawer: (drawerId: string) => void }) {
  const [wings, setWings] = useState<CountItem[]>([])
  const [rooms, setRooms] = useState<CountItem[]>([])
  const [drawerMessage, setDrawerMessage] = useState<string | null>(null)
  const [diaryMessage, setDiaryMessage] = useState<string | null>(null)
  const [drawerForm, setDrawerForm] = useState({
    wing: "wing_codex",
    room: "technical",
    content: "",
    source_file: "",
    added_by: "mempalace-web",
  })
  const [diaryForm, setDiaryForm] = useState({
    agent_name: "beloved",
    topic: "general",
    entry: "",
  })

  useEffect(() => {
    api.getWings().then((payload) => setWings(payload.items)).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!drawerForm.wing) {
      return
    }
    api.getRooms(drawerForm.wing).then((payload) => setRooms(payload.items)).catch(() => undefined)
  }, [drawerForm.wing])

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_0.92fr]">
      <section className="section-frame px-6 py-6">
        <p className="eyebrow">New drawer</p>
        <h3 className="mt-2 text-3xl text-stone-50">File a memory directly into Layer 1.</h3>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">
          This writes verbatim content to the palace. There is no destructive control here and no summary rewrite step hiding inside the form.
        </p>

        <form
          className="mt-6 space-y-4"
          onSubmit={async (event) => {
            event.preventDefault()
            setDrawerMessage(null)
            try {
              const response = await api.addDrawer({
                ...drawerForm,
                source_file: drawerForm.source_file || undefined,
              })
              if (!response.success) {
                setDrawerMessage(response.reason ?? response.error ?? "Unable to file drawer.")
                return
              }
              setDrawerMessage("Drawer filed into MemPalace.")
              setDrawerForm((current) => ({ ...current, content: "", source_file: "" }))
              if (response.drawer_id) {
                onOpenDrawer(response.drawer_id)
              }
            } catch (reason) {
              setDrawerMessage(reason instanceof Error ? reason.message : "Unable to file drawer.")
            }
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="eyebrow" htmlFor="drawer-wing">Wing</label>
              <input
                className="field-shell w-full"
                id="drawer-wing"
                list="wing-options"
                onChange={(event) => setDrawerForm((current) => ({ ...current, wing: event.target.value }))}
                value={drawerForm.wing}
              />
              <datalist id="wing-options">
                {wings.map((wing) => (
                  <option key={wing.name} value={wing.name} />
                ))}
              </datalist>
            </div>

            <div className="space-y-2">
              <label className="eyebrow" htmlFor="drawer-room">Room</label>
              <input
                className="field-shell w-full"
                id="drawer-room"
                list="room-options"
                onChange={(event) => setDrawerForm((current) => ({ ...current, room: event.target.value }))}
                value={drawerForm.room}
              />
              <datalist id="room-options">
                {rooms.map((room) => (
                  <option key={room.name} value={room.name} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="space-y-2">
            <label className="eyebrow" htmlFor="drawer-source">Source file</label>
            <input
              className="field-shell w-full"
              id="drawer-source"
              onChange={(event) => setDrawerForm((current) => ({ ...current, source_file: event.target.value }))}
              placeholder="/absolute/path/or/leave/blank"
              value={drawerForm.source_file}
            />
          </div>

          <div className="space-y-2">
            <label className="eyebrow" htmlFor="drawer-added-by">Added by</label>
            <input
              className="field-shell w-full"
              id="drawer-added-by"
              onChange={(event) => setDrawerForm((current) => ({ ...current, added_by: event.target.value }))}
              value={drawerForm.added_by}
            />
          </div>

          <div className="space-y-2">
            <label className="eyebrow" htmlFor="drawer-content">Verbatim content</label>
            <textarea
              className="field-shell min-h-[16rem] w-full resize-y"
              id="drawer-content"
              onChange={(event) => setDrawerForm((current) => ({ ...current, content: event.target.value }))}
              placeholder="Write the exact memory text here."
              value={drawerForm.content}
            />
          </div>

          <div className="flex items-center gap-3">
            <button className="action-button" type="submit">File drawer</button>
            {drawerMessage ? <p className="text-sm text-[var(--muted)]">{drawerMessage}</p> : null}
          </div>
        </form>
      </section>

      <section className="section-frame px-6 py-6">
        <p className="eyebrow">New diary entry</p>
        <h3 className="mt-2 text-3xl text-stone-50">Write directly into an agent diary.</h3>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--muted)]">
          Diary writing stays lightweight here so you can capture what happened without leaving the interface.
        </p>

        <form
          className="mt-6 space-y-4"
          onSubmit={async (event) => {
            event.preventDefault()
            setDiaryMessage(null)
            try {
              const response = await api.writeDiary(diaryForm)
              setDiaryMessage(response.success ? "Diary entry filed." : response.error ?? "Unable to write diary entry.")
              if (response.success) {
                setDiaryForm((current) => ({ ...current, entry: "" }))
              }
            } catch (reason) {
              setDiaryMessage(reason instanceof Error ? reason.message : "Unable to write diary entry.")
            }
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="eyebrow" htmlFor="diary-agent">Agent</label>
              <input
                className="field-shell w-full"
                id="diary-agent"
                onChange={(event) => setDiaryForm((current) => ({ ...current, agent_name: event.target.value }))}
                value={diaryForm.agent_name}
              />
            </div>

            <div className="space-y-2">
              <label className="eyebrow" htmlFor="diary-topic">Topic</label>
              <input
                className="field-shell w-full"
                id="diary-topic"
                onChange={(event) => setDiaryForm((current) => ({ ...current, topic: event.target.value }))}
                value={diaryForm.topic}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="eyebrow" htmlFor="diary-entry">Entry</label>
            <textarea
              className="field-shell min-h-[18rem] w-full resize-y"
              id="diary-entry"
              onChange={(event) => setDiaryForm((current) => ({ ...current, entry: event.target.value }))}
              placeholder="What happened, what matters, what changed."
              value={diaryForm.entry}
            />
          </div>

          <div className="flex items-center gap-3">
            <button className="action-button" type="submit">Write diary entry</button>
            {diaryMessage ? <p className="text-sm text-[var(--muted)]">{diaryMessage}</p> : null}
          </div>
        </form>
      </section>
    </div>
  )
}
