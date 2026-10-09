---
name: platform-adoption-prerequisites
description: Identify blockers before platform adoption code.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [platform-work, adoption, observability, requirements-gathering, stakeholder-alignment, blockers, onboarding]
    related_skills: [plan, requesting-code-review, document-to-action-items]
---

# Platform Adoption & Observability Prerequisites

Use this skill when you are implementing a complex platform feature (observability, instrumentation, onboarding, infrastructure) that requires:

- **Multi-stakeholder sign-off** (adoption owners, infrastructure, security/DPP, etc.)
- **Blockers before code** — certain architectural/policy decisions must be locked in writing before implementation is deterministic
- **Parallel workstreams** — some teams handle onboarding while you prepare the code
- **Long lead time** — approval cycles or external provisioning delays

The goal is to make the entire adoption path transparent, identify blockers upfront, and produce structured emails/documentation that unblock each stakeholder in parallel rather than serially.

## Core Pattern

**Do not code until approvals are documented.** Platform adoption work succeeds or fails at the prerequisite phase. Coding against an assumed spec leads to rework, PII violations, compliance issues, and wasted time.

## When to Use This Skill

✓ You are instrumenting an app for platform-wide observability (OpenTelemetry, metrics dashboards, tracing)
✓ You are adding security/compliance features (DPP, audit, encryption, secret management)
✓ You are integrating with platform infrastructure (Kyma, vault, collectors, gateways, external services)
✓ You need approval from multiple teams (adoption, security, infrastructure, product)
✓ The implementation plan references "confirm with platform team" or "get written approval"

✗ You are implementing a feature entirely within a single application repo with no external dependencies
✗ You are fixing a bug that has a clear, documented root cause
✗ You are refactoring internal code that doesn't touch deployment or external contracts

## Core Workflow

### 1. Read the Existing Plan/Spec (if provided)

Your starting point is usually:
- A Jira ticket with technical requirements
- An implementation plan document (often very detailed)
- Links to platform guidance/technical pages
- A list of "decisions that must be confirmed before code" (the blockers)

**Spend 30 minutes understanding:**
- What the feature builds and why
- What the architecture must look like
- What constraints exist (privacy, performance, compliance)
- Which decisions are already locked vs. still open
- Who owns each decision

### 2. Identify Stakeholder Tracks

Map each blocker to the person/team that owns the answer:

**Example: OpenTelemetry Adoption**

| Blocker | Owner | Category |
|---------|-------|----------|
| Metric catalogue version & semantic conventions | Erik Mehling (Adoption) | **KPI/adoption alignment** |
| User/session identity mechanism & DPP approval | Lidziya Smirnova (Infrastructure) + DPP office | **Identity/security** |
| OctoRoute tenant/endpoint/protocol | Lidziya Smirnova (Infrastructure) | **Infrastructure provisioning** |
| Cost calculation & attribution | Erik Mehling (Adoption) | **KPI/adoption alignment** |
| Signal scope & collector topology | Lidziya Smirnova (Infrastructure) | **Architecture** |

Group blockers by owner. Often 2–3 distinct stakeholders, each with 2–5 blockers.

### 3. Decompose Each Blocker into a Question

Turn each blocker into one or more specific, answerable questions:

**Bad blocker:**
> Confirm the identity mechanism

**Good blockers:**
> 1. Does the platform provide an approved mechanism to derive a pseudonymous/hashed user identifier from the bearer token?
> 2. Or should the app emit no user-level distinctness signal on metrics at all?
> 3. Are there specific claim/header names or retention rules?

**Why:** Open-ended blockers get vague answers. Specific questions get specific answers you can code to.

### 4. Compose Structured Stakeholder Emails

Write one email per stakeholder owner. Structure:

**Header:** Subject line including the Jira ticket + what you're asking for
**Opening:** One sentence: "I'm [feature] and need your confirmation on [number] critical items before I write code."
**Body:** Numbered list of questions (3–6 per email), each with:
  - One sentence stating the question
  - One sentence explaining why it blocks you
  - Context (what the app currently has, what the guidance says, what the constraint is)
**Closing:** "Once I have these [N] items confirmed in writing, I can [concrete next steps]."

**Tone:** Professional, specific, not apologetic. You're not asking permission — you're asking for the spec.

### 5. Include Background & Context

In each email, reference:
- The Jira ticket (gives them the big picture)
- Accessible guidance or links (so they know you did your homework)
- What the app currently does (grounds the question)
- Why the answer matters to the implementation

**Example:**
> "FAA currently propagates the bearer token to downstream services (DSP/OData) for row-level security, but the token itself is a secret and cannot be emitted on metrics. The plan prohibits emitting `user.id` on metrics. So we need to understand: Does the platform provide an approved mechanism to derive a pseudonymous/hashed user identifier *from* that token, or should FAA not emit any user-level distinctness signal on metrics at all?"

This is much better than just "How do we calculate DAU?"

### 6. Document the Implementation Plan's Blocker Section

If the plan already exists, read the "Decisions that must be confirmed before code is written" section carefully. Those are usually your starting point. Add any blockers the plan missed.

### 7. Create a References Document (Optional but Recommended)

After writing the emails, create a `docs/adoption/ADOPTION_BLOCKERS.md` or similar in your repo with:

