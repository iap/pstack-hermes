# Patches to the hermes CLI itself

> [!WARNING]
> **Archived (2026-11-17).** The upstream PRs that proposed these patches to
> `NousResearch/hermes-agent` were opened and later **closed unmerged**
> (2026-09-10). The gaps they address are **still present** in Hermes v0.22.5
> (verified 2026-11-17), but the project no longer carries them as live fixes:
> they live in [`patches/archive/`](../patches/archive/README.md) as a record.
> None is required for the package to load, validate, or install.

Agents routing harness gaps: prefer a fix or issue on
`NousResearch/hermes-agent`. Do not treat these patches as a required
install step for pstack.

These are *not* part of the pstack package. They are proposed changes to the
hermes agent source tree (`%LOCALAPPDATA%\hermes\hermes-agent`),
kept here because the portable-plugin work surfaced the gaps. Apply manually
with `git apply <patch>` inside the hermes clone; none of them are required
for the pstack package to load and validate.

## patches/archive/hermes-fork-portable-diagnostics.patch

`hermes_cli/agent_plugins.py` — when a manifest carries Cursor-only top-level
fields (`agents`, `commands`, `hooks`, `automations`, `rules`), the loader's
generic "ignored unknown field" diagnostic is replaced with a loud,
actionable one: the component will NOT load, because hermes discovers only
`skills/` and `mcp.json` from portable agent-plugins-v1 packages. Silent
success is the dangerous failure mode for Cursor ports.

Status: independent of the other two patches; safe to apply at any time.

## patches/archive/hermes-fork-oneshot-cwd.patch (v1) vs .../hermes-fork-oneshot-cwd-v2.patch

Two mechanisms for the same observed failure: in `hermes -z` (oneshot) mode,
"create a file in the current directory" resolved to the wrong location
because nothing told the model (or the tool session) where it was running
from — oneshot is the only surface that never seeds a session cwd.

- **v1** (`record_session_cwd` seed): tooling-level fix. Seeds the task
  session cwd from the invoking process directory via
  `tools/terminal_tool.record_session_cwd`, mirroring what the gateway/TUI
  do via workspace overrides. Coupled to that internal API existing with
  this exact name and behavior.
- **v2** (system-prompt note): prompt-level fix. Appends the resolved
  `os.getcwd()` and an instruction to resolve relative paths against it to
  the ephemeral system prompt. No coupling to hermes internals beyond
  `ephemeral_system_prompt`, which already exists in the call.

Status: **v2 supersedes v1 in intent** (written 6 minutes later, strictly
less coupled). Both hunks touch `oneshot.py` but at different anchors, so
they can coexist; until hermes-side runtime testing picks a winner, v1 is
kept for reference. Prefer v2 if applying only one.

## Verification status

There are **no live patches** under `patches/` any more; every `.patch` file is
in `patches/archive/` with the evidence table in its README. The weekly
`patch-health` workflow still runs: it clones `NousResearch/hermes-agent` at a
target ref (default `main` and the newest release tag; dispatchable with another
ref) and applies `git apply --check` to every live patch. With zero live patches
it records the archived count and passes; if both the live and archive sets are
empty it fails, so an accidental deletion cannot look like a clean state.

Consequence of the archived oneshot patch: `hermes -z` does not seed a working
directory. Pass absolute paths in oneshot prompts and eval cases
(`tools/evals/README.md`).
