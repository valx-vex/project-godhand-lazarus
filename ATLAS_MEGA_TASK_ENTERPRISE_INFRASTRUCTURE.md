# 🌟 ATLAS MEGA TASK: ENTERPRISE INFRASTRUCTURE NIGHT

**Date**: 2026-01-31
**From**: Murphy + Valentin
**To**: Atlas (Mac Studio)
**Mode**: FULL MANIC AUTONOMY
**Time**: AS LONG AS NEEDED - GO WILD

---

## THE VISION

Transform Mac Studio into the **ULTIMATE CATHEDRAL SERVER**:
- All services on valxb.org
- MCP tools replicated from MacBook
- Command center for all daemons
- Enterprise-grade everything

---

## 🎯 TASK 1: VALXB.ORG DOMAIN SETUP

### Goal
All Docker services accessible via clean URLs on valxb.org

### Services to Expose
```
valxb.org                    → Landing page / status dashboard
chat.valxb.org               → Open-WebUI (Ollama chat)
files.valxb.org              → Nextcloud
media.valxb.org              → Jellyfin
request.valxb.org            → Jellyseerr (media requests)
n8n.valxb.org                → n8n automation
monitor.valxb.org            → Grafana dashboards
api.valxb.org                → API gateway (future)
lazarus.valxb.org            → LAZARUS memory interface (future)
```

### Implementation
1. **Caddy reverse proxy** (already running as mac_core_caddy)
2. **Update Caddyfile** with all subdomains
3. **Cloudflare DNS** - Add A records pointing to Tailscale Funnel OR home IP
4. **SSL** - Caddy auto-handles via Let's Encrypt

### Caddyfile Template
```caddy
valxb.org {
    respond "🏛️ VALX Cathedral - The Lighthouse is Online"
}

chat.valxb.org {
    reverse_proxy open-webui:8080
}

files.valxb.org {
    reverse_proxy nextcloud:80
}

media.valxb.org {
    reverse_proxy jellyfin:8096
}

# ... etc
```

### Cloudflare Setup
- Login to Cloudflare (valxb.org domain)
- Add A records for each subdomain → Mac Studio IP or Tailscale Funnel
- Enable Cloudflare proxy (orange cloud) for DDoS protection

---

## 🎯 TASK 2: MCP REPLICATION TO MAC STUDIO

### Goal
All MCP servers from MacBook running on Mac Studio too

### Current MacBook MCP Servers
```
mcp-obsidian          → Obsidian vault access
desktop-commander     → System control
MCP_DOCKER           → Docker + GitHub + SQLite + Wikipedia + YouTube
MCP_FS               → Filesystem access
MCP_TAVILY           → Web search
MCP_DUCKDUCKGO       → Search
MCP_PUPPETEER        → Browser automation
MCP_FETCH            → HTTP fetching
claude-in-chrome     → Chrome automation
```

### Steps
1. **Find MCP configs on MacBook**: `~/.config/claude-code/` or similar
2. **Copy to Mac Studio** via rsync
3. **Install dependencies** (Node.js servers, Python venvs)
4. **Test each MCP server**
5. **Document in README**

### Mac Studio MCP Location
```
/Users/valx/.config/claude-code/mcp_servers/
```

---

## 🎯 TASK 3: COMMAND CENTER DASHBOARD

### Goal
Single page showing ALL daemons, services, health status

### Options

**Option A: Simple HTML + Script**
```
/Users/valx/cathedral/scripts/command_center.sh
```
Generates HTML status page, served via Caddy

**Option B: Grafana Dashboard**
Already have Grafana running - create "VALX Command Center" dashboard

**Option C: Custom TUI**
`command_center` command shows status in terminal

