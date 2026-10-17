---
name: local-model-hosting-apple-silicon
description: "Host a local LLM on Apple Silicon; wire Docker clients."
version: 1.0.0
---

# Hosting a Local Model on Apple Silicon + Connecting Clients

Stand up a local LLM on an Apple Silicon Mac (M-series) and wire a client
— often an agent harness or app running in Docker — to it over an
OpenAI-compatible API. The defining constraint shapes the whole topology.

## Hard constraint: no GPU in Docker on macOS

Docker Desktop on macOS runs containers inside a Linux VM with NO Metal/GPU
passthrough. A model running INSIDE a container on a Mac is CPU-only — slow and
wasteful of unified memory. Therefore:

- Run the MODEL SERVER natively on macOS (Ollama / llama.cpp / LM Studio / MLX)
  so it uses the GPU.
- Containerize only the CLIENT / agent harness (orchestration + I/O is CPU-bound
  and fine in a container).
- The container reaches the host model at `http://host.docker.internal:11434`
  (Ollama's default port). This is the opposite of Linux+NVIDIA, where you
  containerize everything.

## Procedure (Ollama native + client in Docker)

1. Install & expose Ollama on the Mac:
   - `brew install ollama`
   - `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"` — REQUIRED. Default is
     127.0.0.1, which the Docker VM cannot reach; without this the container
     gets connection-refused.
   - `ollama serve` (or `brew services start ollama` for always-on).
2. Pull a model sized to unified memory, MINDING THE CONTEXT GATE below.
   Verify: `ollama run <model> "hi"` and
   `curl http://localhost:11434/v1/models`. A large pull that dies partway
   (network/DNS drop) is not lost — just re-run `ollama pull <tag>`; it resumes
   from the last completed blob rather than restarting.
3. Build the client container so it can reach the host:
   - compose MUST include `extra_hosts: ["host.docker.internal:host-gateway"]`
     or the container cannot resolve the host at all.
   - Mount volumes for persistence (config/state and workspace) so sessions and
     output survive `docker compose down`.
   - Keep the container alive with `command: sleep infinity` for a long-running
     worker; exec in with `docker compose exec <svc> bash`.
4. Point the client at the model as an OpenAI-compatible endpoint:
   base_url `http://host.docker.internal:11434/v1`, model = exact `ollama list`
   tag, api_key = any dummy string (Ollama ignores it, but clients that require
   a key need one present).
5. Verify END-TO-END with a real query through the client, not just a curl —
   the model-capability gates (below) only fire on a real completion.

## Pitfalls

- Advertised context window is a hard gate for some clients. Hermes Agent
  REFUSES any model whose EFFECTIVE context window is below 64K tokens
  (`"...below the minimum 64,000 required..."`). ALL Ollama qwen2.5 GGUF builds
  (14b AND 32b) declare only 32768 in `model_info.context_length`, so the base
  tag is rejected out of the box. TWO fixes, either works:
  1. Preferred / cheapest — override `num_ctx` with a Modelfile and re-create the
     model (reuses existing blobs, no re-download):
     `printf 'FROM qwen2.5:32b\nPARAMETER num_ctx 64000\n' > M && ollama create qwen2.5-32b-64k -f M`,
     then point the client at the NEW tag. This IS the documented, working fix
     (Hermes reads the effective num_ctx and accepts it) even though
     `model_info.context_length` still prints 32768 — do not be fooled into
     thinking the override failed by reading that field.
  2. Choose a model whose build advertises ≥64K natively (llama3.1:8b/3.3,
     mistral-small:24b are native 128K in `model_info`; qwen2.5 is NOT).
  Check before wiring: `curl -s http://localhost:11434/api/show -d '{"model":"<tag>"}'`
  and read `model_info`'s `*.context_length`; for a num_ctx override read the
  `parameters` block instead.
- RUNTIME context gate is separate from and stricter than the advertised one.
  Newer Hermes ALSO checks the window Ollama actually LOADED the model with
  (`ollama ps` CONTEXT column), not just the declared metadata, and refuses with
  "Ollama runtime context is too small... needs at least 64000". A
  `custom_providers[].models.<tag>.context_length` override does NOT satisfy this
  — that only sets the DISPLAY window. The fix that always works is baking
  `PARAMETER num_ctx 65536` into the model via Modelfile + `ollama create`
  (above) so Ollama loads it wide every time. This bit especially with thinking
  models (qwen3) whose default tags load at 40960. Loading a ~20GB model at a
  64K window takes noticeably longer than at the default (~2-3min cold on
  Metal), because the KV cache allocation scales with the window.
- Local 20–32B on Metal is not instant: first message after a model switch
  takes ~90s (cold load of a ~20GB model), then it stays resident ~15min idle.
  Set `HERMES_API_TIMEOUT=1800` in `$HERMES_HOME/.env` (env var, NOT a
  config.yaml key) so slow local generations do not time out.
- Model size vs unified memory: a Q4 model needs roughly its GB size resident.
  ~20GB (qwen2.5:32b) is comfortable on 48GB; a 70B (~43GB Q4) needs 64GB+ or it
  swaps and crawls. Ask the user's RAM before recommending a size. Rough budget:
  weights (once) + parallel_requests x KV-cache-per-slot + OS (~9GB on macOS);
  keep the total under ~75% of RAM (the default Metal GPU allocation cap, tunable
  via `sysctl iogpu.wired_limit_mb`).

## Subagents / concurrency memory model (answer the "do subagents multiply RAM?" question)

The intuition that N subagents each need their own model copy is WRONG, and the
real cost driver is concurrency, not agent count:

- Model WEIGHTS load ONCE into unified memory and are SHARED by every request —
  the main agent and all subagents hit the same single loaded Ollama instance.
  Spawning N subagents does NOT load N copies of the weights; the ~20GB is paid once.
- A context window costs KV-CACHE memory PER CONCURRENT inference (~4-8GB at 64K),
  not per subagent. Sequential subagents reuse one context slot -> flat memory;
  PARALLEL ones each need a slot -> memory grows by ~KV-per-slot each.
- The concurrency ceiling is `OLLAMA_NUM_PARALLEL` (default small). Ollama QUEUES
  requests beyond that rather than crashing, so many subagents cost TIME (they
  serialize through limited slots), not a RAM explosion. Cap it deliberately on
  constrained RAM: `launchctl setenv OLLAMA_NUM_PARALLEL 2` then restart ollama
  (~2-3 concurrent 20GB-model inferences is comfortable on 48GB).
- Separate caveat: each subagent is its own agentic loop, so a local model's
  slow tok/s multiplies across a fan-out — local subagent fan-out is workable but
  slow; steer heavy parallel subagent work to a cloud model.
- `python:3.12-slim` has no PyYAML or other extras — read config files with
  `grep`/text tools, not an ad-hoc `python3 -c 'import yaml'`.
- A dotted config key like `qwen2.5:14b` may read back as "not set" from a
  dot-path config getter that splits on the `.`; confirm the value by reading
  the config file directly rather than trusting the getter.

## Hermes-in-Docker specifics

- Install inside the image with the official installer
  (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`); it
  links `hermes` into `/usr/local/bin`, so no PATH gymnastics are needed.
- Set `HERMES_HOME` to a mounted path (e.g. `/data/.hermes`) so config, sessions,
  memory, and skills persist and start empty/isolated from the host's Hermes.
- Wire the model:
  `hermes config set model.provider custom`;
  `hermes config set model.base_url "http://host.docker.internal:11434/v1"`;
  `hermes config set model.model "<ollama-tag>"`;
  dummy key in `$HERMES_HOME/.env` +
  `hermes config set model.api_key '${CUSTOM_API_KEY}'` (settings in config.yaml,
  secret in .env).
- The container's Hermes is a SEPARATE instance from any interactive one — its
  own memory/skills/sessions. Intended for an isolated long-running worker.
- Long-running work: `hermes chat -q "..."` fire-and-forget, or `tmux` +
  `hermes` (detach Ctrl-b d, reattach `tmux attach`); `sleep infinity` +
  mounted volumes keep it alive across restarts.

## Reasoning / thinking models (qwen3, deepseek-r1, qwq, etc.)

An instruct model (qwen2.5) CANNOT reason no matter how it is wired — the model
itself must carry the `thinking` capability. Confirm with
`curl -s http://localhost:11434/api/show -d '{"model":"<tag>"}'` and check
`capabilities` includes `thinking` (and `tools` for agent use).

- Ollama exposes the chain-of-thought over the OpenAI `/v1` endpoint as a
  SEPARATE `reasoning` field on the message (NOT `<think>` tags in `content`,
  NOT `reasoning_content`). Hermes reads that field and renders the thinking
  trace. Verify with a real completion and a GENEROUS `max_tokens` (1500+): a
  thinking model can spend the whole budget reasoning and return empty `content`
  if the budget is small, which looks like a failure but is not.
- Reasoning depth is controlled by `agent.reasoning_effort`
  (none/minimal/low/medium/high/xhigh/max/ultra). Recent Hermes DOES propagate
  this to Ollama custom providers (top-level `reasoning_effort`, plus
  `extra_body.think` for base_urls recognized as Ollama — `localhost:11434`
  qualifies).
- SCOPE reasoning to the local model, never globally. `agent.reasoning_effort`
  is a GLOBAL default and will change the user's OTHER models (e.g. their
  default cloud model) too. Use a per-model override instead:
  `agent.reasoning_overrides: {"<tag>": "medium"}` (bare model tag works). Leave
  the global `reasoning_effort` unset so non-local models keep provider default.
- qwen3 is dual-mode (thinks on demand); deepseek-r1 always reasons. Both need
  the 64K runtime window (bake num_ctx as above) since their default tags load
  below it.

## Tool-calling reliability: local reasoning models are for chat/reasoning, NOT Hermes agentic work

Wiring a local reasoning model to work as a chat/reasoning model does NOT mean it
can drive Hermes's tools. Treat these as separate capabilities and set the user's
expectation up front:

- The failure signature is the model looping on Hermes's `tool_call` deferred-tool
  meta-tool with the wrong argument shape:
  `tool_call requires 'calls' (an array of {name, arguments})`, repeated with
  identical args (`repeated_exact_failure_warning; count=N`), producing no side
  effect. Root cause is a CAPABILITY CEILING, not a config bug: a local ~32B
  cannot reliably fill Hermes's nested meta-tool schemas (`tool_call`/`tool_search`,
  delegation, MCP), and reasoning models make it worse by leaking chain-of-thought
  into the tool-call JSON.
