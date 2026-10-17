---
name: cfaai-wiki-save-and-lint
description: "Use when saving docs to or linting the CFAAI LLM wiki."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [obsidian, wiki, cfaai, lint, karpathy, llm-wiki]
    related_skills: [obsidian, llm-wiki]
---

# CFAAI LLM Wiki — Save & Lint

Use this skill when:
- Saving any document (plan, note, guide) from the fin-analyst-agent repo or CFAAI work into the wiki
- Running a lint/health-check on the wiki
- Asked to "update the wiki" with new knowledge

## Vault location

The vault is a Karpathy three-layer LLM wiki backed by an Obsidian vault:

  /Users/C5418860/VSCodeRepos/cfaai-llm-wiki/vault/

Key files:
- vault/CLAUDE.md         -- schema contract (read first every session)
- vault/index.md          -- derived page catalog (update "By topic" section after ingest)
- vault/log.md            -- append-only action log (always append after any change)
- vault/wiki/             -- LLM-owned entity+concept pages (agent writes these)
- vault/sources/          -- IMMUTABLE raw sources (notes/, webpages/, github/, clippings/)

Set OBSIDIAN_VAULT_PATH=/Users/C5418860/VSCodeRepos/cfaai-llm-wiki/vault if env var lookups are needed.

## Three-layer rules (never cross)

1. sources/ is IMMUTABLE — read only, never rewrite body
2. wiki/ is LLM-OWNED — agent creates, updates, cross-links
3. CLAUDE.md / index.md / log.md are infrastructure — agent updates under strict rules

## Orientation (mandatory at session start)

Before any wiki operation in a new session:
1. read_file vault/CLAUDE.md
2. read_file vault/index.md
3. read_file vault/log.md (last ~30 lines)
4. search_files for the topic at hand before creating anything

## Ingest workflow (saving a new doc)

1. Copy/write the raw file to sources/notes/YYYY-MM-DD-<slug>.md with frontmatter:
     type: source
     source_kind: note
     title: <title>
     ingested: YYYY-MM-DD
     tags: [raw, <topic-tags>]
     related_wiki: []

2. Create wiki/<slug>.md with REQUIRED frontmatter (see below). Synthesize — do NOT paste source content verbatim.

3. Add inlinks: edit Related section of at least 2 existing wiki pages to link to the new page. Without inlinks the page becomes an orphan immediately.

4. Update index.md "By topic" section (between <!-- BEGIN: manual-curation --> and <!-- END: manual-curation -->). Add to an existing section or create a new one. Update _Last regenerated_ date.

5. Append to log.md:
     ## [YYYY-MM-DD] ingest-note | <title> | (source)
     Created sources/notes/... Created/Updated wiki/... Added cross-refs to ...

## Required wiki page frontmatter

```yaml
---
type: wiki
title: <Canonical Title>
aliases: [<alt names>]
tags: [<from taxonomy in CLAUDE.md>]
summary: <one sentence, used in index.md>
provenance: extracted | inferred | mixed
sources:
  - "[[<source-slug>]]"
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Hard rules (from CLAUDE.md):
- Wikilinks in YAML lists MUST be quoted: ["[[foo]]"] not [[[foo]]]
- Dates ISO YYYY-MM-DD
- Tags are YAML list, never inline #hashtags
- No unknown frontmatter keys

## Lint workflow

Run programmatically with execute_code (Python). Checks in priority order:

1. Broken wikilinks — target not in wiki/ AND not in sources/ — SEVERITY: high
   NOTE: wikilinks pointing to dated source slugs (e.g. [[2026-07-01-foo]]) are VALID source
   citations. Only flag when the slug is absent from both wiki/ and sources/.

2. Orphan pages (no inlinks from any other wiki page or index.md) — SEVERITY: medium
   Fix by adding a Related entry in a semantically relevant existing page.

3. Missing/invalid frontmatter — SEVERITY: medium
   The sources: field is a multi-line YAML list. A naive line-parser false-positives "empty"
   when the list is on continuation lines. Check for "sources:\n  -" pattern or use PyYAML.

4. Pages not in index.md "By topic" section — SEVERITY: low
   Add to an appropriate section in the manual-curation block.

5. Page size > 200 lines — SEVERITY: low (candidate for splitting)

6. Log rotation: if log.md exceeds 500 entries, rename to log-YYYY.md and start fresh.

After lint, append a log.md entry:
  ## [YYYY-MM-DD] lint-wiki | N issues found/fixed | —

## Saving a plan document (e.g. CFAAI-NNN-*.md from fin-analyst-agent)

1. Copy file to vault/wiki/<cfaai-nnn-slug>.md
2. Prepend frontmatter (don't replace content)
3. Add inlinks from the most relevant existing pages (e.g. fin-analyst-agent.md for FAA plans)
4. Add to index.md under an appropriate section
5. Append to log.md

## Pitfalls

- ALWAYS orient first (CLAUDE.md + index.md + recent log) before any op in a new session
- sources: frontmatter is multi-line YAML — don't false-positive it as empty with a naive parser
- Broken wikilinks to source slugs (dated like 2026-07-01-foo) are VALID — sources/ is the target
- Never hand-edit index.md outside the <!-- BEGIN/END: manual-curation --> block
- All wiki page edits must update the `updated:` frontmatter date
- Every new page needs at least 2 outbound [[wikilinks]] and at least 1 inlink
- Do not use tags not in CLAUDE.md taxonomy — add new tags to CLAUDE.md first
