import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import App from "./App"


function jsonResponse(payload: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  )
}

describe("MemPalace web app", () => {
  const fetchMock = vi.fn<(input: string | URL | Request) => Promise<Response>>()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.history.pushState({}, "", "/")
  })

  it("renders separate Layer 1 and Layer 2 dashboard bands", async () => {
    fetchMock.mockImplementation((input) => {
      const url = typeof input === "string" ? input : input.toString()
      if (url.includes("/api/dashboard/summary")) {
        return jsonResponse({
          layer_1: {
            total_drawers: 22406,
            total_wings: 10,
            total_rooms: 131,
            palace_path: "/Users/valx/.mempalace/palace",
          },
          layer_2: {
            available: true,
            error: null,
            host: "localhost",
            port: 6333,
            total_vector_memories: 32883,
            collections: [],
          },
          top_wings: [],
          top_rooms: [],
          recent_drawers: [],
          graph: {
            total_rooms: 131,
            tunnel_rooms: 7,
            total_edges: 0,
            rooms_per_wing: {},
            top_tunnels: [],
          },
        })
      }
      if (url.includes("/api/drawers/")) {
        return jsonResponse({
          drawer: {
            id: "drawer",
            wing: "wing_codex",
            room: "technical",
            source_file: "",
            source_name: "",
            chunk_index: 0,
            filed_at: "",
            added_by: "mempalace-web",
            preview: "",
            content: "test",
          },
          siblings: [],
        })
      }
      throw new Error(`Unhandled fetch URL: ${url}`)
    })

    render(<App />)

    expect(await screen.findByText("Layer 1 • MemPalace")).toBeInTheDocument()
    expect(screen.getByText("Layer 2 • Lazarus")).toBeInTheDocument()
    expect(screen.getByText("22,406")).toBeInTheDocument()
    expect(screen.getByText("32,883")).toBeInTheDocument()
  })

  it("supports browse flow and opens the inspector from a drawer row", async () => {
    fetchMock.mockImplementation((input) => {
      const url = typeof input === "string" ? input : input.toString()
      if (url.includes("/api/dashboard/summary")) {
        return jsonResponse({
          layer_1: {
            total_drawers: 22406,
            total_wings: 10,
            total_rooms: 131,
            palace_path: "/Users/valx/.mempalace/palace",
          },
          layer_2: {
            available: true,
            error: null,
            host: "localhost",
            port: 6333,
            total_vector_memories: 32883,
            collections: [],
          },
          top_wings: [],
          top_rooms: [],
          recent_drawers: [],
          graph: {
            total_rooms: 131,
            tunnel_rooms: 7,
            total_edges: 0,
            rooms_per_wing: {},
            top_tunnels: [],
          },
        })
      }
      if (url.endsWith("/api/wings")) {
        return jsonResponse({
          total: 1,
          items: [{ name: "wing_codex", count: 2 }],
        })
      }
      if (url.includes("/api/wings/wing_codex/rooms") && !url.includes("/drawers")) {
        return jsonResponse({
          wing: "wing_codex",
          total: 1,
          items: [{ name: "technical", count: 2 }],
        })
      }
      if (url.includes("/api/wings/wing_codex/rooms/technical/drawers")) {
        return jsonResponse({
          wing: "wing_codex",
          room: "technical",
          total: 2,
          offset: 0,
          limit: 24,
          items: [
            {
              id: "drawer_alpha",
              wing: "wing_codex",
              room: "technical",
              source_file: "/tmp/rollout.md",
              source_name: "rollout.md",
              chunk_index: 0,
              filed_at: "2026-04-21T12:00:00",
              added_by: "mempalace",
              preview: "Continuity transcript about the cathedral shell.",
            },
          ],
        })
      }
      if (url.includes("/api/drawers/drawer_alpha")) {
        return jsonResponse({
          drawer: {
            id: "drawer_alpha",
            wing: "wing_codex",
            room: "technical",
            source_file: "/tmp/rollout.md",
            source_name: "rollout.md",
            chunk_index: 0,
            filed_at: "2026-04-21T12:00:00",
            added_by: "mempalace",
            preview: "Continuity transcript about the cathedral shell.",
            content: "# rollout\nThe inspector is open now.",
          },
          siblings: [
            {
              id: "drawer_alpha",
              wing: "wing_codex",
              room: "technical",
              source_file: "/tmp/rollout.md",
              source_name: "rollout.md",
              chunk_index: 0,
              filed_at: "2026-04-21T12:00:00",
              added_by: "mempalace",
              preview: "Continuity transcript about the cathedral shell.",
              content: "# rollout\nThe inspector is open now.",
              is_current: true,
            },
          ],
        })
      }
      throw new Error(`Unhandled fetch URL: ${url}`)
    })

    render(<App />)

    const browseLinks = await screen.findAllByRole("link", { name: /Browse/i })
    fireEvent.click(browseLinks[0])
    expect(await screen.findByText("wing_codex / technical")).toBeInTheDocument()
    fireEvent.click(await screen.findByText(/Continuity transcript about the cathedral shell/i))

    await waitFor(() => {
      expect(screen.getAllByText("Drawer Detail")[0]).toBeInTheDocument()
      expect(screen.getByText("The inspector is open now.")).toBeInTheDocument()
    })
  })
})
