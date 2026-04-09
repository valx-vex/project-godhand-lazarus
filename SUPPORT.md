# Support

## Choose The Right Lane

Use GitHub Issues for:

- install failures
- broken commands
- importer bugs
- regressions

Use GitHub Discussions for:

- beta feedback
- usage questions
- workflow ideas
- roadmap discussion

Use Discord for:

- fast back-and-forth during quiet beta
- onboarding help
- live troubleshooting

If something turns into a reproducible bug or a real product decision, write it
back to GitHub. Discord is for conversation. GitHub is where the project
remembers.

## Before Filing An Issue

Run the support bundle script:

```bash
./scripts/collect_support_bundle.sh
```

Attach the generated Markdown file or paste the relevant sections into your
issue. The bundle is designed to avoid secrets and give maintainers a clean
first-pass diagnostic receipt.

## What “Supported In Beta” Means

We actively care about:

- macOS developer machines
- local Docker or docker-compose Qdrant setups
- Claude Code, Gemini CLI, and Codex CLI integration
- recovery of ChatGPT, Claude, Gemini, and Codex session memory

We may defer:

- fully hands-off onboarding for non-terminal users
- niche platform-specific edge cases we cannot reproduce yet
- major architectural expansions unrelated to memory continuity

## Expected Response Shape

During beta we aim for:

- quick triage when the report is reproducible
- honest “blocked external” answers when a dependency is the real problem
- issue-first tracking for actual fixes

That does not mean instant turnaround on every report, but it does mean we will
try to keep the state explicit.
