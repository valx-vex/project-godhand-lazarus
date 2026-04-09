# Security Policy

## Supported Status

Godhand Lazarus is in quiet beta. The code is real and working, but the
hardening surface is still evolving.

## Reporting A Vulnerability

Do not open a public issue with exploit details.

Use one of these paths:

1. If GitHub private vulnerability reporting is available for the repo, use it.
2. Otherwise contact the maintainers through the private beta coordination
   channel.
3. If neither path is available, open a minimal issue requesting secure contact
   and include no technical details beyond the fact that you have a security
   report.

## What To Include

- affected command, script, or workflow
- impact summary
- reproduction steps
- environment details
- whether secrets or local data exposure is involved

## Beta Security Expectations

- local-first behavior is a design goal, not a license to skip review
- imports and support bundles must stay secret-safe by default
- we prefer private coordination for fixes before disclosure
