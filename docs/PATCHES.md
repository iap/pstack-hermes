# Patches to the hermes CLI itself

These are *not* part of the pstack package. They are proposed changes to the
hermes agent source tree (`%LOCALAPPDATA%\hermes\hermes-agent`),
kept here because the portable-plugin work surfaced the gaps. Apply manually
with `git apply <patch>` inside the hermes clone; none of them are required
for the pstack package to load and validate.

## patches/hermes-fork-portable-diagnostics.patch

`hermes_cli/agent_plugins.py` — when a manifest carries Cursor-only top-level
fields (`agents`, `commands`, `hooks`, `automations`, `rules`), the loader's
generic "ignored unknown field" diagnostic is replaced with a loud,
actionable one: the component will NOT load, because hermes discovers only
`skills/` and `mcp.json` from portable agent-plugins-v1 packages. Silent
success is the dangerous failure mode for Cursor ports.

Status: independent of the other two patches; safe to apply at any time.

## patches/hermes-fork-oneshot-cwd.patch (v1) vs patches/hermes-fork-oneshot-cwd-v2.patch

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
