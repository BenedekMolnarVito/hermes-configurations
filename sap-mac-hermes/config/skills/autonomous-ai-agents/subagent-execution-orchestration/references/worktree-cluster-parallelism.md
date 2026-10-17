# Worktree-cluster parallelism — setup & guards

Mechanics for running file-disjoint task clusters in parallel on separate worktrees.
Use after you have VERIFIED two clusters' file-touch sets are disjoint (empty intersection).

## Create the cluster worktree + branch off the current impl head

```bash
WT=/path/to/scratch/wt-<cluster-name>
git worktree add -b <cluster-branch> "$WT" <impl-branch-or-head-sha>
git -C "$WT" rev-parse --abbrev-ref HEAD   # confirm the branch
# confirm the cluster's files are untouched vs the base (empty diff = good):
git -C "$WT" diff --stat <base-branch> -- <cluster file paths...>
```

Basing the cluster branch off the impl-branch HEAD (not raw base) keeps a single lineage
so the final merge brings only the cluster's own commits.

## node_modules is NOT shared across worktrees

A fresh worktree has no `node_modules`. Run the install INSIDE the worktree before the
child can test/build, or the child's `npm run test` fails on missing deps:

```bash
cd "$WT" && npm ci     # (or the project's install command)
```

## Scratch-file leak guard (brief/instruction files)

If you copy per-task brief files into the worktree for the child to read, they show as
UNTRACKED there. The child commits specific files, but if it ever runs `git add -A`,
those scratch files leak into a commit. After each cluster commit, verify no scratch/doc
files landed:

```bash
git -C "$WT" show --stat <sha> | grep -E 'brief|instructions|globals|report|\.superpowers' \
  && echo 'LEAK' || echo 'clean'
```

Prefer putting briefs under a git-ignored path (the plan workspace, e.g. `.superpowers/`),
not inside the worktree, so they can never be staged.

## Merge the cluster back (conflict-free by construction)

From the impl branch:

```bash
git merge --no-ff <cluster-branch> -m "merge(<cluster>): integrate ..."
# a file-disjoint merge touches ONLY the cluster's files and reports ZERO conflicts;
# if git reports a conflict, the disjointness assumption was WRONG — stop and re-check
# the file-touch sets, do not --force past it.
```

Then run the full suite + build on the MERGED tree before the final review — green on each
cluster separately does not prove green together.

## Clean up

```bash
git worktree remove --force "$WT" && git worktree prune
git branch -d <cluster-branch>     # -d only; it's fully merged. Never -D on your own initiative.
```

`--force` on `worktree remove` is safe ONLY because the worktree holds just committed+merged
commits plus git-ignored scratch; never force-remove a worktree with unique uncommitted work.
