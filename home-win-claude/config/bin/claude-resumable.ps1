# Launch Claude Code with the resumer channel enabled, so a session stopped by a
# rate limit is automatically continued when the limit resets.
# The resumer plugin is third-party (not on Anthropic's approved channel list),
# hence the development-channels flag. Keep this terminal window open while waiting.
# Usage: claude-resumable [any claude args, e.g. --add-dir C:/path/repoB]
& claude --dangerously-load-development-channels plugin:resumer@wong2-plugins @args
