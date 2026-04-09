# Maintainer Playbook

## Core Rule

Discord is for conversation. GitHub is where the project remembers.

If a Discord thread reveals a reproducible bug, a real product request, or a
decision that future maintainers will need, move it into GitHub.

## Beta Triage Loop

1. Ask for the support bundle first.
2. Classify the report:
   - install
   - bug
   - docs
   - enhancement
   - blocked external
3. If the report is incomplete, label it `needs-repro`.
4. If the problem is external, keep the issue open only if there is project
   work to do; otherwise close it with a clear explanation.
5. If the fix is valid and bounded, map it to an issue and then a PR.

## Label Rules

- `beta` for issues discovered during beta operations
- `install` for setup or environment failures
- `bug` for confirmed defects
- `docs` for documentation fixes
- `enhancement` for improvements
- `good first issue` and `help wanted` only when a maintainer would genuinely
  welcome outside help
- `needs-repro` when the report lacks enough machine truth to act
- `blocked-external` when a third-party CLI, quota, or provider is the blocker

## Response Pattern

- thank the user briefly
- name the real state directly
- avoid pretending uncertainty is clarity
- ask for the narrowest next artifact that will unblock triage
- close the loop in GitHub once the state is known

## Beta Escalation

Escalate to maintainer attention when:

- the support bundle suggests data loss risk
- a report affects multiple CLIs or multiple nodes
- the bug contradicts the README or release notes
- a user found a security-sensitive path
