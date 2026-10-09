---
name: hermes-local-model-backend
description: "Point Hermes at a local Ollama/llama.cpp model."
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, local-models, ollama, docker, apple-silicon, custom-provider, config]
---

# Hermes on a Local Model Backend

Wire Hermes to a model running on the user's own hardware via an OpenAI-compatible
endpoint (Ollama, llama.cpp, MLX, LM Studio). Covers the two things that actually
bite: Hermes' minimum context-window gate, and the Apple-Silicon + Docker networking
split. For the desktop one-click managed-runtime path see the `hermes-agent` bundled
skill / docs `user-guide/local-models`; this skill is the manual CLI/headless path.

## Hard constraints to state up front

- HERMES REQUIRES A MODEL ADVERTISING >=64K CONTEXT. Below that, Hermes refuses to
  send: "context window of N tokens, which is below the minimum 64,000 required."
  This is a startup gate, not a runtime warning — the model never gets called.
- APPLE SILICON: Docker on macOS CANNOT reach the Metal GPU (containers run in a
  Linux VM with no GPU passthrough). So the MODEL SERVER must run NATIVELY on macOS
  to be GPU-accelerated; only CPU-bound layers (an agent harness) belong in a
  container. Do not containerize the model on a Mac and expect GPU speed.

## Procedure — point Hermes at a native Ollama model

1. Ensure Ollama listens where the client can reach it. Default bind is 127.0.0.1,
   invisible to containers. For host-only use it is fine; for a container client set
   `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"` (macOS) and restart `ollama serve`.
   Verify: `curl http://localhost:11434/v1/models`.
2. CLEAR THE 64K GATE (see next section) BEFORE wiring Hermes — otherwise the first
   chat fails and looks like a connection bug when it is a capability gate.
3. Configure the custom provider (never hand-edit config.yaml; use `hermes config set`):
   - `hermes config set model.provider custom`
   - `hermes config set model.base_url "<endpoint>/v1"` (see networking note for the host)
   - `hermes config set model.model "<model-name>"`
   - Ollama ignores the key but Hermes wants one present: put a dummy in `$HERMES_HOME/.env`
     (e.g. `CUSTOM_API_KEY=ollama-local-dummy`) and `hermes config set model.api_key '${CUSTOM_API_KEY}'`.
4. Set a generous timeout for slow local inference — it is an ENV VAR, not a config key:
   add `HERMES_API_TIMEOUT=1800` to `$HERMES_HOME/.env`.
5. Verify end-to-end with a real call: `hermes chat -q "Reply in one sentence and name your model."`
   A cold 20GB+ model load can take 60-90s on first call — run it backgrounded with a
   long timeout, do not assume a hang.

## The 64K context gate — the fix that actually works

Every Ollama qwen2.5 GGUF (14b AND 32b) advertises only 32768 in
`model_info.context_length`, so all sizes fail the gate. The GGUF architecture
metadata caps at 32K regardless of the model's theoretical 128K capability.

WORKING FIX (documented in Hermes docs `guides/local-ollama-setup`): create a
Modelfile that raises the runtime context, then rebuild under a new tag — Hermes
gates on the effective `num_ctx`, which the override does set:

    cat > Modelfile <<'EOF'
    FROM qwen2.5:32b
    PARAMETER num_ctx 64000
    EOF
    ollama create qwen2.5-32b-64k -f Modelfile   # reuses existing blobs, no re-download

Then point Hermes at the NEW name (`qwen2.5-32b-64k`), not the base tag.

- Do NOT confuse `model_info.context_length` (baked GGUF metadata, unchangeable via
  Modelfile — still shows 32768) with the `parameters` `num_ctx` (what Hermes uses).
  Checking only the metadata will make you wrongly conclude the fix failed.
- Models with native >=64K in their GGUF metadata (Llama 3.1/3.3, Mistral-Small)
  need NO override — prefer them if the user has no model preference. If the user
  insists on a specific family that advertises 32K (e.g. qwen2.5), use the Modelfile
  override rather than substituting a different model.
- Do not burn a multi-GB re-download probing sizes: the context limit is per-FAMILY
  metadata, so a smaller sibling (qwen2.5:14b) tells you what the 32b will advertise.
- THE GATE IS A RUNTIME CHECK, not just metadata. Newer Hermes inspects the window
  Ollama actually LOADED (`ollama ps` CONTEXT column). A model whose GGUF advertises
  <64K (e.g. qwen3:32b at 40960) is refused with "Ollama runtime context is too small"
  EVEN with a `custom_providers[].models.<id>.context_length` override — that override
  only affects Hermes' displayed number, not the loaded window. The Modelfile
  `num_ctx` bake is what makes Ollama load the wider window, so it is the reliable fix
  for ANY family, qwen2.5 and qwen3 alike. The error message names `model.ollama_num_ctx`
  / `model.context_length` keys, but those are top-level `model.*` keys; the Modelfile
  route works regardless of whether the model is reached via top-level config or a
  custom_providers entry.

## Networking: native vs Docker client

The base_url host depends on WHERE Hermes runs, not where Ollama runs:
- Hermes native on the same Mac  ->  `http://localhost:11434/v1`
- Hermes inside a Docker container -> `http://host.docker.internal:11434/v1`, and the
  compose service needs `extra_hosts: ["host.docker.internal:host-gateway"]` or the
  name does not resolve. Getting this backwards yields "connection refused".

## Hermes-in-Docker (long-running worker on a Mac)

