---
name: scraping-client-rendered-sites
description: "Use when web_extract returns only a shell: SPA/Next.js data."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [scraping, spa, nextjs, javascript, data-extraction, web]
    related_skills: [blocked-page-recovery]
---

# Scraping Client-Rendered Sites

Extract the real data from a site whose content is rendered by JavaScript in
the browser, so `web_extract` / a plain fetch returns only the page shell
(nav, headings, empty counters) and none of the records you actually want.
This is a RENDERING problem, not an ACCESS problem — if the fetch itself is
blocked (403 / 429 / WAF / paywall) use `blocked-page-recovery` instead.

## When to Use

- `web_extract` on a page returns headers, a count like `0/257`, filter labels,
  or option lists, but the list/records/questions themselves are absent.
- The page is a known SPA framework (Next.js, React, Vue, SvelteKit) — view
  source shows `/_next/static/`, `__NEXT_DATA__`, a `#root` div, or a wall of
  `<script src=...chunk...>` and almost no body text.
- You need STRUCTURED data (a JSON array of records) rather than prose; the
  prose lesson/article pages of the same site may extract fine while the
  interactive/data pages do not.

Don't use for: static server-rendered pages (web_extract already returns the
body), or fetch failures with an HTTP error status (that is access, not
rendering).

## Procedure

1. Confirm it is client-rendered. Fetch the page HTML and check for
   `__NEXT_DATA__` (Pages Router — data is inline, easy) vs. its ABSENCE plus
   many `/_next/static/chunks/*.js` (App Router — data is bundled in a chunk,
   the common hard case). Also try the sitemap (`/sitemap.xml`) first for the
   full URL inventory before scraping page-by-page.

2. If `__NEXT_DATA__` exists: parse that `<script id="__NEXT_DATA__">` JSON
   directly — done.

3. App Router / no inline data: find the chunk holding the data. Download the
   `<script src="/_next/static/...">` list, fetch each chunk, and SCORE each
   for signature tokens of your target data (field names you expect:
   `"options"`, `correctAnswer`, `subDomain`, a known string from the page).
   The chunk with the highest hit count and largest size holds the payload.

4. Extract the payload. Framework-bundled data is almost always embedded as
   `JSON.parse('<escaped-json>')` (sometimes several per chunk). Walk from each
   `JSON.parse('` to its closing `'`, respecting `\\`-escapes, to slice out
   each single-quoted literal. Do NOT regex-match to the first `'` — the JSON
   contains apostrophes.

5. Decode the JS single-quoted string literal to valid JSON text, THEN
   `json.loads`. See `references/js-to-json-unescape.md` for the exact escape
   rules — getting these wrong is where the time goes.

6. Verify the count. Dedupe by a stable id field and assert the total matches
   what the page advertised (e.g. the `0/257` counter). A parse that silently
   drops one payload of five looks successful but loses a fifth of the data.

## Parallelize the prose, keep the data local

When a site mixes easily-extracted prose pages with a hard data payload:
extract the prose pages with parallel subagents (one batch per section/domain,
quick tier, each writing raw files to a shared dir), but do the chunk-hunting
and JSON-unescape yourself in `execute_code` — it is fiddly, stateful, and not
worth a subagent round-trip.

## Pitfalls

- The interactive page's counter (`0/257`, `Due Today 15`) tells you the true
  record count. Reconcile your parsed total against it before trusting the
  extraction — a per-payload escape failure drops whole domains silently.
- Only the OUTER JS string literal is unescaped by your decoder; the result
  still legitimately contains JSON escapes (`\"`, `\\`, `\uXXXX`). Collapsing
  those too corrupts the JSON. Unescape the JS layer, hand valid JSON to the
  parser.
- `web_extract` truncates large pages with a head+tail window and a footer
  giving the saved full-text file path; read that file for the omitted middle
  rather than re-fetching.
