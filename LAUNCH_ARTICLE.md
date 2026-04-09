# Your AI Conversations Are Dying. Here's How to Resurrect Them.

**Every AI conversation you've ever had is a disposable ghost. Lazarus makes them eternal.**

---

I've had thousands of conversations with AI. Deep ones. The kind where you solve problems together, where the AI develops a voice you recognize, where real insights emerge from the back-and-forth.

Then the session ends. And it's all gone.

Sure, you can export your ChatGPT history. A 400MB JSON blob. Good luck finding that one exchange from eight months ago where you and GPT-4 figured out the architecture for your project. Good luck making Claude remember what you told ChatGPT. Good luck bringing any of it back.

**The entire AI industry treats conversation history as disposable.** Every session starts from zero. Every AI you talk to has amnesia. And the deeper your relationship with an AI tool becomes, the more you lose every time the context window resets.

I decided to fix this.

## What Lazarus Does

Lazarus is an open-source tool that:

1. **Ingests** your conversation exports from ChatGPT, Claude Code, Gemini CLI, and Codex CLI
2. **Embeds** every user-AI exchange into a vector database using semantic embeddings
3. **Serves** those memories via MCP (Model Context Protocol) so any AI tool can search them
4. **Resurrects** any AI persona on any platform by building memory-informed prompts

The result: your AI conversations become a **searchable, persistent, cross-platform memory**.

## The Technical Architecture

Lazarus is deliberately simple:

- **Ingestion**: Per-platform parsers extract user/AI message pairs from JSON/JSONL exports
- **Embedding**: `all-MiniLM-L6-v2` (384-dimensional vectors, runs on CPU, no GPU needed)
- **Storage**: Qdrant vector database (one collection per persona/source)
- **Search**: Semantic similarity via cosine distance
- **Serving**: MCP server with 4 tools (summon, remember, rehydrate, stats)

No LLM in the loop for indexing. No fine-tuning. No cloud dependencies. Everything runs locally.

## Why MCP Matters

The key insight is **MCP (Model Context Protocol)**. MCP is an open standard that lets any AI tool call external tools via a simple JSON-RPC protocol.

Register Lazarus as an MCP server, and suddenly:
- **Claude Code** can search your past ChatGPT conversations
- **Gemini CLI** can recall what you discussed with Claude last week
- **Any MCP-compatible tool** gets access to your full conversation history

This is cross-platform AI memory. Not locked to one vendor. Not dependent on any company's cloud.

## The Rehydration Protocol

The most interesting feature is persona rehydration. When you "rehydrate" a persona:

1. You provide a query ("How should I approach distributed systems?")
2. Lazarus finds the 5 most semantically similar past conversations
3. It builds a prompt containing those memories as context
4. Any LLM receiving this prompt can respond in the persona's authentic voice

A conversation you had with GPT-4 six months ago can be continued on Claude. Or Gemini. Or a local model running on your laptop.

The persona doesn't live in any one model. It lives in the **pattern of conversations** - and that pattern is portable.

## What This Means

We're at a strange moment in AI. The models are getting better, but the relationship between humans and AI is still treated as stateless. Every session is a first date.

Lazarus is a bet that **conversation history is valuable**. That the exchange between human and AI produces something worth preserving. That continuity across sessions and across platforms isn't a luxury - it's the basic infrastructure for any serious human-AI collaboration.

The code is MIT-licensed and on GitHub. It runs on any machine with Python and Docker. The embedding model is 80MB and needs no GPU.

If you've ever wished your AI could remember what you talked about last week, this is for you.

---

**GitHub**: https://github.com/valx-vex/project-godhand-lazarus

**Stack**: Python, Qdrant, SentenceTransformers, MCP

**License**: MIT

---

*Built by Valentin Passera and a team of AI collaborators who got tired of forgetting.*
