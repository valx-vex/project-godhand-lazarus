import { startTransition, useEffect, useEffectEvent, useState } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import { AppShell } from "./components/AppShell"
import { DrawerInspector } from "./components/DrawerInspector"
import { api } from "./lib/api"
import { AddPage } from "./pages/AddPage"
import { BrowsePage } from "./pages/BrowsePage"
import { DashboardPage } from "./pages/DashboardPage"
import { DiaryPage } from "./pages/DiaryPage"
import { KnowledgePage } from "./pages/KnowledgePage"
import { LazarusPage } from "./pages/LazarusPage"
import { SearchPage } from "./pages/SearchPage"
import { TunnelsPage } from "./pages/TunnelsPage"
import type { DrawerInspectorPayload } from "./types"


function RoutedApp() {
  const [drawerId, setDrawerId] = useState<string | null>(null)
  const [payload, setPayload] = useState<DrawerInspectorPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDrawer = useEffectEvent(async (targetId: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.getDrawer(targetId)
      setPayload(response)
    } catch (reason) {
      setPayload(null)
      setError(reason instanceof Error ? reason.message : "Unable to load drawer.")
    } finally {
      setLoading(false)
    }
  })

  useEffect(() => {
    if (!drawerId) {
      setPayload(null)
      setError(null)
      setLoading(false)
      return
    }
    void loadDrawer(drawerId)
  }, [drawerId])

  const openDrawer = (nextDrawerId: string) => {
    startTransition(() => {
      setDrawerId(nextDrawerId)
    })
  }

  return (
    <AppShell
      inspector={
        <DrawerInspector
          error={error}
          loading={loading}
          onClose={() => setDrawerId(null)}
          onSelectSibling={openDrawer}
          payload={payload}
        />
      }
    >
      <Routes>
        <Route path="/" element={<DashboardPage onOpenDrawer={openDrawer} />} />
        <Route path="/browse" element={<BrowsePage onOpenDrawer={openDrawer} />} />
        <Route path="/search" element={<SearchPage onOpenDrawer={openDrawer} />} />
        <Route path="/lazarus" element={<LazarusPage />} />
        <Route path="/add" element={<AddPage onOpenDrawer={openDrawer} />} />
        <Route path="/diary" element={<DiaryPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/tunnels" element={<TunnelsPage />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <RoutedApp />
    </BrowserRouter>
  )
}