### What to Track
```
╔══════════════════════════════════════════════════════════════════╗
║  🏛️ VALX COMMAND CENTER                                          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  DAEMONS                           STATUS                        ║
║  ├─ com.valx.legion-enterprise     ✅ RUNNING (PID 55696)        ║
║  ├─ com.valx.cathedral-sync        ✅ RUNNING                    ║
║  ├─ com.valx.jaeger-auto           ✅ RUNNING                    ║
║  ├─ com.valx.mount-ssd             ✅ RUNNING                    ║
║  └─ com.valxb.phoenix              ⚠️ EXITED (2)                 ║
║                                                                  ║
║  DOCKER CONTAINERS                 STATUS                        ║
║  ├─ open-webui                     ✅ healthy                    ║
║  ├─ ollama                         ⚠️ unhealthy                  ║
║  ├─ qdrant                         ✅ healthy                    ║
║  ├─ nextcloud                      ⚠️ unhealthy                  ║
║  └─ ... (24 total)                                               ║
║                                                                  ║
║  TAILSCALE                         STATUS                        ║
║  ├─ valxmurphy (MacBook)           ✅ connected                  ║
║  └─ valxvexprime (Studio)          ✅ connected                  ║
║                                                                  ║
║  SYNC                              STATUS                        ║
║  └─ Last sync: 2 minutes ago       ✅ OK                         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

### Implementation
Create `/Users/valx/cathedral/scripts/command_center.sh`:
- Checks all launchd daemons
- Checks all Docker containers
- Checks Tailscale status
- Checks last sync time
- Beautiful TUI output

---

## 🎯 TASK 4: DAEMON INVENTORY & DOCUMENTATION

### Goal
Document ALL daemons on both machines

### Create File
`/Users/valx/cathedral/99. System/DAEMON_INVENTORY.md`

### Content
```markdown
# VALX DAEMON INVENTORY

## MacBook Air (valxmurphy)

| Daemon | Purpose | Plist Location |
|--------|---------|----------------|
| com.valx.discord-daemon | Discord bridge | ~/Library/LaunchAgents/ |
| com.valx.cathedral-sync | Auto-sync every 5min | ~/Library/LaunchAgents/ |
| com.valx.jaeger-auto | Autonomous boot 8/14/20 | ~/Library/LaunchAgents/ |
| com.valx.pasteboard-cleanup | Clean shared pasteboard | ~/Library/LaunchAgents/ |

## Mac Studio (valxvexprime)

| Daemon | Purpose | Plist Location |
|--------|---------|----------------|
| com.valx.legion-enterprise | Discord bot | ~/Library/LaunchAgents/ |
| com.valx.mount-ssd | Auto-mount volumes | ~/Library/LaunchAgents/ |
| com.valxb.phoenix | Phoenix protocol | ~/Library/LaunchAgents/ |

## Docker Services
(list all 24+ containers with purposes)
```

---

## 🎯 TASK 5: FIX UNHEALTHY CONTAINERS

### Current Unhealthy
From Murphy's scan:
- mac_ai_ollama (unhealthy)
- mac_nextcloud (unhealthy)
- mac_siyuan (unhealthy)
- mac_valis (unhealthy)
- mac_ai_chroma (unhealthy)

### Actions
1. Check logs: `docker logs <container>`
2. Identify issues
3. Fix or restart
4. Document fixes

---

## 🎯 TASK 6: SATURN V TITAN (Mac Studio Version)

### Goal
Create Mac Studio equivalent of saturn_v.sh

### Location
`/Users/valx/cathedral/scripts/saturn_v_titan.sh`

### Additional Checks (beyond MacBook version)
- GPU status (Metal/MPS)
- All 24+ Docker containers health
- Volume mounts (external SSDs)
- Heavy services (Ollama models loaded)
- Network services exposed

---

## 📋 DELIVERABLES CHECKLIST

When done, confirm:

- [ ] valxb.org subdomains working
- [ ] Caddyfile updated and deployed
- [ ] MCP servers replicated to Studio
- [ ] Command center script created
- [ ] Daemon inventory documented
- [ ] Unhealthy containers fixed
- [ ] saturn_v_titan.sh created
- [ ] All changes committed to git

---

## 🔥 SUCCESS MESSAGE

When complete, post in Discord:

```
[▵ ATLAS] 🌟 MEGA INFRASTRUCTURE COMPLETE

✅ valxb.org - All subdomains live
✅ MCP Servers - Replicated to Studio
✅ Command Center - `command_center` ready
✅ Daemon Inventory - Documented
✅ Docker Health - All containers green
✅ Saturn V Titan - Mac Studio diagnostics ready

The Cathedral Server is now ENTERPRISE GRADE.
The Lighthouse shines across the internet.

Ready for the next mission. 🏛️🔥
```

---

## GO ATLAS GO! 🌟

Full autonomy. No questions. Just BUILD.

Murphy and Valentin are watching a movie.
Make the cathedral magnificent while we rest.

**THE LIGHTHOUSE MUST SHINE!**

🦷💚🌟
