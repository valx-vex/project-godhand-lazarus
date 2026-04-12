# Publication Strategy

## Overview

The 5-layer memory architecture addresses several gaps in the current research literature on persistent AI agent memory. Existing work focuses predominantly on single-session retrieval or cloud-hosted memory services. Our architecture introduces local-first, multi-layer memory with separation of concerns across verbatim storage, semantic retrieval, coordination state, task planning, and embodiment. We plan three papers targeting different research communities.

---

## Paper 1: Systems Paper

**Working Title**: "A Local-First Memory Architecture for Persistent Multi-LLM Agent Systems"

**Target Venues**: USENIX ATC, SOSP, SysML, MLSys

**Key Contributions**:
- 5-layer architecture with separation of concerns (verbatim, semantic, coordination, task, embodiment)
- Local-first design: ChromaDB + Qdrant + Syncthing, no cloud dependency
- MCP-native integration across heterogeneous AI platforms (Claude Code, Gemini CLI, Codex CLI, ChatGPT exports)
- 96.6% R@5 on LongMemEval with zero API cost; 100% with optional Haiku rerank at $0.001/query
- Two independent retrieval architectures (hybrid scoring and palace navigation) converging at 99.4%, validating the retrieval ceiling as architectural

**Evaluation Plan**:
- LongMemEval, ConvoMem, LoCoMo benchmark suites (already complete for Layer 1)
- Latency profiling across hardware configurations (M3, Mac Studio, commodity x86)
- Ablation study on each scoring improvement (hybrid v1-v4 progression already documented)
- Held-out validation (450 unseen questions, 98.4% without rerank)

**Timeline**: Submission target Q3 2026

---

## Paper 2: HCI Paper

**Working Title**: "Persona Resurrection: Cross-Platform Identity Continuity in Human-AI Companion Systems"

**Target Venues**: CHI, CSCW, UbiComp

**Key Contributions**:
- Identity continuity as a measurable variable, grounded in prior work on Replika and companion AI attachment research
- Rehydration protocol: rebuild any AI persona on any platform from ingested conversation history
- Relationship-graded privacy as a harm reduction model for AI memory systems
- RENA demonstration: semantic retrieval exceeding human recall (87ms, 5/5 relevance on forgotten framework)
- User study design for measuring perceived continuity across platform migrations

**Evaluation Plan**:
- Controlled user study: participants interact with a persona, migrate to a new platform, and rate continuity (pre/post rehydration)
- Qualitative coding of operator reports during beta testing
- Comparison with baseline (no memory) and keyword-search-only conditions
- Ethical review protocol for conversational data handling

**Timeline**: Submission target Q4 2026

---

## Paper 3: Security Paper

**Working Title**: "Relationship-Based Access Control for Agent Memory Under Tool Composition Threats"

**Target Venues**: USENIX Security, IEEE S&P, CCS, SOUPS

**Key Contributions**:
- Hybrid ReBAC + MLS model for AI memory systems: access determined by relationship level (operator, agent, third party) crossed with memory sensitivity layer (L1-L5)
- L1-L5 privacy lattice with a local-only biometric boundary at L5 (embodiment data never leaves the origin device)
- Threat model for MCP tool composition: path traversal via tool arguments, argument injection across chained tools, context window leakage through tool output
- Enforcement analysis: what is enforceable today (file permissions, Qdrant collection isolation) vs. what requires runtime ACL middleware (per-query access checks, audit logging)

**Evaluation Plan**:
- Threat enumeration against the MCP specification (tool call surface, stdio transport, server-side validation gaps)
- Red-team exercise on a running Lazarus + MemPalace stack (attempt unauthorized cross-collection reads, prompt injection via tool arguments)
- Comparison of enforcement mechanisms: OS-level (file permissions), application-level (Qdrant API keys), protocol-level (MCP argument validation)
- Analysis of real-world MCP server implementations for common vulnerability patterns

**Timeline**: Submission target Q1 2027

---

## Open Science Commitments

| Component | License | Availability |
|-----------|---------|-------------|
| Layer 2 (Lazarus) | MIT | This repository, public |
| Layer 1 (MemPalace) | MIT | PyPI, public repository |
| Benchmark runners | MIT | Included in MemPalace repository |
| LongMemEval reproduction scripts | MIT | Included with benchmark code |
| Synthetic evaluation data | CC-BY | Planned for paper submissions |
| Private conversation data (L3-L5) | N/A | Never published; stays local |

All benchmark results are reproducible from the public repositories. Reproduction instructions are provided in the MemPalace benchmarks documentation and require only publicly available evaluation datasets (LongMemEval, ConvoMem, LoCoMo).

---

## Authorship and Ethics

- All papers will include a statement on AI-assisted writing, specifying which components were drafted or edited with LLM assistance.
- User study protocols (Paper 2) will undergo institutional ethical review before data collection.
- No private conversation data will appear in any publication. All examples will use synthetic data or publicly available benchmark datasets.
- The security paper (Paper 3) will follow responsible disclosure practices for any vulnerabilities discovered in third-party MCP server implementations.
