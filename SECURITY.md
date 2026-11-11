# Security Policy

## Scope

This repository contains local revenue experiments, content tools, templates, and reusable helpers. It does not contain provider credentials, customer data, payment records, OAuth state, or generated production output.

## Never commit

- Google, Gumroad, OpenAI, Hermes, Twilio, YouTube, social-media, or marketplace tokens
- Passwords, OAuth files, private keys, cookies, connection strings, or account exports
- Lead lists, phone numbers, email addresses, customer records, payment data, or private messages
- `.env` files, local databases, logs, generated audio/video, scraped data, or runtime state

## Safe configuration

Use a local secret manager or environment variables. Keep provider tokens and OAuth files owner-readable only. Use synthetic data for tests. Review every generated message and verify consent before contacting a person or publishing content.

## Pre-push checklist

- Inspect staged paths for hidden token files, data exports, output media, caches, and local state.
- Run `git diff --cached --check`.
- Run high-confidence secret scans over staged files and reachable history.
- Compile the selected Python tools and run their local dry-run or help paths.
- Confirm that any publication or outreach action still requires deliberate human approval.

If a credential or private record is committed, revoke or rotate it immediately, remove it from the current tree and reachable history, and re-scan the remote repository.
