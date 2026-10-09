# <Data Product / Topic> — Business Requirements from Stakeholder Discussion

**Source:** <transcript filename> (recorded <date>).
**Participants:** <name (role), ...>.
**Purpose:** Capture what the business wants the agent to know and do, so
`skills/<slug>/SKILL.md` (prompt) and the data wiring can be aligned. This is a
*requirements* reference, not a prompt edit. Prompt edits follow via the
`faa-analyst-skill-prompt-editing` skill once decisions are confirmed.

> Transcript-quality note: speakers are <accent/native-language> and the
> voice-to-text is imperfect. Likely mis-transcriptions are flagged inline as
> `[transcript: "<heard>" → probably <meaning>]`. Open questions are in §7.

---

## 1. Context — what is changing
<Background the agent should carry as context, not as a queryable fact. Note
provenance / architecture if the stakeholders explained it.>

**Requirement R1 — <name>.** <imperative statement of what must change> (type:
Prompt-context / Wiring-verify / Docs / Process / Feature).

## 2. New capabilities the agent must know about
### 2.x <capability>
<speaker, timestamp> — <what was said, distilled>.
**Requirement Rn — <name>.** <statement>.

## 3. Routing — when to use this DP vs. the other(s)
### 3.1 Signals that TRIGGER this data product
<keyword/scope signals>.
### 3.2 Exceptions / scope boundaries
<e.g. group-total stays on the other DP because of an access-control gap>.
**Requirement Rn — scope-aware routing.** <statement>.

## 4. Limitations / caveats (CRITICAL)
<access control, not-assigned portions, DAC/GCON scopes, refresh cycles>.
**Requirement Rn — communicate <caveat>.** <when the agent must warn, and when
it must NOT (scope threshold)>.

## 5. Data stability / refresh behavior
<actuals-only? plan figures? refresh-cycle impact?>.

## 6. Living model + change management
<planned enhancements; the field-rename notification handshake so the agent
isn't left self-fixing a renamed measure — the measure palette is hard-coded>.

## 7. Open questions for the user (REWRITE to "Resolved decisions" after clarify)
1. <the scope-reversing / ambiguous decision — ask, don't assume>
2. <wire names / measure names — placeholder until the model is published?>
...

## 8. Requirements summary & gap vs. current skill
| ID | Requirement | Type | vs. current `skills/<slug>/SKILL.md` |
|----|-------------|------|--------------------------------------|
| R1 | ... | Prompt (context) | New / Contradicts / Already present |

**Headline gaps the current skill does NOT yet handle:** <list>.

---

*Confirm the §7 open questions, then apply prompt edits via
`faa-analyst-skill-prompt-editing`; wiring/verify items via
`faa-data-product-wiring` / `faa-prodsteer-am-swap`.*
