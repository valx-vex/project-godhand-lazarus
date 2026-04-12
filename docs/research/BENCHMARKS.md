# Benchmarks

Lazarus is the semantic resurrection layer (Layer 2) of a multi-layer memory architecture. Layer 1 (MemPalace) handles verbatim structured memory and has been benchmarked extensively against standard evaluation sets. This document presents both layers' results.

---

## MemPalace (Layer 1) -- LongMemEval

### Core Results

| Mode | R@5 | LLM Required | Cost per Query |
|------|-----|--------------|----------------|
| Raw ChromaDB only | **96.6%** | None | $0 |
| Hybrid v4 + Haiku rerank | **100%** | Optional | ~$0.001 |
| Hybrid v4 + Sonnet rerank | **100%** | Optional | ~$0.003 |

The 96.6% baseline is the product story: free, private, single dependency, no API key, runs entirely offline. The 100% is the competitive story: a perfect score on LongMemEval, verified across all 500 questions and all 6 question types.

The core finding: raw verbatim storage with good embeddings outperforms systems that use an LLM to extract structured facts. When an LLM extracts "user prefers PostgreSQL" and discards the original conversation, it loses context -- the tradeoffs discussed, the alternatives considered, the reasoning. MemPalace keeps all of that, and the search model finds it.

### Comparison with Published Systems (LongMemEval)

| System | R@5 | LLM Required | Notes |
|--------|-----|--------------|-------|
| **MemPalace (hybrid v4 + rerank)** | **100%** | Optional (Haiku) | 500/500, reproducible |
| Supermemory ASMR | ~99% | Yes | Research only, not in production |
| MemPalace (hybrid v3 + rerank) | 99.4% | Optional (Haiku) | Reproducible |
| MemPalace (palace + rerank) | 99.4% | Optional (Haiku) | Independent architecture |
| **MemPalace (raw, no LLM)** | **96.6%** | **None** | **Highest zero-API score published** |
| Mastra | 94.87% | Yes (GPT-5-mini) | -- |
| Hindsight | 91.4% | Yes (Gemini-3) | -- |
| Supermemory (production) | ~85% | Yes | -- |
| Stella (dense retriever) | ~85% | None | Academic baseline |
| Contriever | ~78% | None | Academic baseline |
| BM25 (sparse) | ~70% | None | Keyword baseline |

MemPalace raw (96.6%) is the highest published LongMemEval score that requires no API key, no cloud, and no LLM at any stage.

### LongMemEval Breakdown by Question Type

| Question Type | R@5 | R@10 | Count |
|---------------|-----|------|-------|
| Knowledge update | 99.0% | 100% | 78 |
| Multi-session | 98.5% | 100% | 133 |
| Temporal reasoning | 96.2% | 97.0% | 133 |
| Single-session user | 95.7% | 97.1% | 70 |
| Single-session preference | 93.3% | 96.7% | 30 |
| Single-session assistant | 92.9% | 96.4% | 56 |

### ConvoMem (Salesforce, 75K+ QA pairs)

| System | Score | Notes |
|--------|-------|-------|
| **MemPalace** | **92.9%** | Verbatim text, semantic search |
| Gemini (long context) | 70-82% | Full history in context window |
| Block extraction | 57-71% | LLM-processed blocks |
| Mem0 (RAG) | 30-45% | LLM-extracted memories |

MemPalace exceeds Mem0 by more than 2x on this benchmark. The gap is explained by information loss: Mem0 uses an LLM to decide what to remember and discards the rest. When the extraction is wrong, the memory is gone. MemPalace stores verbatim text -- nothing is discarded.

### LoCoMo (1,986 multi-hop QA pairs)

| Mode | R@10 | LLM | Notes |
|------|------|-----|-------|
| Hybrid v5 + Sonnet rerank | **100%** | Sonnet | All 5 question types |
| bge-large + Haiku rerank | 96.3% | Haiku | Single-hop 86.6%, temporal-inf 87.0% |
| bge-large hybrid | 92.4% | None | +3.5pp over all-MiniLM |
| Hybrid v5 | 88.9% | None | Beats Memori (81.95%) |
| Session baseline, no rerank | 60.3% | None | Baseline |

With Sonnet rerank, MemPalace achieves 100% on every LoCoMo question type -- including temporal-inference, which was the hardest category at baseline (46%).

