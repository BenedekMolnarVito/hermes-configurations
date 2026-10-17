---
name: jev-team-roles
description: "Use to triage tickets, bugs, OKRs, specs via Jev."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jev, team, tickets, bugs, okr, specs, triage, typesafe]
    related_skills: [jev-decisions, jev-engineering]
---

# Jev Team Roles

Triage tickets to teams, assess AC completeness, classify bug severity,
and score OKR alignment — all via JEV typed questions.

## When to Use

- Assigning an incoming ticket to the right team or owner.
- Scoring how complete and testable acceptance criteria are.
- Classifying a bug report's severity and checking duplicate likelihood.
- Evaluating how well a proposed feature or task aligns with OKRs.

Don't use for:
- PR code quality checks or test triage — use jev-engineering.
- Generic list classification — use jev-decisions.
- Executing Jira API calls or updating tickets — use the jira skill.

## How to Run

Do NOT answer from your own judgement when this skill applies — build the inputs
and call the matching script under `scripts/`.

```
python3 ~/.hermes/skills/jev-team-roles/scripts/ticket_triage.py --input job.json
python3 ~/.hermes/skills/jev-team-roles/scripts/ac_completeness.py --input job.json
python3 ~/.hermes/skills/jev-team-roles/scripts/bug_triage.py --input job.json
python3 ~/.hermes/skills/jev-team-roles/scripts/okr_align.py --input job.json
```

### ticket_triage job shape

```json
{
  "summary": "Login button broken on mobile",
  "description": "Users on iOS 17 cannot log in.",
  "teams": {"frontend": "Web/mobile UI", "backend": "API and auth", "qa": "Testing"}
}
```

Output: `{"status":"ok","results":{"team":"frontend","team_confidence":0.9,"priority_score":1.8}}`

### ac_completeness job shape

```json
{
  "title": "User can reset password",
  "acceptance_criteria": "Given user on login page, when they click reset, then email is sent."
}
```

Output: `{"status":"ok","results":{"completeness_score":2.1}}`

### bug_triage job shape

```json
{
  "summary": "App crashes on empty input",
  "description": "Steps: open form, submit empty, app crashes.",
  "severity_options": {"critical": "Data loss/crash", "major": "Broken feature", "minor": "Cosmetic"}
}
```

Output: `{"status":"ok","results":{"severity":"critical","severity_confidence":0.95,"duplicate_noul":0.1}}`

### okr_align job shape

```json
{
  "proposal": "Add dark mode to the app",
  "okrs": [
    {"key": "user_retention", "description": "Increase 30-day retention by 10%"},
    {"key": "dev_velocity", "description": "Ship 2 features per sprint"}
  ]
}
```

Output: `{"status":"ok","results":[{"okr_key":"user_retention","alignment_score":1.2}, ...]}`

## Notes

- jevlib is stdlib-only (no pip install needed).
- Requires `TYPESAFE_API_KEY` in the environment.
- On unavailability (no key, network error), scripts print `{"status":"jev_unavailable"}` — fail-open.
