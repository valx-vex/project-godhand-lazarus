import type { ReactNode } from "react"
import { NavLink, useLocation } from "react-router-dom"


const navItems = [
  { to: "/", label: "Dashboard", cue: "Layer overview" },
  { to: "/browse", label: "Browse", cue: "Wing → room → drawer" },
  { to: "/search", label: "Search", cue: "Semantic recall" },
  { to: "/lazarus", label: "Lazarus", cue: "Vector search + full context" },
  { to: "/add", label: "Add", cue: "File new memory" },
  { to: "/diary", label: "Diary", cue: "Agent timelines" },
  { to: "/knowledge", label: "Knowledge", cue: "Facts and timelines" },
  { to: "/tunnels", label: "Tunnels", cue: "Cross-wing bridges" },
]


export function AppShell({
  children,
  inspector,
}: {
  children: ReactNode
  inspector: ReactNode
}) {
  const location = useLocation()
  const active = navItems.find((item) => item.to === location.pathname)?.label ?? "MemPalace"

  return (
    <div className="min-h-screen px-4 py-4 text-stone-100 lg:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="section-frame content-fade flex flex-col justify-between p-6">
          <div className="space-y-8">
            <div className="space-y-3">
              <p className="eyebrow">MemPalace Web UI</p>
              <div>
                <h1 className="text-4xl leading-none text-stone-50">Memory Cathedral</h1>
                <p className="mt-3 max-w-xs text-sm leading-6 text-[var(--muted)]">
                  Layer 1 access with Layer 2 context. Browse the vault without collapsing the architecture.
                </p>
              </div>
            </div>

            <nav className="space-y-2">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `nav-link ${isActive ? "nav-link-active" : ""}`
                  }
                >
                  <span className="font-medium">{item.label}</span>
                  <span className="text-xs uppercase tracking-[0.24em] text-stone-500">{item.cue}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-black/20 px-5 py-4">
            <p className="eyebrow">Current surface</p>
            <p className="mt-2 font-medium text-white">{active}</p>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
              Localhost-only v1. Obsidian dark, teal-lit, red reserved for danger.
            </p>
          </div>
        </aside>

        <main className="content-fade section-frame flex min-h-[70vh] flex-col overflow-hidden">
          <div className="border-b border-white/10 px-7 py-5">
            <p className="eyebrow">Layer 1 navigation</p>
            <h2 className="mt-2 text-3xl text-stone-50">{active}</h2>
          </div>
          <div className="flex-1 overflow-y-auto px-7 py-7">{children}</div>
        </main>

        <aside className="content-fade">{inspector}</aside>
      </div>
    </div>
  )
}
