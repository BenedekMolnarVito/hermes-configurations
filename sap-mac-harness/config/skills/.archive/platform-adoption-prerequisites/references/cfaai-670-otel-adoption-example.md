# Reference: CFAAI-670 OpenTelemetry Adoption — Real-World Example

This is a concrete, real-world example of platform adoption prerequisites in action. It demonstrates:

- How a detailed implementation plan already contained the blocker list
- How to map blockers to stakeholders  
- How to decompose blockers into specific, answerable questions
- How to structure emails for each stakeholder track

## The Task

Instrument Financial Analyst Agent (FAA) as an OpenTelemetry/OctoRoute producer so the central AI Adoption Dashboard can track adoption metrics (active users, sessions, tokens, latency, errors).

**Why it blocked:** FAA currently logs only to MLflow (great for traces, zero token/cost visibility). The adoption dashboard needs OpenTelemetry signals, but this requires platform onboarding, infrastructure setup, and DPP approval before any FAA code changes.

## Blockers Identified (from the plan)

The implementation plan explicitly listed six decisions that must be confirmed before code:

1. **Standard metric catalogue** — Which semantic-convention version? Required attributes? Temporality? Metrics vs. spans vs. logs?
2. **Identity/DPP contract** — How to derive distinct users/sessions without emitting `user.id` on metrics?
3. **OctoRoute tenant details** — Producer ID, cost object, endpoint, protocol, certificate authority, region?
4. **Dashboard mapping** — Is client `request_identifier` an approved business session ID, or must it stay out of telemetry?
5. **Cost calculation** — What is the authoritative source/formula for `cost_eur`?
6. **Signal scope & collector topology** — Logs/traces in addition to metrics? Direct to OctoRoute or in-cluster gateway?

## Stakeholder Mapping

| Blocker | Owner | Expertise |
|---------|-------|-----------|
| 1, 4, 5 | **Erik Mehling** | KPI/adoption alignment, dashboard consumption, cost attribution |
| 2 (DPP), 3, 6 | **Lidziya Smirnova** | Infrastructure, OctoRoute onboarding, mTLS, collector topology, semantic conventions |

Two parallel tracks:
- **Erik's track:** Adoption metrics, identity/DPP, cost
- **Lidziya's track:** Infrastructure provisioning, onboarding, architecture

## Decomposition into Questions

### For Erik (KPI/Adoption)

**Blocker 1 → Questions:**
- Which semantic-convention version/catalogue should I reference as authoritative?
- Are the instrument names from the public guidance page the exact ones the dashboard consumes?

**Blocker 4 → Questions:**
- The app has both `request_identifier` (client-supplied) and `session_id` (FAA-generated UUID). Which should become a dashboard dimension?
- Or should both stay out of telemetry?

**Blocker 5 → Questions:**
- Who owns the cost calculation? Is there an approved pricing table?
- Should cost be emitted only when available, or is it optional for MVP?

**Blocker 2 (Identity)** — Shared with Lidziya & DPP → Questions:**
- The plan prohibits `user.id` on metrics. What *is* the approved mechanism for calculating DAU/WAU/MAU?
- Does it require a pseudonymous identifier on approved spans only?
- Or does the platform derive distinctness from server-side logs?

### For Lidziya (Infrastructure/OctoRoute)

**Blocker 3 → Questions:**
- Where/how do we submit the OctoRoute producer onboarding ServiceNow request?
- What are the exact endpoint format, protocol (HTTP 3333 or gRPC 3334), and region mapping?
- Who provides/manages the SAP-signed client certificate? Where does the private key live (Vault secret, HSM)?

**Blocker 6 → Questions:**
- Do we need logs/traces in addition to metrics, or is metrics-only sufficient?
- Will there be a direct endpoint per app, or an in-cluster gateway Collector?

**Blocker 1 (shared)** → Questions:
- Can you share the canonical metric names and attributes that the Adoption Dashboard consumes?
- Are the names from the public guidance page accurate, or is there a more recent internal spec?

## Email Structure

Two emails were composed:

### Email 1: Erik Mehling (KPI/Adoption Alignment)

**Subject:** CFAAI-670 Prerequisites — Metric Catalogue & Dashboard KPI Alignment

**Content:**
- 5 numbered questions about metric catalogue, identity mechanism, business session identity, cost attribution, and onboarding timeline
- Each question included:
  - What the blocker is (one sentence)
  - Why it blocks implementation (one sentence)
  - Context (what FAA currently has, what the guidance says, what the constraint is)
- Closing: "Once I have these five items confirmed in writing, I can document the contract and proceed with code."

### Email 2: Lidziya Smirnova (Infrastructure/OctoRoute)

**Subject:** CFAAI-670 Prerequisites — OctoRoute Onboarding & mTLS Setup

**Content:**
- 6 numbered questions about OctoRoute onboarding intake, certificate/key provisioning, collector topology, endpoint details, secret materialization in Kyma, and semantic conventions
- Each question included context and grounding
- Closing: "Once I have these six items confirmed, I can proceed with Task 1 (OctoRoute onboarding) and Tasks 2–3 (telemetry module)."

## Key Principles Demonstrated

1. **Read the plan first.** The blockers were already identified; the job was to decompose them into questions.
2. **Map blockers to owners.** Each blocker went to the person/team that could answer it with authority.
3. **Turn blockers into specific questions.** "Confirm the identity mechanism" → "Does the platform accept a pseudonymous identifier on approved spans only, or should FAA emit no user-level signal on metrics?"
4. **Ground in current state.** "FAA currently propagates the bearer token to downstream services (DSP/OData) for row-level security, but the token itself is a secret and cannot be emitted on metrics."
5. **Professional tone, not apologic.** "I need your confirmation on X" not "I'm sorry, could you maybe help with X?"
6. **Parallel workstreams.** Two emails sent to two tracks simultaneously, unblocking both in parallel rather than serial approval.

## Result

- Erik's team coordinates DPP approval and metric schema
- Lidziya's team does OctoRoute onboarding and infrastructure design
- **Development is blocked** until both tracks produce written approval
- When approvals arrive, the code is written against a locked spec, not assumptions
- Future code reviews can reference the approval docs to verify compliance

## Common Mistake Avoided

**Bad approach:** Draft an adoption telemetry module before confirming the metric catalogue, identity mechanism, or OctoRoute endpoint.
→ Result: Rework when the platform team says "that's not the catalogue we use" or "that identity mechanism violates DPP."

**Right approach:** Blockers first, spec in writing, then code.
→ Result: Clean implementation, no compliance surprises.