When the user wants containerized long-running workflows against the native model:
- Dockerfile: `python:3.12-slim` + `curl git ca-certificates tmux`, install via
  `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`. The installer
  symlinks `hermes` into `/usr/local/bin` — no PATH juggling needed. `CMD ["sleep",
  "infinity"]` keeps the container alive for detached work.
- compose: mount `./data:/data` with `HERMES_HOME=/data/.hermes` and `./workspace:/workspace`
  so sessions/memory/skills and outputs survive restarts; `extra_hosts` as above.
- The container's Hermes is a SEPARATE instance from the user's interactive Hermes —
  its own empty memory/skills/sessions. Say so; the user should not expect their
  personal config to carry in.
- Build/install steps are long and can be misread as a server by the terminal tool;
  run `docker compose build` backgrounded with notify, do not foreground it.

## Giving the user a switchable local provider (use custom_providers, NOT a bare alias)

To give the user `/model` access to the local model, add a `custom_providers` entry —
NOT a `model.aliases.<name>` block. A bare alias with its own base_url is resolved as
a plain model NAME against whatever provider is already active; `--model <alias>` (and
the picker) do NOT switch the endpoint to the alias's base_url, so the request lands on
the user's current cloud provider and 400s ("invalid model"). A `custom_providers` entry
is what actually rebinds the endpoint AND what the `/model` picker lists.

    custom_providers:
      - name: <Display Name>            # this string is what shows in /model and is the --provider value
        base_url: http://localhost:11434/v1   # localhost = user's native Hermes, NOT host.docker.internal
        key_env: CUSTOM_API_KEY               # reuse the dummy-key env var
        model: <default-model>
        models:
          <model-name>: {}                    # add one entry per model; {} = use native metadata
          <model-name-2>: { context_length: 65536 }   # per-model context override lives here

Editing a nested list via `hermes config set` is awkward; edit config.yaml with a
yaml-safe script (back it up first) or `hermes setup`'s Custom Endpoint flow. After a
write, run `hermes config check` (no errors = valid) before testing.

- Aliases do NOT appear in the `/model` picker; custom_providers DO. If the user says
  "I added it but don't see it in the list," you used an alias — convert to a
  custom_providers entry.
- `custom_providers[].models.<id>.context_length` is the documented display/context
  override, but on Ollama it does NOT force the runtime window — see the 64K gate note.
See `hermes-model-tier-routing` for the built-in tier aliases (deep/standard/quick).

## Choosing a local model for AGENTIC (tool-calling) work — model choice beats config

A local model that chats fine may still be unable to DRIVE Hermes' tools. This is a
model-capability ceiling, not a config bug — do not chase it with toolset/reasoning
tweaks past one attempt.

- VERIFY THE FULL AGENTIC FLOW, not a raw single tool call. Both a working and a
  broken model return a valid `tool_calls` array for a one-shot `/v1/chat/completions`
  probe. The discriminating test is a multi-step run THROUGH Hermes (e.g. "write a file
  then read it back"): run `hermes chat -q ...` and confirm the side effect actually
  happened (the file exists). Check `hermes logs --level WARNING` for the session id.
- FAILURE SIGNATURE: repeated `tool_call requires 'calls' (an array of {name,...})`
  and `repeated_exact_failure_warning; count=N` in the logs. The weak model fixates on
  Hermes' `tool_call`/`tool_search` DEFERRED-TOOL meta-tool and mis-fills its nested
  `{"calls":[...]}` schema, looping without progress. A lean `-t terminal,file` toolset
  and `--reasoning low` do NOT fix it — tested.
- Qwen3 family is WEAK at Hermes tool calling (reasoning interleaving corrupts the
  call JSON). gemma4:31b handles the same flow cleanly (3 valid calls, file created,
  zero errors) — the Ollama `local-ollama-setup` guide calls it the reliable
  tool-caller. When the user needs local agentic work, reach for gemma4:31b (or another
  model with a strong tool-calling reputation) over a Qwen3 thinking model.
- Require the `tools` capability (`curl .../api/show -d '{"model":"<m>"}'` →
  `capabilities`). gemma4:31b also advertises 262144 native context, so it clears the
  64K gate with NO Modelfile override — a second reason to prefer it.
- Split by strength: keep a thinker (qwen3) for reasoning/chat and a tool-caller
  (gemma4) for agentic runs, both as models under the one custom_providers entry.

## Reasoning (thinking) models

A reasoning model emits a chain-of-thought Hermes can render. Wiring is identical to
any other Ollama model; two extra points:

- Ollama exposes the trace as a separate `reasoning` field on the OpenAI response
  (NOT `<think>` tags in `content`). Hermes reads that field. If a probe shows empty
  `content`, raise `max_tokens` — a low budget gets fully consumed by the thinking phase.
- SCOPE REASONING PER-MODEL, never globally. `agent.reasoning_effort` is a GLOBAL
  default that would also change the user's cloud/default model's behavior. Use a
  per-model override so only the local thinker reasons:

      agent:
        reasoning_overrides:
          <model-name>: medium    # none|minimal|low|medium|high|xhigh|max|ultra

  Recent Hermes DOES propagate `reasoning_effort` to Ollama custom providers (top-level
  field + `extra_body.think` for base_urls recognized as Ollama).
- Reasoning HELPS math/analysis but HURTS tool-call JSON (thinking leaks into the
  call). For a dual-mode model doing tool work, keep effort low or off.

## Honest caveat to give the user

A local 32B at 64K on a 48GB Mac is comfortable but noticeably slower than cloud for
tool-heavy agent runs — good for background workflows, less so for snappy interactive
use. Offer a cloud fallback (`fallback_providers`) rather than overselling local speed.
