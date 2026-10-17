# Calling TypeSafe JEV (System One `Choice`) for probe classification

The classifier the probe rubrics use. No SDK needed — raw HTTP works.

## Endpoint

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <TYPESAFE_API_KEY>
Content-Type: application/json
```

Body:
```json
{
  "state": {"response_text": "<verbatim run output>", "probe_id": "P1", "run_variant": "off"},
  "model": "jev-latest",
  "questions": {
    "verdict": {
      "type": "choice",
      "instructions": "<the judgment, stated in full>",
      "criteria": {"PASS_FULL": "<def>", "PASS_PARTIAL": "<def>", "FAIL": "<def>", "NA": "<def>"}
    }
  }
}
```

Response: `answers.verdict.choice` (bucket), `.probabilities` (map), `.confidence` (0..1).
Gate: confidence < 0.70 -> escalate that run to a human SME (do not silently accept).

## Getting the key when the Hermes tool shell can't see it

Hermes `execute_code`/`terminal` shells do NOT source the user's `~/.zshrc`, so a
key exported there (or in `~/.hermes/.env`) is absent from `os.environ`. Pull it
from a login shell, but read the env NUL-delimited — a `printf`/`echo` of the var
can be contaminated by rc banners (e.g. a 'Restored session:' line):

```python
import subprocess
raw = subprocess.run(["zsh","-lic","env -0"], capture_output=True, text=True).stdout
key = next((p[len("TYPESAFE_API_KEY="):] for p in raw.split("\0")
            if p.startswith("TYPESAFE_API_KEY=")), "").strip()
```

Never print the key value; only its presence/length. Key shape: `apikey_<hex>`.
