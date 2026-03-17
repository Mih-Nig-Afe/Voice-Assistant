# Security Guidelines

This is a public repository. Keep credentials out of source control and build contexts.

## Secrets Policy

- Never commit `.env` or any real API keys.
- Keep real credentials only in local `.env` files or your CI secret store.
- Commit only `.env.example` placeholders.
- Never paste secrets in issues, pull requests, or logs.

## Required Local Setup

1. Copy `.env.example` to `.env`.
2. Fill in your local keys.
3. Run the assistant with local `.env`.

## If a Secret Was Exposed

1. Rotate/revoke the affected key at the provider immediately.
2. Replace local `.env` with the new key.
3. Check recent commits for accidental leaks.
4. If a key was committed, rewrite history and force-push (only if the team approves):
   - `git filter-repo` or BFG can remove historical secrets.

## Build and CI Hygiene

- `.dockerignore` excludes `.env*` to avoid sending secrets in Docker build context.
- `.gitignore` excludes `.env*` while preserving `.env.example`.
- Use GitHub Actions secrets for workflow credentials.
