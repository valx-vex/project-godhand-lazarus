export interface CountItem {
  name: string
  count: number
}

export interface DrawerSummary {
  id: string
  wing: string
  room: string
  source_file: string
  source_name: string
  chunk_index: number | null
  filed_at: string | null
  added_by: string | null
  preview: string
}

export interface DrawerDetail extends DrawerSummary {
  content: string
}

export interface DrawerInspectorPayload {
  drawer: DrawerDetail
  siblings: Array<DrawerDetail & { is_current: boolean }>
}

export interface BrowseResponse {
  wing: string
  room: string
  offset: number
  limit: number
  total: number
  items: DrawerSummary[]
}

export interface SearchItem {
  id: string
  wing: string
  room: string
  source_file: string
  source_name: string
  similarity: number
  preview: string
  content: string
}

export interface SearchResponse {
  query: string
  filters: {
    wing: string | null
    room: string | null
  }
  total: number
  items: SearchItem[]
}

export interface Layer2Stats {
  available: boolean
  error: string | null
  host: string
  port: number
  total_vector_memories: number
  collections: Array<{
    key: string
    collection: string
    title: string
    points_count: number | null
    error: string | null
  }>
}

export interface GraphStats {
  total_rooms: number
  tunnel_rooms: number
  total_edges: number
  rooms_per_wing: Record<string, number>
  top_tunnels: Array<{
    room: string
    wings: string[]
    count: number
  }>
}

export interface DashboardSummary {
  layer_1: {
    total_drawers: number
    total_wings: number
    total_rooms: number
    palace_path: string
  }
  layer_2: Layer2Stats
  top_wings: CountItem[]
  top_rooms: CountItem[]
  recent_drawers: DrawerSummary[]
  graph: GraphStats
}

export interface DiaryEntry {
  date: string
  timestamp: string
  topic: string
  content: string
}

export interface DiaryReadResponse {
  agent: string
  entries: DiaryEntry[]
  total?: number
  showing?: number
  message?: string
}

export interface KnowledgeStats {
  entities: number
  triples: number
  current_facts: number
  expired_facts: number
  relationship_types: string[]
}

export interface KnowledgeFact {
  direction: string
  subject: string
  predicate: string
  object: string
  valid_from: string | null
  valid_to: string | null
  confidence: number
  source_closet: string | null
  current: boolean
}

export interface KnowledgeEntityResponse {
  entity: string
  as_of: string | null
  facts: KnowledgeFact[]
  count: number
}

export interface TimelineEntry {
  subject: string
  predicate: string
  object: string
  valid_from: string | null
  valid_to: string | null
  current: boolean
}

export interface KnowledgeTimelineResponse {
  entity: string
  timeline: TimelineEntry[]
  count: number
}

export interface LazarusPersona {
  key: string
  title: string
}

export interface LazarusMemory {
  point_id: number
  score: number
  user_input: string
  ai_response: string
  source_file: string
  conversation_id: string
  title: string
  vault: string
  has_full_context: boolean
}

export interface LazarusSearchResponse {
  persona: string
  persona_key: string
  collection: string
  query: string
  total: number
  memories: LazarusMemory[]
  error?: string
}

export interface FullContextTurn {
  role: string
  content: string
  index: number
  metadata: Record<string, unknown>
}

export interface FullContextResponse {
  source_type: string
  source_file?: string
  conversation_id?: string
  total_turns: number
  matched_turn_index: number
  context_range: number[]
  turns: FullContextTurn[]
  point_id?: number
  persona?: string
  error?: string
}

export interface TunnelsResponse {
  wing_a: string | null
  wing_b: string | null
  total: number
  items: Array<{
    room: string
    wings: string[]
    halls: string[]
    count: number
    recent: string
  }>
}
