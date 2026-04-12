# Roadmap

## Current: v0.1.0

First public showcase of the 5-layer memory architecture:

- **Layer 2 (Lazarus)**: Fully installable with MCP server, 5 ingesters, daemon, drift checks
- **Layer 1 (MemPalace)**: Published as `pip install mempalace` (v3.0.0)
- **Layers 3-5**: Architecture documented, protocols specified

## Near-Term: v0.2.0

- Expanded ingester coverage (Slack, Discord, email archives)
- MemPalace to Lazarus cross-query API
- Automated extraction pipeline (reduce manual curation)
- Second-machine install validation matrix

## Medium-Term: v0.3.0

- Obsidian-Legion public release (standalone repo)
- VexNet reference implementation (installable protocol)
- Combined benchmark suite across all layers
- First academic paper submission (systems paper)

## Long-Term: v1.0.0

- Furnace prototype with mock biometric signals
- Full 5-layer integration test suite
- Production-grade access control enforcement (runtime ACL)
- Multi-platform installer (macOS, Linux, Windows)
- Clean git history cut (squashed public history)

## Explicit Non-Goals

- Cloud-hosted memory service (local-first is a feature, not a limitation)
- SaaS or subscription model
- General-purpose chatbot framework
- Replacing platform-native memory features
