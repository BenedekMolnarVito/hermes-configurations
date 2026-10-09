# Classifying triage findings with the JEV API (TypeSafe System One)

When a triage/planning task has a **classification-type decision** — pick one label
from a fixed set, a yes/no, or a graded rating — decide it with a **JEV** call, not
with free-form agent reasoning. Typed output is auditable and calibrated; a plan that
says "the subagent decides the bucket" invites inconsistent, unverifiable labels.

The canonical FAA case: deciding which existing fix bucket a session's root cause
belongs to (Correctness / Domain Knowledge / Silent Failure). That is a `Choice`.

## Skill + live docs (source of truth — read before wiring)

- Skill: `skill_view("typesafe-ai")` (Jev is TypeSafe's flagship System One model).
- Live docs (Mintlify — append `.md` to any page path):
  - Choice primitive: https://docs.typesafe.ai/primitives/choice.md
  - HTTP API: https://docs.typesafe.ai/api.md
  - Python SDK: https://docs.typesafe.ai/sdk/python.md
- The live docs override anything below if they disagree; re-check the API version
  before relying on a field name.

## API contract (as of jev-1.13.x)

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`, header
  `Authorization: Bearer $TYPESAFE_API_KEY`, `Content-Type: application/json`.
- Body: `{ "state": <content>, "model": "jev-latest", "questions": { "<your-id>": {..} } }`.
  `state` is the content to judge (string, or a JSON object with named fields you
  reference in the question via backticked paths). You choose each question id; the
  answer comes back under the same id. **The id is never sent to the model** — put all
  meaning in `instructions`/`criteria`.
- Three question types:
  - **Choice** — one of a fixed set. `criteria` is `{option: description|null}` (≤255
    options). Answer: `choice`, `probabilities` (sum to 1), `confidence`.
  - **Noul** — yes/no. Answer: `noul` (0..1 probability of yes). A Noul near 0.5 means
    similar yes/no probability, NOT medium intensity.
  - **Score** — graded rating over an ordered `criteria` array of level descriptions
    (2..10 levels). Answer: probability-weighted `score`, `legend`, `probabilities`,
    `confidence`.
- Ask independent questions over the same `state` **together** — they run in parallel
  in one request and cannot see each other's answers. State each speculative premise
  explicitly; code consumes only the applicable answers.

## Python SDK

```bash
uv add typesafe-sdk   # TYPESAFE_API_KEY in env, server-side only — never hardcode
```

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

with TypeSafeClient() as client:
    resp = client.system_one(state=fact_sheet, questions={"bucket": BUCKET_CHOICE})
    ans = resp.answers["bucket"]      # or resp.choices["bucket"]
    ans.choice; ans.confidence; ans.probabilities
```

## Sharpen the question, not the label

- One narrow, coherent judgment per question. Split independently-useful dimensions
  (e.g. bucket vs. "was recursion the cause") into separate questions in the same call.
- Use structured object `criteria` (fields like `what` / `not_for` / `examples`) when
  two options are easily confused; a bare string per option is fine otherwise. The
  model sees the field names too, so name them to label the content.
- Include a no-match / "none of the above" option when nothing may fit.

## Confidence gate — code owns the routing, JEV owns the label

Subagents supply the evidence and consume JEV's typed answer; they do NOT substitute
their own label. Route on the numbers (thresholds are starting points — tune on the
real cases in front of you):

- `confidence >= 0.5` and no rival option > 0.25 probability → accept `choice`.
- otherwise → **escalate to the human** for the final label; record JEV's distribution.
- any rival option > 0.25 → note it as a secondary/cross-cutting label on the outcome.

Typed output guarantees the interface, not the truth — validate borderline cases with
a person. Confidence summarizes distribution concentration, not workflow correctness.

## Bucket Choice template (refine criteria against the buckets' real ticket definitions)

```python
BUCKET_CHOICE = Choice(
    instructions=("Given the root-cause analysis of one failed FAA agent session, "
                  "which existing fix bucket should the follow-up ticket go into?"),
    criteria={
        "correctness": {"what": "Wrong/incomplete numeric result: bad filters, wrong "
            "aggregation math, wrong hierarchy lookup, recursion-limit exhaustion that "
            "truncated a legitimate analysis.",
            "not_for": "Missing domain data/knowledge, or failures hidden from the user."},
        "domain_knowledge": {"what": "Lacked/misapplied domain knowledge: missing skill "
            "guidance, unknown value_help mapping, misunderstood P&L/product-steering "
            "concept, unwired data product.",
            "not_for": "Pure math/filter errors, or silent aborts with correct knowledge."},
        "silent_failure": {"what": "Aborted/looped/returned empty or degraded answer "
            "without surfacing the error (GraphRecursionError swallowed into an empty "
            "answer, value_help resolution that failed silently).",
            "not_for": "Wrong-but-complete answer (correctness), or knowledge genuinely "
            "absent (domain_knowledge)."},
    },
)
```

Discover the buckets' canonical Jira representation first (a `jira_search` for the
bucket names) so the follow-up lands in an EXISTING bucket and the `criteria` wording
matches reality.
