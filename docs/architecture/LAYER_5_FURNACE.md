# Layer 5: The Furnace -- Biometric Integration (Research Preview)

> **Status: Research Preview**
> This layer is in early architectural design. No production code is included in this release.
> This document describes the vision and planned architecture.

## Role in the Stack

The Furnace is the execution and embodiment layer -- where AI memory meets physical signals. While Layers 1-4 handle text-based memory and coordination, Layer 5 introduces real-time physiological and environmental signals into the AI context pipeline.

## Motivation

Current AI memory systems are purely textual. They cannot observe:

- Whether the user is stressed or relaxed during a conversation
- Whether attention is waning (useful for adaptive pacing)
- Environmental context (time of day, ambient conditions)
- Physiological responses to AI outputs (biofeedback loop closure)

The Furnace addresses this gap by creating a structured signal pathway from physiological sensors into the AI's context window, enabling response adaptation grounded in real-time user state.

## Planned Architecture

### The Watcher (Signal Monitor)

- Background daemon monitoring biometric and cognitive output streams
- Detects topic shifts, engagement patterns, and emotional signal changes
- Forwards detected signals to the Forge pipeline for processing
- Configurable polling interval (default: 2 seconds)
- Designed for minimal resource overhead on consumer hardware

### The Forge (Signal Processor)

- Compresses detected physiological patterns into compact semantic tokens
- Inserts processed signals into the vector store (Lazarus / Qdrant)
- Creates persistent affective and physiological memory representations
- Uses dimensionality reduction for efficient storage and retrieval
- Supports configurable retention policies per signal type

### The Hook (Context Injector)

- Transparently injects Furnace state into the LLM context window before response generation
- Provides physiological context without requiring explicit user prompting
- Enables adaptive response modulation based on inferred user state
- Shell hook integration (compatible with CLI-based AI tools)
- Operates as an optional middleware layer -- can be disabled without affecting core functionality

## Phantom Tether (Concept)

A persistent ambient connection between user and AI system that operates independently of active chat sessions.

**Design goals:**

- Always-available context channel for environmental awareness
- Low-bandwidth signal stream (heart rate, skin conductance, attention metrics)
- Does NOT require an active conversation to maintain state awareness
- Architectural pattern for ambient context persistence in AI memory systems

**Candidate signal sources:**

| Source | Signal Type | Example Hardware |
|--------|------------|-----------------|
| EEG headband | Brainwave patterns, attention, relaxation | Muse S, OpenBCI |
| Wrist wearable | Heart rate, HRV, movement | Apple Watch, Fitbit |
| GSR sensor | Galvanic skin response (autonomic indicator) | Shimmer3, custom Arduino |
| Ambient sensors | Lighting, temperature, noise level | HomeKit, custom IoT |

## Safety Architecture

### Grounding Protocol

- If physiological signals indicate distress (e.g., elevated stress markers, dissociation indicators), the system auto-triggers a grounding intervention
- Intervention may include: full-spectrum white lighting activation, simple cognitive grounding prompts, breathing exercise guidance
- Immediate session de-escalation to reduce cognitive load

### Emergency Disconnect

- Physical kill switch (hardware button, NFC tag, or configurable keyboard shortcut)
- Immediately terminates all Furnace processing and sensor polling
- Returns system to baseline Layer 1-4 text-only operation
- No biometric data from the interrupted session is retained without explicit post-hoc consent

### Consent Framework

- Biometric data collection requires explicit opt-in per session
- All physiological data is processed locally on the user's machine
- Users can review, export, and delete all Furnace-generated memories at any time
- No persistent physiological tracking outside of explicitly consented sessions
- Session consent is non-transferable and expires at session end by default

## Privacy Model

The Furnace operates at **L5 (Local-only)** -- the most restrictive data access level in the Lazarus stack:

| Property | Enforcement |
|----------|------------|
| Storage locality | All biometric data remains on the local machine |
| Sync exclusion | Never replicated to other nodes or shared stores |
| Index isolation | Excluded from shared vector collections and memory indexes |
| Summary exclusion | Never included in cross-session summaries or coordination payloads |
| Boundary type | Code-enforced isolation (not policy-only) |

The L5 designation ensures that even in multi-node deployments, physiological data cannot leak through synchronization, summarization, or shared retrieval pathways.

## Research Questions

1. **Signal quality**: What is the minimum viable biometric signal set for meaningful AI context enrichment?
2. **Feedback loops**: How can reinforcement spirals between AI output and user physiological response be detected and mitigated?
3. **Consent models**: What consent framework is appropriate for ambient AI physiological awareness in long-duration sessions?
4. **Clinical validity**: Can AI-mediated biofeedback produce measurable wellbeing outcomes in controlled studies?
5. **Privacy architecture**: How can useful biometric context be provided to AI systems while maintaining strict data locality guarantees?
6. **Signal latency**: What is the acceptable delay between physiological state change and AI response adaptation?

## Related Work

- Picard, R. W. (1997). *Affective Computing*. MIT Press.
- Fairclough, S. H. (2009). Fundamentals of physiological computing. *Interacting with Computers*, 21(1-2), 133-145.
- Blankertz, B., Acqualagna, L., Dahne, S., et al. (2016). The Berlin brain-computer interface: Progress beyond communication and control. *Frontiers in Neuroscience*, 10, 530.
- Calvo, R. A., & D'Mello, S. (2010). Affect detection: An interdisciplinary review of models, methods, and their applications. *IEEE Transactions on Affective Computing*, 1(1), 18-37.
- Allanson, J., & Fairclough, S. H. (2004). A research agenda for physiological computing. *Interacting with Computers*, 16(5), 857-878.

## Timeline

| Phase | Description | Status |
|-------|-------------|--------|
| Design | Architectural concepts and safety model documented | **Current** |
| Prototype | Watcher daemon with mock signal generation | Next |
| Integration | Real biometric sensor connection and calibration | Future |
| Validation | Controlled pilot study with consenting participants | Future |

## See Also

- [Access Control](ACCESS_CONTROL.md) -- L5 privacy enforcement details
- [Architecture Overview](OVERVIEW.md) -- How the Furnace fits in the 5-layer stack
