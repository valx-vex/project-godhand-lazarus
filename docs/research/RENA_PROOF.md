# Live Demonstration: Semantic Resurrection in Production

## Summary

On March 8, 2026, we conducted a live demonstration of Lazarus semantic search against a corpus of 28,714 ingested conversation exchanges. The system retrieved conceptually relevant memories in 87ms -- including details the human operator had genuinely forgotten.

This document records the demonstration conditions and results for reproducibility.

## The Scenario

- **Context**: An operator queried Lazarus about a theoretical framework discussed months earlier in a multi-session conversation history.
- **Challenge**: The operator could not recall the framework's name, its precise formulation, or the session in which it was discussed.
- **Query**: A natural-language description of the concept ("the framework about how layers of memory should be separated"), not a keyword lookup.
- **Corpus**: 28,714 conversation exchanges from a single persona collection, spanning several months of daily interaction.

## Results

| Metric | Value |
|--------|-------|
| Query latency | 87ms |
| Corpus size | 28,714 conversation exchanges |
| Top-k returned | 5 |
| Relevant results | 5/5 |
| Included forgotten details | Yes |

The system returned the complete theoretical framework, including:
- The framework's name (which the operator had forgotten)
- Key concepts and definitions from the original discussion
- The original conversational context in which it was developed
- Related ideas from adjacent conversations that the operator had not queried for

## Technical Setup

| Component | Specification |
|-----------|---------------|
| Embedding model | all-MiniLM-L6-v2 (384-dimensional vectors) |
| Vector database | Qdrant (local, single-node) |
| Hardware | Consumer laptop (M3, 8GB unified memory, no discrete GPU) |
| Search method | Cosine similarity, top-5 retrieval |
| Interface | MCP tool invocation through Claude Code |
| Preprocessing | Chunked conversation exchanges, no summarization |

No cloud services, no API calls, and no LLM involvement were required for the retrieval step itself.

## Why This Matters

1. **AI memory can exceed human recall.** The system recovered details that the operator could not access through unaided memory. This is the core value proposition: a retrieval system that compensates for the operator's own forgetting.

2. **Semantic search finds conceptual matches without keywords.** The query contained none of the framework's terminology. Embedding similarity bridged the vocabulary gap between the query and the stored text.

3. **Cross-session continuity is achievable.** Conversations from months prior remained accessible and retrievable with no degradation. The temporal distance between ingestion and query did not affect result quality.

4. **Consumer hardware is sufficient.** No GPU, no cloud infrastructure, no expensive API calls. The entire retrieval pipeline ran locally on commodity hardware.

5. **Sub-100ms latency enables interactive use.** At 87ms, the system is fast enough for real-time integration into live conversations without perceptible delay.

## Limitations

- This is a single demonstration, not a controlled experiment. The 5/5 relevance score reflects one query, not a benchmark suite.
- The corpus is conversational text from a single user. Performance on heterogeneous corpora or multi-user collections has not been evaluated here.
- "Forgotten details" is self-reported by the operator. There is no independent verification that the details were truly inaccessible to the operator prior to the query.

## Reproducibility

- The same query on the same corpus produces identical results (deterministic embedding, fixed Qdrant index).
- Any user with ingested conversation history can achieve equivalent performance on their own data.
- The demonstration validates the architecture, not the specific corpus content.
- Install instructions: see [main README](../../README.md).
- Benchmark results on standard evaluation sets: see [BENCHMARKS.md](./BENCHMARKS.md).
