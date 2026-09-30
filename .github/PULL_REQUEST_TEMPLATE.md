<!--
Keep this short: a template nobody finishes is worse than none.
Every checkbox below is something CI or tools/pr_checklist.py can actually
verify. Boxes that cannot be verified were deleted, not softened.
Instructions live in HTML comments and never render in the PR form.
Full gate list mirrors the CONTRIBUTING "Pull requests" section.
Attribution is standing policy in CONTRIBUTING.md - no per-PR checkbox.
The ```yaml provenance``` block is machine-read by tools/pr_checklist.py.
-->
# Pull request

## What changed
<!-- one or two lines: the change, not a narrative -->

## Affected surface
- [ ] tooling (`tools/`, CI, docs)
- [ ] generated package (`pstack/`) — **requires a rebuild from the current pin**

## Provenance — required if `pstack/` changed
<!-- tools/pr_checklist.py compares source_commit below to the tree's
     .build-provenance.txt. Copy the exact values from your rebuilt package.
     converter is optional; source_commit is the one that must be right. -->
```yaml
source_commit: <40-char SHA from pstack/.build-provenance.txt>
converter: convert.py (sha256[:16]=<first 16 of your convert.py hash>)
```

## Verification
<!-- Paste the command output. A checked box with no output below it is flagged
     by tools/pr_checklist.py. Put each command's output under its own box. -->
- [ ] `uv run --frozen ruff check tools`
      ```
      <output>
      ```
- [ ] `uv run --frozen pytest -q`
      ```
      <output>
      ```
- [ ] package rebuilt from the pin and `git status` shows the intended `pstack/` diff
      ```
      <git status --porcelain output, or "n/a - no pstack/ change">
      ```
- [ ] poteto-mode scripts green, if touched (`bun run test` + `bun run typecheck`)
      ```
      <output, or "n/a">
      ```

## Notes for reviewers
<!-- Anything a reviewer should weigh: trade-offs, skipped boxes and why,
     screenshots, follow-ups. Optional. -->
