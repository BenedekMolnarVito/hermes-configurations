# Runner brief — execute smoke suite  (dispatch to QUICK/lowest tier)

You only RUN and REPORT. Do not edit code, scenarios, or the harness. Do not judge from screenshots.

## Setup (already done by parent unless stated)
- Target device: <serial> ONLY (export ANDROID_SERIAL=<serial>; pass -s <serial> to every adb call). Another
  physical device may be attached — never touch it.
- Fresh debug APK + any helper APK installed. Listener/permissions granted.

## Run
<exact command, e.g. cd .maestro/smoke && python harness.py --fresh --only <ids>>  (timeout 600)

## Report (this text is all the parent sees — keep it short)
RESULT: <n_pass>/<n_run> PASS   (report.json: <path>)
For each FAIL/ERROR, one block:
  <id>: <assertion that failed>
    expected: <value>   got: <value>
    evidence: <out/<id>_dom.json path + the 1-3 relevant DOM lines/rows>
    suspect: <file:line hint from the scenario, or 'scenario drift' if a testid/url changed>
If the harness itself aborted (no device, no key, CDP socket missing), say so in one line with the error — never invent results.
