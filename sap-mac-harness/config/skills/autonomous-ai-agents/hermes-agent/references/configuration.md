# Configuration, Toolsets & Voice

Edit with `hermes config edit` or `hermes config set section.key value`.
Full reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Config Sections (most-used keys)

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length`, `aliases` |
| `agent` | `max_turns` (90), `tool_use_enforcement`, `service_tier`, `verify_on_stop` |
| `terminal` | `backend` (local/docker/ssh/modal/daytona/singularity), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `interface` (cli/tui), `language`, `show_reasoning`, `show_cost`, `pet` |
| `approvals` | `mode` (smart/manual/off), `timeout`, `cron_mode` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral/elevenlabs/deepinfra) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts/gemini/piper/kittentts/deepinfra/xai) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider`, `write_approval` |
| `security` | `redact_secrets`, `website_blocklist` |
| `delegation` | `model`, `provider`, `max_concurrent_children`, `max_iterations` (50), `max_spawn_depth` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |
| `curator` | `enabled`, `consolidate` (false, opt-in aux-model consolidation), `interval_hours`, `stale_after_days` |

`hermes config check` reports sections missing from an older config.

### Context window for a custom / LiteLLM-proxied model is wrong (shows 200K, want 1M)

When a model is served through a `custom` provider (e.g. a LiteLLM / SAP AI Core
gateway at `localhost:PORT`), Hermes does NOT learn the window from the chat endpoint.
If the proxy's `/v1/models` list carries no `context_length` metadata (most do not),
Hermes falls back to a hardcoded FAMILY default — `"claude": 200000` — so a model the
gateway actually serves at 1M still displays 200K. Setting a top-level key will not fix
it: the resolver (`agent/model_metadata.py::get_model_context_length`, step 0c) reads a
PER-MODEL `context_length` inside the `custom_providers` entry.

Fix procedure:
1. Confirm the proxy's REAL cap (authoritative) — query its model-info endpoint, which
   exposes `max_input_tokens` per model (the `/v1/models` list does not):
   `curl -s -H "Authorization: Bearer $KEY_ENV" http://localhost:PORT/litellm/v1/model/info`
   Set `context_length` to that `max_input_tokens`, not a hopeful round number — raising a
   model above its true cap just invites overflow 400s. Caps are per-model (one gateway can
   serve opus-4.8 at 1M but haiku at 200K), so override only the models that genuinely report
   the larger window and leave the rest untouched.
2. Add `context_length: <N>` to each model under its `custom_providers` entry:
   ```yaml
   custom_providers:
     - name: Local (localhost:6655)
       base_url: http://localhost:6655/litellm/v1
       models:
         anthropic--claude-4.8-opus: {context_length: 1000000}
   ```
   An entry-level `context_length` (sibling of `base_url`) backs every model the entry serves
   when no per-model override exists — use it only when the whole gateway shares one cap.
3. This edit cannot go through `hermes config set` (it addresses dotted paths and cannot index
   into the `custom_providers` LIST), and the `patch`/`write_file` tools REFUSE `config.yaml`
   (security guard: "Agent cannot modify security-sensitive configuration"). Edit the file with
   a YAML-safe round-trip run under the Hermes venv, which has ruamel (host python usually does
   not): `cd ~/.hermes/hermes-agent && venv/bin/python <script>`. Back up first and either keep
   the diff to the exact leaf lines or accept that a full ruamel round-trip re-indents every
   sequence (valid YAML, parses identically, but a noisy diff) — a plain-text replace of just
   the `: {}` -> `: {context_length: N}` lines keeps the diff minimal.
4. Verify end-to-end with Hermes's own resolver before telling the user it's done — don't trust
   the file alone: `venv/bin/python -c "from agent.model_metadata import get_model_context_length as g; print(g('MODEL', base_url='BASE', provider='custom'))"`.
   Also re-run `python -c "import yaml; yaml.safe_load(open('~/.hermes/config.yaml'))"` to prove no indent corruption.
5. The window is read at session start, so the meter only updates on `/reset` or relaunch — tell the user.

No client-side `anthropic-beta: context-1m-2025-08-07` header is needed when going through a
LiteLLM gateway — the gateway opts in upstream. That beta lives in `anthropic_adapter.py` and
only fires on NATIVE Anthropic / Azure / Bedrock routes, never the OpenAI-compatible custom path.
If a gateway ever does require a client header, add it as `extra_headers:` on the
`custom_providers` entry (supported knob, merged onto the OpenAI client's default_headers).

### Toolsets

Enable/disable via `hermes tools` (interactive) or `hermes tools enable/disable NAME`.
Full enumeration: `TOOLSETS` dict in `toolsets.py` (`_HERMES_CORE_TOOLS` is the default bundle most platforms inherit).

| Toolset | What it provides |
|---------|-----------------|
| `web` / `search` | Web search + extraction / search-only subset |
| `browser` | Browser automation (Browserbase, Camofox, or local Chromium) |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `coding` | Code-editing helpers (LSP-backed) |
| `computer_use` | Desktop GUI control (cua-driver) |
| `vision` | Image analysis |
| `image_gen` | Image generation and image-to-image editing |
| `video` / `video_gen` | Video analysis / video generation |
| `x_search` | X (Twitter) search (X OAuth or API key) |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `context_engine` | Pluggable context-engine hooks |
| `project` | Named multi-folder workspace tools |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `todo` | In-session task planning |
| `kanban` | Multi-agent work-queue tools (gated to workers) |
| `debugging` | Extra introspection tools (off by default) |
| `safe` | Minimal low-risk toolset for locked-down sessions |
| `spotify`, `discord`, `discord_admin`, `feishu_doc`, `feishu_drive`, `yuanbao` | Service integrations (gated on their credentials). `homeassistant` (`ha_*` tools) is not built in: it comes from the `homeassistant` catalog plugin (`hermes plugins install homeassistant`) |

Tool changes take effect on `/reset` (new session) — never mid-conversation, to preserve prompt caching.

## Voice

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

```yaml
stt:
  enabled: true
  provider: local   # local (faster-whisper, free) | groq | openai | mistral | elevenlabs | deepinfra
  local:
    model: base     # tiny, base, small, medium, large-v3, turbo
```

Auto-detect priority: local faster-whisper (`python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"`) → Groq (`GROQ_API_KEY`, free tier) → OpenAI (`VOICE_TOOLS_OPENAI_KEY`) → Mistral Voxtral (`MISTRAL_API_KEY`).

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS (default) | None | Yes |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral | `MISTRAL_API_KEY` | Paid |
| Gemini | `GOOGLE_API_KEY` | Free tier |
| NeuTTS / Piper / KittenTTS (local) | None | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.
