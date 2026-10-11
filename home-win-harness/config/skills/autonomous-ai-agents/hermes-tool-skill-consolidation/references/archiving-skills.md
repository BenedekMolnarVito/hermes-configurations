# Archiving skills (reversibly)

## Curator only touches AGENT-created skills

`hermes curator archive <name>` works ONLY on skills with
`created_by: agent` provenance. Bundled and hub skills are curator-off-limits
(it never deletes or archives them). So the creative/unused bundled skills
cannot be hidden via curator. Check origin first: `hermes curator usage`
(columns: origin = agent|bundled|hub|local).

## `hermes skills opt-out` is all-or-nothing — do NOT use for selective hiding

`hermes skills opt-out` writes a `.no-bundled-skills` marker that stops
seeding ALL bundled skills; `--remove` DELETES every unmodified bundled skill.
That nukes useful bundled skills (hermes-agent, systematic-debugging, etc.)
to hide a few creative ones. Wrong tool for selective work.

`hermes skills config` is the interactive per-skill enable/disable, but it has
NO flags — you cannot script it from a session.

## The reversible method: move directories to a holding folder

Move each unwanted skill's directory (the one containing SKILL.md) into
`~/.hermes/skills_disabled/`, PRESERVING its relative path so restore is a
trivial reverse-move. This works for bundled, agent, and local skills alike
and touches nothing else.

```bash
cd ~/.hermes/skills
DEST=~/.hermes/skills_disabled
mkdir -p "$DEST"
for name in <skill-names>; do
  dir=$(find . -type d -name "$name" -exec test -f "{}/SKILL.md" \; -print | head -1)
  [ -z "$dir" ] && { echo "NOT FOUND: $name"; continue; }
  rel="${dir#./}"
  mkdir -p "$DEST/$(dirname "$rel")"
  mv "$dir" "$DEST/$rel"
  echo "archived: $rel"
done
```

Restore one: `mv ~/.hermes/skills_disabled/<cat>/<name> ~/.hermes/skills/<cat>/`

## Caveat to tell the user

Moved skills are no longer curator-tracked. `hermes update` won't re-seed the
bundled ones while they sit in skills_disabled, but a `hermes skills reset`
flow could re-pull bundled skills — warn them, and re-run the move if so.

## Duplicate handling (bundled vs superpowers/plugin)

When a bundled skill duplicates a superpowers (plugin) skill
(systematic-debugging, test-driven-development, requesting-code-review), keep
the plugin version (actively maintained; lives under
`~/.hermes/plugins/<plugin>/skills/` and is untouched by moving the bundled
copy) and archive the standalone bundled copy. Confirm the plugin copy exists
first: `ls ~/.hermes/plugins/superpowers/skills/`.

## Sharpening overlapping triggers instead of archiving

When skills are NOT duplicates but their triggers overlap (e.g. a GitHub
cluster: pr-workflow / code-review / issues / repo-management / auth /
issue-to-pr / enterprise), don't archive — rewrite each `description:` to a
disjoint "Use when … (other case -> other-skill)." trigger so routing is
unambiguous. Patch the frontmatter description only. Safe on agent/local
skills; on bundled skills it marks them user-modified — flag to the user.
