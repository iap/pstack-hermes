# Runbook — upstream drift (re-pinning)

> [!IMPORTANT]
> Upstream (`cursor/plugins` → `pstack`) is **pinned**. The port is faithful to
> that SHA, not to upstream `HEAD`. Drift is expected and handled here; it is
> never fixed by hand-editing `pstack/` (that tree is generated and would be
> wiped on the next build).

## How drift surfaces

Any of these means upstream moved past the pin:

- **The build fails loudly** — `CONVERT ERROR: anchor audit: N transform
  anchor(s) never matched`. This is the primary detector: an anchor written
  against the pinned text no longer matches, so the transform would silently
  do nothing. The build refuses to produce a package.
- **The weekly upstream-drift workflow** opens a tracking issue when upstream
  `pstack/` changes past the pin.
- **The "Verify pinned SHA" step** in `ci.yml` fails when the checked-out upstream
  clone's SHA no longer equals `UPSTREAM_PIN`. It compares the checkout, not
  `.build-provenance.txt` — provenance records that same SHA by construction.

## Procedure

1. **Fetch and diff.** Update the local upstream clone, then diff the new SHA
   against the pin — focus on `skills/`, `agents/`, and the Cursor manifest:
   `git -C <pstack-clone> log --oneline <pin>..HEAD -- pstack/`
2. **Decide the new pin.** Read the upstream commits. If they touch text any
   map anchors on, they are in scope; unrelated files may be ignored.
3. **Update the maps, not the package.** For each dead anchor:
   - re-anchor to the new upstream text and keep the intended replacement, or
   - prune the entry if upstream already made the change, and record why in the
     commit body.
   Edit `tools/convert.py` only.
4. **Rebuild and let the gates run.**
   `uv run --frozen tools/convert.py --source <pstack-clone> --out pstack`
   must exit 0 with a clean anchor audit.
5. **Validate.** `uv run --frozen tools/validate.py --package pstack` —
   static + gold manifest + gold load must pass.
6. **Re-check the package docs.** If the change touches what the differences
   contract or Known limitations describe, update the README template in
   `convert.py` and rebuild.
7. **Update `UPSTREAM_PIN` everywhere it is declared.** It is repeated
   independently in **three** workflows — `ci.yml`, `release.yml`, and
   `upstream-drift-watch.yml` — and all three must move together. The converter
   holds no pin: it records the SHA of the clone it is pointed at, so
   `source_commit` in `.build-provenance.txt` follows the checkout.
8. **PR** with `rebuilt from pin <sha>` in the body (the PR template carries the
   fields) and a one-line note per map change.

## Do not

- **Do not hand-edit `pstack/`.** It is generated; edits vanish on rebuild.
- **Do not delete a dead anchor without checking its intent.** "Never matched"
  can mean *upstream reworded* (re-anchor) or *upstream already fixed it*
  (prune) — decide per entry and say which in the commit body.
- **Do not silence the audit.** There is no force flag; the audit exists so a
  silently no-op transform cannot ship.
- **Do not fold unrelated changes into a re-pin.** Keep map updates and pin
  bumps reviewable on their own.

## Rollback

A bad rebuild only affects the branch: the build is atomic (`pstack.tmp-build`
swap with rollback on failure), and the previous `pstack/` stays intact until a
successful swap. To revert a landed pin bump, revert the PR — the package is
regenerated from the previous pin.
