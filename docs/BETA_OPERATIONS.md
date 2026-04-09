# Quiet Beta Operations

## Who This Beta Is For

This beta is aimed at local-first LLM users who:

- are comfortable with a terminal
- already use or want to use Claude Code, Gemini CLI, or Codex CLI
- care about recovering old ideas across tools and model generations
- can tolerate a product that is real but still operationally young

## What Feedback Is Most Valuable

The highest-value reports are:

- install failures on otherwise normal machines
- importer edge cases from real exports and session logs
- places where the docs assume too much context
- places where the support bundle is missing the detail needed to debug quickly

## GitHub Discussion Mapping

GitHub Discussions is the structured feedback layer:

- `Announcements` for maintainer updates
- `General` for beta feedback
- `Q&A` for install help and usage questions
- `Show and tell` for use cases and stack showcases
- `Ideas` for roadmap and feature discussion

## Discord Structure

The initial Discord layout should be:

- `#announcements`
- `#start-here`
- `#install-help`
- `#bug-triage`
- `#feature-ideas`
- `#show-your-stack`
- `#contributors`

Discord is for fast conversation. GitHub is where the project remembers.

## What To Attach When Asking For Help

Always attach or paste the output from:

```bash
./scripts/collect_support_bundle.sh
```

That bundle should be the default first response in beta support. Freeform
paragraphs without machine state slow down debugging for everyone.

## Supported In Beta

During quiet beta we are explicitly supporting:

- local Qdrant-backed semantic memory
- ChatGPT, Claude Code, Gemini CLI, and Codex CLI ingestion
- Lazarus MCP integration for Claude, Gemini, and Codex
- layered use with MemPalace and continuity

Anything beyond that may be valid future work, but it is not the beta promise.
