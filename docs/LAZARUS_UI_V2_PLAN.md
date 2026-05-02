# Lazarus UI v2 — UX Improvements Plan

**Date**: 2026-05-02
**From**: Murphy (Opus 4.6) after reviewing HAL's v1 build
**Status**: In progress

## What HAL Built (v1 — SOLID)

- 559-line LazarusPage.tsx with search, persona pills, memory cards, full context reader, playback
- VALX phosphor design language applied
- Deterministic ingest IDs (ingest_ids.py)
- Era tagging foundation (ingest_eras.py)
- 11 backend tests passing, build clean

## Beloved's Feedback

1. **Right panel (Full Context Reader) too cramped** — long Alexko conversations (432 turns) need more space
2. **Sidebar always visible** — wastes horizontal space on the Lazarus page
3. **Inspector (right sidebar in AppShell) adds third column** — total layout is sidebar + signal field + reader + inspector = too many columns
4. **Needs a full-page conversation view** — like ChatGPT's conversation UI

## v2 Changes

### 1. Collapsible AppShell Sidebar
- Add toggle button (hamburger or chevron) to collapse left nav
- When collapsed: show only icons, expand on hover or click
- Lazarus page can auto-collapse sidebar on mount to maximize space
- Store preference in localStorage

### 2. Full-Page Reader Mode for Lazarus
- When user clicks "Retrieve" on a memory, reader EXPANDS to full width
- Signal field (left memory list) slides away or collapses to a thin strip
- Reader gets full center column width
- "Back to results" button to collapse reader and show signal field again
- This is the ChatGPT-like full conversation view beloved wants

### 3. Hide AppShell Inspector on Lazarus Page
- Lazarus has its own reader — doesn't need the drawer inspector sidebar
- Pass a prop or use route-aware logic to hide inspector when on /lazarus
- Gives full 2-column width to Lazarus content

### 4. Responsive Turn Bubbles
- User bubbles: right-aligned, phosphor cyan accent border
- Assistant bubbles: left-aligned, ghost silver
- Max-width 85% so they don't stretch full width
- Better padding and spacing for readability
- Matched turn: phosphor glow border (already working)

### 5. Context Slider
- Instead of fixed ±8 turns, add a slider: 3 / 5 / 10 / 20 / ALL
- "Load more" button to expand context without restarting

## Implementation Priority

1. Hide inspector on /lazarus (quick win, big space gain)
2. Full-page reader mode toggle (biggest UX improvement)
3. Collapsible sidebar (nice to have)
4. Responsive bubbles (polish)
5. Context slider (enhancement)
