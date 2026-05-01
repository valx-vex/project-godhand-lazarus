import type {
  BrowseResponse,
  CountItem,
  DashboardSummary,
  DiaryReadResponse,
  DrawerInspectorPayload,
  FullContextResponse,
  GraphStats,
  KnowledgeEntityResponse,
  KnowledgeStats,
  KnowledgeTimelineResponse,
  LazarusPersona,
  LazarusSearchResponse,
  SearchResponse,
  TunnelsResponse,
} from "../types"

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api"

function buildUrl(path: string, params?: Record<string, string | number | null | undefined>) {
  const url = new URL(`${API_BASE}${path}`)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") {
      continue
    }
    url.searchParams.set(key, String(value))
  }
  return url.toString()
}

async function readJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      detail = payload.detail ?? detail
    } catch {
      // Keep the original status text when the body is not JSON.
    }
    throw new Error(detail)
  }

  return (await response.json()) as T
}

export const api = {
  getDashboardSummary() {
    return readJson<DashboardSummary>(buildUrl("/dashboard/summary"))
  },
  getWings() {
    return readJson<{ total: number; items: CountItem[] }>(buildUrl("/wings"))
  },
  getRooms(wing: string) {
    return readJson<{ wing: string; total: number; items: CountItem[] }>(buildUrl(`/wings/${wing}/rooms`))
  },
  getDrawers(wing: string, room: string, params: { offset?: number; limit?: number } = {}) {
    return readJson<BrowseResponse>(buildUrl(`/wings/${wing}/rooms/${room}/drawers`, params))
  },
  getDrawer(drawerId: string) {
    return readJson<DrawerInspectorPayload>(buildUrl(`/drawers/${drawerId}`))
  },
  search(query: string, params: { wing?: string; room?: string; limit?: number } = {}) {
    return readJson<SearchResponse>(buildUrl("/search", { q: query, ...params }))
  },
  addDrawer(payload: {
    wing: string
    room: string
    content: string
    source_file?: string
    added_by: string
  }) {
    return readJson<{ success: boolean; drawer_id?: string; reason?: string; error?: string }>(buildUrl("/drawers"), {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  readDiary(agentName: string, lastN = 10) {
    return readJson<DiaryReadResponse>(buildUrl(`/diary/${agentName}`, { last_n: lastN }))
  },
  writeDiary(payload: { agent_name: string; entry: string; topic: string }) {
    return readJson<{ success: boolean; entry_id?: string; error?: string }>(buildUrl("/diary"), {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  getKnowledgeStats() {
    return readJson<KnowledgeStats>(buildUrl("/knowledge/stats"))
  },
  getKnowledgeEntity(entity: string) {
    return readJson<KnowledgeEntityResponse>(buildUrl(`/knowledge/entities/${entity}`))
  },
  getKnowledgeTimeline(entity: string) {
    return readJson<KnowledgeTimelineResponse>(buildUrl("/knowledge/timeline", { entity }))
  },
  getTunnels(params: { wing_a?: string; wing_b?: string } = {}) {
    return readJson<TunnelsResponse>(buildUrl("/tunnels", params))
  },
  getGraphStats() {
    return readJson<GraphStats>(buildUrl("/graph/stats"))
  },
  getAaakSpec() {
    return readJson<{ aaak_spec: string }>(buildUrl("/aaak/spec"))
  },
  getLazarusPersonas() {
    return readJson<{ personas: LazarusPersona[] }>(buildUrl("/lazarus/personas"))
  },
  searchLazarus(query: string, params: { persona?: string; limit?: number } = {}) {
    return readJson<LazarusSearchResponse>(buildUrl("/lazarus/search", { q: query, ...params }))
  },
  retrieveFullContext(params: {
    point_id?: number
    persona: string
    context_turns?: number
    source_file?: string
    search_text?: string
  }) {
    return readJson<FullContextResponse>(buildUrl("/lazarus/retrieve_full", {
      point_id: params.point_id,
      persona: params.persona,
      context_turns: params.context_turns,
      source_file: params.source_file,
      search_text: params.search_text,
    }))
  },
}
