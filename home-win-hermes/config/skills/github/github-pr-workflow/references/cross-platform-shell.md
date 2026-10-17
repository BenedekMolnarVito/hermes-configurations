# Cross-Platform Shell Script Patterns

Patterns for writing shell scripts that work on both Windows (git-bash/MSYS) and macOS/Linux.

## OS Detection

```bash
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    # Windows git-bash
    export ANDROID_HOME="${ANDROID_HOME:-$(cygpath -u "${LOCALAPPDATA:-$HOME/AppData/Local}")/Android/Sdk}"
    export SMOKE_SCRATCH="${SMOKE_SCRATCH:-$(cygpath -u "${LOCALAPPDATA:-$HOME/AppData/Local}")/hermes/cache/scratch}"
    ;;
  *)
    # macOS / Linux
    export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}"
    export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
    export SMOKE_SCRATCH="${SMOKE_SCRATCH:-${TMPDIR:-/tmp}}"
    ;;
esac
```

## Idempotent PATH Prepend

Prevent duplicate PATH entries when the script is sourced multiple times:

```bash
_ts_prepend() { case ":$PATH:" in *":$1:"*) ;; *) PATH="$1:$PATH" ;; esac; }
for _d in "$ANDROID_HOME/cmdline-tools/latest/bin" "$ANDROID_HOME/emulator" "$ANDROID_HOME/platform-tools" "$HOME/.maestro/bin"; do
  _ts_prepend "$_d"
done
[ -n "${JAVA_HOME:-}" ] && _ts_prepend "$JAVA_HOME/bin"
# Collapse any duplicates already accumulated in this shell
PATH="$(printf '%s' "$PATH" | awk -v RS=: -v ORS=: '!seen[$0]++' | sed 's/:$//')"
export PATH; unset -f _ts_prepend; unset _d
```

## Windows PATH Length Limit

`cmd.exe` (used by `npm run` scripts) ignores PATH beyond ~8191 chars. Idempotent prepend prevents accumulation that breaks `vite`/`vitest` commands.

## Emulator Serial Lock

Always target emulator only, never physical devices:

```bash
export ANDROID_SERIAL="${ANDROID_SERIAL:-emulator-5554}"
```

## cygpath for Path Conversion

Convert Windows paths to POSIX in git-bash:

```bash
# Windows: C:\Users\name\AppData\Local → /c/Users/name/AppData/Local
cygpath -u "$LOCALAPPDATA"
```

## Shebang

Use `#!/usr/bin/env bash` for portability. Avoid `#!/bin/bash` on Windows git-bash.