# Issue #49: Local-only stack forge design

## Problem

Current `orch` stack providers require external dependencies:
- `github` — needs `gh` CLI + GitHub API
- `gitlab` — stubbed, not implemented
- `graphite` — needs proprietary `gt` CLI

Users without GitHub/GitLab access (air-gapped, offline, no auth) have no stack-management path.

## Goal

A **local-only forge** that tracks PR/MR topology using git-native primitives only — no external API, no Graphite, no GitLab.

## Data Model (forge-agnostic)

```json
{
  "branches": [
    {
      "name": "string",
      "sha": "string",
      "parents": ["string"],   // branch SHAs this branch is based on
      "children": ["string"]   // branch SHAs built on top of this one
    }
  ],
  "head": "string"             // current branch name
}
```

A "stack" = chain of branches where each branch's parent is the merge-base of the branch below it.

## Git-native inference algorithm

### Enumeration
```bash
git for-each-ref refs/heads/ --format='%(refname:short) %(objectname:short)'
```

### Relationship inference
For each pair of branches (A, B):
```bash
git merge-base --is-ancestor A B   // Is A an ancestor of B?
git merge-base A B                 // Find the merge-base commit
```

### Topology construction
1. Enumerate all branches + SHAs
2. For each branch B, find branches A where `merge-base(A,B) == A` → A is a parent of B
3. Build adjacency list: branch → {parents, children}
4. Head = `git symbolic-ref --short HEAD`

## Edge cases

| Case | Handling |
|------|----------|
| Merged branch | Child no longer tracked; mark as closed/merged |
| Rebased branch | SHA changed; re-detect topology on next run |
| Divergent history | Multiple merge-bases; pick closest common ancestor |
| Multi-remote | Consider only local refs by default; optional remote scanning |
| Orphan branch | No parents; root of stack |
| Empty repo | No branches; empty stack |

## Phase 1 deliverables

1. ✅ Data model definition (above)
2. ✅ Git-graph inference algorithm (above)
3. Edge case documentation (above)
4. Follow-up issue opened for Phase 2 implementation

## Phase 2 implementation (separate issue)

1. Implement `localFrontier(repo, pin?)` in `store.ts`
2. Wire into `resolveFrontier()` for `provider === "local"`
3. Update `orch.ts` CLI description
4. Add tests in `orch.test.ts`
5. Rebuild `pstack/` from converter

## Verification

- `orch frontier set --provider local` discovers stack from local git state
- `orch status` renders correctly
- `bun run test` passes
- `uv run --frozen tools/validate.py` exits 0