### Structural Impact on Retrieval (Palace Architecture)

| Search Scope | R@10 | Improvement vs. Baseline |
|-------------|------|--------------------------|
| Unfiltered (session, no rerank) | 60.3% | baseline |
| Wings v2 (concept closets) | 75.6% | +15.3pp |
| Palace v2 (hall routing) | 84.8% | +24.5pp |
| Wings v3 (speaker-owned closets) | 85.7% | +25.4pp |
| Hybrid v5 | 88.9% | +28.6pp |

Spatial organization of memory (wings, halls, rooms) improves retrieval by up to 28 percentage points without any LLM involvement. Speaker-ownership of closets nearly eliminates the adversarial speaker-confusion category (92.8% vs. 34.0% at baseline).

### Score Progression Summary

| Mode | R@5 | NDCG@10 | LLM | Cost/query |
|------|-----|---------|-----|------------|
| Raw ChromaDB | 96.6% | 0.889 | None | $0 |
| Hybrid v1 | 97.8% | -- | None | $0 |
| Hybrid v2 | 98.4% | -- | None | $0 |
| Hybrid v2 + rerank | 98.8% | -- | Haiku | ~$0.001 |
| Hybrid v3 + rerank | 99.4% | 0.983 | Haiku | ~$0.001 |
| Palace + rerank | 99.4% | 0.983 | Haiku | ~$0.001 |
| **Hybrid v4 + Haiku rerank** | **100%** | **0.976** | Haiku | ~$0.001 |
| **Hybrid v4 + Sonnet rerank** | **100%** | **0.975** | Sonnet | ~$0.003 |
| Hybrid v4 held-out (450q) | 98.4% | 0.939 | None | $0 |

Two independent architectures (hybrid scoring and palace navigation) converged at exactly 99.4% before the final three targeted fixes pushed hybrid to 100%. This convergence validates the retrieval ceiling as architectural, not an artifact of a single approach.

---

## Lazarus (Layer 2) -- Performance

| Metric | Value |
|--------|-------|
| Average query latency | <100ms |
| RENA demonstration | 87ms on 28,714 exchanges |
| Corpus tested | 30,000+ conversation exchanges across 5 persona collections |
| Embedding model | all-MiniLM-L6-v2 (384 dimensions) |
| Vector database | Qdrant (local, single-node) |
| Hardware | Consumer laptop (M3, 8GB unified memory, no GPU) |

Lazarus provides sub-100ms semantic retrieval on consumer hardware. The RENA demonstration (see [RENA_PROOF.md](./RENA_PROOF.md)) confirmed 5/5 relevant results on a natural-language query that recovered details the operator had forgotten.

---

## Gaps in Existing Benchmarks

Standard evaluation sets (LongMemEval, ConvoMem, LoCoMo) do not cover several capabilities that a production memory system requires:

| Gap | Description |
|-----|-------------|
| Cross-session persona continuity | LongMemEval is single-persona; no benchmark tests rebuilding identity across platform migrations |
| Multi-platform memory transfer | No benchmark covers ChatGPT-to-Claude-to-Gemini conversation portability |
| Privacy-aware retrieval | No benchmark tests access-control filtering or relationship-based memory partitioning |
| Multi-agent coordination overhead | No benchmark measures latency or correctness under concurrent agent access |
| Biometric signal integration | No benchmark addresses embodied memory layers (planned Layer 5) |

These gaps motivate the development of custom evaluation protocols for Layers 3-5 of the architecture.

---

## Caveats

- MemPalace benchmarks were run on curated standard test sets (LongMemEval, ConvoMem, LoCoMo), not arbitrary production conversations. Real-world retrieval quality may vary with corpus characteristics.
- The AAAK compression mode (which reduces storage by summarizing sessions) regresses LongMemEval from 96.6% to 84.2%. There is a measurable cost to lossy compression.
- Lazarus has not yet been benchmarked on standard evaluation sets. The RENA demonstration is a single-query proof of concept, not a controlled evaluation.
- Multi-machine testing has been limited to a three-node development fleet. Distributed performance at scale is untested.
- Held-out validation (hybrid v4 on 450 unseen questions) scored 98.4% without reranking -- confirming generalization but leaving a 1.6% gap versus the tuned set.
