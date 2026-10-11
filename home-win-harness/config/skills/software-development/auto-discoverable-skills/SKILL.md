---
name: auto-discoverable-skills
description: "Author skills agents auto-pick and that drive a helper."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, authoring, auto-discovery, subagents, routing, helper-scripts]
    related_skills: []
---

# Authoring Auto-Discoverable Skills

How to write a skill so an agent or subagent PICKS it at run-time from the skill
list and then DOES the right thing (runs the helper / follows the procedure)
rather than improvising. This is the discovery-and-invocation mechanism; it is
not about repo frontmatter conventions (that is the bundled
`hermes-agent-skill-authoring` skill). Use both together when contributing a
skill upstream.

## When to Use

- Building a new skill you want agents/subagents to pick up on their own from the
  skill list, without the user naming it.
- A skill exists but agents keep ignoring it or reasoning the answer themselves
  instead of running its helper — the description or body needs sharpening.
- You want to confirm a skill's trigger actually fires before relying on it.

Don't use for: repo frontmatter/structure/test/docs conventions for contributing
a skill upstream — that is the bundled `hermes-agent-skill-authoring` skill.

## The mechanism you are designing for

There is no separate "register a trigger" step. Every turn the agent is shown the
skill list as name + description, and the system prompt tells it to load anything
even slightly relevant. So the DESCRIPTION is the entire routing signal, and the
BODY is what steers behavior once loaded. Precise auto-discovery = a sharp
description + a body that says exactly what to do.

## Layer 1 — the description (the whole trigger)

- Hard limit 60 chars, one sentence, ends with a period. `skill_manage(create)`
  refuses longer; the validator's 1024 ceiling is NOT the standard.
- The system-prompt index truncates at 57 chars + "...", so the trigger words must
  survive the first 57 chars. Verify: the substring `description[:57]` must still
  read as the trigger. A trailing word can be cut; the leading verbs cannot.
- Shape: `Use <when/to> <specific trigger>.` Put the discriminating verbs first
  (e.g. `classify/route/gate`), not filler.
- Match trigger breadth to real value. A description that fires on EVERY instance
  of a broad category (e.g. "any decision") makes the agent invoke the skill for
  trivial cases where it should just act — wasting a network call / latency each
  time. Narrow the description to the subset where the skill actually earns its
  cost; encode the wider framing in the body's When-to-Use instead.

## Layer 2 — the body (what a loaded agent does)

- Include a `## When to Use` with concrete trigger examples AND a `Don't use for`
  counter-trigger list. Counter-triggers are what keep a broad-sounding skill
  from over-firing once loaded.
- If the skill has a helper script, add an imperative instruction: "Do NOT answer
  from your own judgement when this skill applies — build the inputs and call
  `scripts/<helper>.py`." Without this an agent reads the skill and then reasons
  the answer in prose anyway.
- Ship non-trivial logic as a `scripts/<name>.py` helper referenced by path; do
  not expect the model to reinline a parser or API client each call. Keep helpers
  stdlib-only when feasible so any interpreter runs them.

## Verifying discovery actually fires (do not skip)

Prove the trigger end-to-end with an UNCOACHED subagent — reading the description
yourself is not proof:

1. `delegate_task` with a realistic task in the skill's domain. The prompt must
   NOT name the skill, the helper, or the underlying tool/API. Tell the child to
   "use whatever capabilities/skills are available" and to report HOW it answered
   (which skill, which tool, which file path) — honesty about improvising included.
2. Read the child's live transcript at the `live_transcripts` path returned by
   the dispatch. A PASS is unambiguous only if an EARLY action is
   `skill_view(<skill>)` — i.e. it discovered the skill from the list and loaded
   it before working, then called the helper. If it produced the answer in prose
   with no skill load, the trigger FAILED — sharpen the description's leading
   words and retest.

## Read the truncation, don't eyeball it

Compute `len(desc)` and `desc[:57]` before committing a description; a description
that looks fine at 60 chars can lose its trigger verb at the 57-char cut. One line
of code beats guessing.

## Pitfalls

- A description that restates the skill NAME or the implementation wastes the
  57-char budget; spend it on the trigger.
- Broadening a description to "catch more" without adding body counter-triggers
  produces an over-firing skill — the failure is silent (wasted calls), not an error.
- A skill body with no explicit "call the helper" instruction gets read and then
  ignored; the agent reasons instead. State the imperative.