- This is NOT fixed by a leaner toolset or lower reasoning. `-t "terminal,file"`
  plus `--reasoning low` still looped in testing. Do not present toolset-trimming
  as a reliable fix for a model that fails this way.
- The model itself is fine at simple calls: a raw `/v1/chat/completions` with ONE
  flat-schema tool returns a clean `tool_calls` array (`finish_reason: tool_calls`).
  The breakdown is specific to Hermes's complex meta-tools, so a raw-endpoint tool
  test PASSING does not prove the model works agentically in Hermes.
- VERIFY tool-calling with an independent side-effect check, never the model's own
  words: ask it to create a file, then check the file exists on disk. A transcript
  that says "I created it" while `ls` shows nothing is the real signal.
- Validated split of responsibilities (recommend this): use the local reasoning
  model for chat and thinking-heavy Q&A, and a strong cloud model for agentic /
  tool-driven work. Keep both as `/model` options. Before pulling another large
  model "to fix tool calling," tell the user this ceiling is inherent to small
  local models with this harness so they can choose whether the download is worth
  it; models marketed for tool use (gpt-oss, gemma-class) MAY do better but are
  unproven here — offer as a test, not a promise.

## Calling the model from inside the container (client-agnostic)

- Smoke test: `curl -s http://host.docker.internal:11434/v1/chat/completions -H
  "Content-Type: application/json" -d '{"model":"<tag>","messages":[{"role":"user","content":"ping"}]}'`
