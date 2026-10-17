---
name: jev-team-roles
description: Triage tickets to teams, score acceptance-criteria completeness, classify bug severity/duplicates, score OKR alignment via TypeSafe JEV. Use for incoming tickets, bug reports, specs, proposals.
---

# Jev Team Roles

Triage tickets to teams, assess AC completeness, classify bug severity, score OKR alignment. JEV typed questions.

## When to Use

- Incoming ticket → right team/owner.
- Score AC completeness/testability.
- Bug report → severity + duplicate likelihood.
- Feature/task alignment with OKRs.

Don't use:
- PR code quality / test triage → jev-engineering.
- Generic list classification → jev-decisions.
- Jira API calls / ticket updates → jira skill.

## How to Run

Do NOT answer from own judgement when skill applies. Build inputs, call matching script.

Write job JSON to `.agent/scratch/` or scratchpad (not repo tree).

```
python ~/.claude/skills/jev-team-roles/scripts/ticket_triage.py --input job.json
python ~/.claude/skills/jev-team-roles/scripts/ac_completeness.py --input job.json
python ~/.claude/skills/jev-team-roles/scripts/bug_triage.py --input job.json
python ~/.claude/skills/jev-team-roles/scripts/okr_align.py --input job.json
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

- jevlib stdlib-only, no pip.
- Needs `TYPESAFE_API_KEY` in env.
- Unavailable (no key, network error) → `{"status":"jev_unavailable"}`. Fail-open.