- The list of blockers and owners
- The questions you asked each owner
- Links to the Jira ticket, guidance pages, and the plan
- A checklist of confirmations received (mark off as replies come in)
- Placeholder for the "golden approval document" (the written spec you'll eventually link from code)

This becomes the living record of "what we asked, who we asked, and when they said yes."

## Email Authoring Rules

### Clarity

- **Use numbered lists**, not paragraphs
- **One question per item** (not multiple nested questions)
- **Name the decision owner** upfront ("I need your confirmation on [X]")
- **Avoid "what do you recommend?"** — ask for a specific decision or mechanism

### Tone

- Professional and direct, not casual
- Assume the recipient knows their domain and will give you a straight answer
- Reference their role/team: "As the infrastructure owner, you've seen this topology before"
- Do not apologize for asking — blockers are normal

### Specificity

- **Bad:** "How should we handle identity?"
- **Good:** "Does the platform accept a pseudonymous identifier on approved spans only, or should FAA emit no user-level signal on metrics?"

- **Bad:** "What endpoint do we use?"
- **Good:** "Once FAA is assigned a producer ID, what does the endpoint look like? Can you provide a sanitized example (e.g., `https://octoroute-producer-<region>.int.sap:3333`)?"

### Length

- 300–500 words per email
- 3–6 blockers per email (more than 6, split into a follow-up)
- Include context paragraph (why the decision matters)

## Pitfalls & How to Avoid Them

### Pitfall 1: Asking open-ended questions

**Bad:** "Tell us about your observability strategy"
**Fix:** "Confirm whether logs/traces are required in addition to metrics, or if metrics-only is sufficient for the Adoption Dashboard"

### Pitfall 2: Including implementation assumptions in the question

**Bad:** "Should we use OTLP/gRPC or OTLP/HTTP for the exporter?"
**Fix:** "Which protocol did the OctoRoute onboarding select — OTLP/HTTP (port 3333) or OTLP/gRPC (port 3334)?"

The owner already knows the answer. Your job is to extract it, not to propose options.

### Pitfall 3: Conflating multiple blockers into one

**Bad:** "How should we handle identity and cost?"
**Fix:** (Two separate numbered items)

When you combine unrelated decisions, the reply gets muddled and you have to follow up.

### Pitfall 4: Not explaining why the blocker matters

**Bad:** "Confirm the metric catalogue version."
**Fix:** "Confirm the source-page catalogue/semantic-convention version. The implementation uses exact instrument names and attributes from the approved schema; using generic names when the platform's schema differs causes dashboard consumption failures and requires rework."

### Pitfall 5: Forgetting to ground the question in "what the app currently has"

**Bad:** "What is the identity mechanism?"
**Fix:** "FAA currently propagates the bearer token to downstream services (DSP/OData) for row-level security, but the token itself is a secret and cannot be emitted on metrics. Confirm the platform's approved mechanism for distinct-user/session calculation and whether FAA should emit any pseudonymous identity signal on metrics."

The recipient knows more if they understand the current state.

### Pitfall 6: Sending emails too early (before you've read the plan)

Before you email stakeholders, **read and understand the implementation plan completely**. Identify which decisions are already locked ("Design invariant: never replace MLflow") vs. still open ("Confirm collector topology"). Only ask about the open ones.

### Pitfall 7: Not providing a written record of the confirmation

**Fix:** After the stakeholder replies, **save their response** or a summary in a central doc (e.g., `docs/adoption/GOLDEN_APPROVALS.md`). When you write code, link back to the approval in comments. This is your compliance record.

## Example: OpenTelemetry Adoption (Real Session)

**Blockers identified:**
1. Metric catalogue version & semantic-convention authority (Erik)
2. User/session identity mechanism (Lidziya + DPP)
3. OctoRoute tenant/endpoint/protocol (Lidziya)
4. Dashboard KPI mapping & cost source (Erik)
5. Signal scope & collector topology (Lidziya)

**Email 1 (Erik):** 5 questions about adoption metrics, identity, and cost
**Email 2 (Lidziya):** 6 questions about OctoRoute onboarding, mTLS, topology, semantic conventions

**Result:** Parallel workstreams
- Erik's team coordinates DPP and metric schema
- Lidziya's team does OctoRoute onboarding and infrastructure design
- Development is blocked until both tracks produce written approval

## Integration with Other Skills

### plan

After all blockers are confirmed, use the `plan` skill to decompose the implementation into tasks. The plan's Task 1 is usually "document the approvals and create the golden reference."

### requesting-code-review

Before merging adoption code, the code review must verify:
- Implementation matches the written approvals
- No PII or secrets appear in code/logs
- All blockers are satisfied by the implementation

### document-to-action-items

If the plan document is very long, use this skill to extract obligations, deadlines, and owners upfront.

## Success Criteria

You have successfully used this skill when:

- [ ] You have identified 4+ blockers and mapped each to an owner
- [ ] You have written 2+ stakeholder emails, each with 3–6 specific questions
- [ ] Each email has context (why the decision matters) and grounding (what the app currently does)
- [ ] Emails are specific enough that a one-sentence reply answers the question
- [ ] You have a checklist (in memory or a shared doc) of which blockers are confirmed
- [ ] You have NOT started writing implementation code
- [ ] You have a plan to document the approvals (so future code reviews can reference them)

## Remember

```
✓ Read the plan/guidance completely before emailing stakeholders
✓ Identify blockers; map each to an owner
✓ Turn blockers into specific, answerable questions
✓ Include context: why the decision matters
✓ Ground in current state: what the app has now
✓ One email per stakeholder; 3–6 items per email
✓ Save confirmations in a central doc
✓ Do NOT code until approvals are documented
✓ Link approvals from code comments/design docs
✓ Use plan skill to decompose after blockers are cleared
```

**Platform adoption succeeds or fails at the prerequisite phase. Lock in the spec before you code.**
