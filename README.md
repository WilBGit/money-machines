# Money Machines Revenue and Content Toolkit

[![CI](https://github.com/WilBGit/money-machines/actions/workflows/ci.yml/badge.svg)](https://github.com/WilBGit/money-machines/actions/workflows/ci.yml)

Money Machines is a collection of local-first scripts, content templates, and service concepts for building revenue experiments around newsletters, consulting, lead generation, website audits, content repurposing, trade journals, video production, and digital products.

## Included active work

- `02-substack-newsletter/`: setup and newsletter content.
- `03-fiverr-consulting/`: service descriptions and offer copy.
- `04-appointment-setter/`: appointment-setting workflow.
- `05-website-audit/`: website audit utility.
- `06-content-repurposing/`: content transformation tools.
- `07-trade-journal/`: trade-journal analysis utility.
- `08-youtube-channel/`: channel plan and local video generator. The standalone generator is also published at https://github.com/WilBGit/youtube-generator.
- `09-etsy-products/`: digital-product plans and cheat-sheet source files.
- `10-lead-list-service/`: lead-list and outreach generation utility.
- `shared/`: reusable analysis, dashboard, OAuth setup, and LLM client helpers.

The retired Gumroad material and `_retired/` directory are intentionally excluded from this publication. Generated media, customer or lead data, local reports, provider tokens, OAuth state, and runtime outputs are also excluded.

## Operating model

These are tools and drafts, not an unattended business or automatic publishing system. Review generated content, prices, market claims, contact data, and legal or platform requirements before use. Do not use the utilities to send unsolicited messages or process personal data without an appropriate lawful basis and user consent.

The shared LLM client is configured to use runtime credentials or the local Hermes OAuth boundary. No provider token is stored in this repository.

## Local usage

Each directory contains its own script or setup notes. Install only the dependencies needed for the selected tool, keep credentials in a local environment, and write generated files outside Git. The YouTube generator requires a separate media review and human publishing checkpoint.

## Security

This public repository is a sanitized source publication. Read `SECURITY.md` before adding integrations. Never add API keys, Google token files, Gumroad tokens, OAuth state, customer records, phone numbers, email lists, payment information, or generated output to Git.