- Python: `OpenAI(base_url="http://host.docker.internal:11434/v1",
  api_key="ollama")` then `chat.completions.create(...)`.

## Adding a switchable local provider to an INTERACTIVE Hermes

When the user wants their own (native, non-container) Hermes to be able to
`/model`-switch to the local Ollama model:

- Native Hermes uses `http://localhost:11434/v1` — NOT `host.docker.internal`
  (that hostname only exists inside a container). Same model server, different
  route per client.
- Add it as a `custom_providers` LIST ENTRY, never as a `model.aliases` entry:
  - A `model.aliases.<name>` with its own `base_url` does NOT switch the
    endpoint on the `hermes chat --model <name>` path — the name is resolved as
    a bare model string against the CURRENT provider, which then rejects it
    (e.g. an unrelated proxy returns HTTP 400 "invalid model"). Aliases also do
    not appear in the `/model` picker.
  - `custom_providers` entries DO appear in `/model` and switch the base_url +
    key correctly. Shape (append to the `custom_providers:` list):
    `{name: "<Display Name>", base_url: "http://localhost:11434/v1",
    key_env: CUSTOM_API_KEY, model: "<tag>",
    models: {"<tag>": {context_length: 64000}}}`. The per-model
    `context_length` here is also honored by the `/model` switch.
- There is no non-interactive CLI to add a custom provider (`hermes setup` is a
  curses wizard). Edit `config.yaml` programmatically instead: back it up, load
  with PyYAML using Hermes's OWN venv python
  (`~/.hermes/hermes-agent/venv/bin/python` — the system/slim python may lack
  yaml), append the dict, `yaml.safe_dump(..., sort_keys=False)`, then validate
  with `hermes config check`.
- Verify by routing a real query explicitly:
  `hermes chat -q "name your model" --provider "<Display Name>" --model "<tag>"`.
  A wrong-endpoint failure surfaces as an error from the OTHER provider's host
  (e.g. a `url.sap` 400), which is the tell that the switch did not take.
