# Portable defaults

This file owns how agents treat environment-dependent defaults in hand-written
source. `AGENTS.md` product policy remains the owner of contractual values;
`CONTRIBUTING.md` owns this repository's `master` PR target.

## Decision rule

A literal value is allowed only when it is a product-policy or repository-contract
entry: `master` for this repository's CI and release gates, Graphite (`gt`) default
with GitHub (`gh`) fallback, LF-only encoding, the `pstack` identity, the hermes
vocabulary, and the model panel in `config/models.json`. Everything else is
environment-dependent and must be resolved at runtime.

## Shipped surfaces

The release ZIP ships `skills/`, `scripts/`, `config/`, `assets/`, `README.md`,
`LICENSE`, `plugin.json` and lockfiles. A branch, path, tool or model those files
assume belongs to the user's environment, not to this repository.

- Default branch: resolve the trunk remote first, then use `<trunk-remote>/HEAD`
  (`git symbolic-ref --short refs/remotes/<trunk-remote>/HEAD`). When that ref is
  absent, query the forge default with `gh repo view --json defaultBranchRef`,
  fetch it, and use `<trunk-remote>/<branch>` for every read. Re-resolve and fetch
  at every audit tick so reads use the current default. Never assume a branch or
  remote name, and never use bare `HEAD`, `refs/heads/...` or the current checkout
  as trunk.
- Remote: derive the trunk remote from the main worktree's configured upstream
  (`git -C <main-worktree> config --get branch.<branch>.remote`), then the first
  configured remote, then `origin`. Remote names may contain a slash; do not split
  an upstream ref at its first slash. For per-branch pushed/ahead checks, use that
  branch's own upstream remote, which may differ from the trunk remote in a fork.
- Paths: use `HERMES_HOME`, `hermes profile show`, `TMPDIR` or `mktemp`. A
  `~/.cursor/...` path is only a compatibility probe that skips gracefully; never
  use a machine-local absolute path as a live default.
- Tools: guard optional binaries with `command -v`, keep the portable GNU/BSD
  `stat`/`date` shims, and provide a documented fallback instead of a hard
  requirement.
- Models: use panel entries from `config/models.json` or provider-qualified
  `vendor/model[:variant]` slugs. A callable model in an example is an example,
  not a universal default.

## Fail closed

If discovery fails, report an unknown or incomplete result. Never substitute the
current checkout branch for the trunk: that can compare a branch with itself and
call it merged. `scripts/worktree-audit.sh` is the reference pattern (`merged=unknown`
plus a stderr warning).

## Tests and evaluation

Every dynamic resolver needs tests for a `master` default, a `main` default, and a
missing or undiscoverable default. See `tools/tests/test_worktree_audit.py` and
`tools/tests/test_check_plan.py`. The narrow gate in `tools/check_docs.py` rejects
literal trunk refs in shipped playbooks. Do not add a blanket model or path regex:
it would flag intentional examples in `docs/EVALS.md` and other docs.
