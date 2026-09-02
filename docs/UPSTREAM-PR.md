# Upstream PR draft — NousResearch/hermes-agent

> Prepared 2026-08-31. Branch: `fix/portable-plugin-hardening`
> (contains 4 commits from `iap/hermes-agent` main). Open the PR from that
> branch to `NousResearch/hermes-agent:main` after pushing.
> Each change is evidence-backed from a real Cursor-plugin port (pstack →
> hermes) documented in this repository.

## Title

fix: portable-plugin diagnostics, one-shot cwd honoring, and plugin-root scanner exemption

## Body

Four related fixes found while porting a real Cursor agent-plugins-v1 plugin
(44 skills) to hermes on Windows. Every change is behavior-verified against
the running agent.

### 1. Loud diagnostics for Cursor-only components in portable manifests

`hermes_cli/agent_plugins.py` `_validate_manifest`: when a portable manifest
declares Cursor-only component fields (`agents`, `commands`, `hooks`,
`automations`, `rules`), emit an actionable diagnostic ("Cursor-only component
'agents' will NOT load: hermes discovers skills/ and mcp.json only") instead
of the generic ignored-field warning. Prevents the silent-success failure mode
where a Cursor plugin loads with its agents/commands/hooks doing nothing.

Verified: synthetic manifest with the three fields emits exactly 3 loud
diagnostics; other unknown fields keep the generic warning.

### 2. One-shot (-z) sessions seed the task-session cwd

`hermes_cli/oneshot.py`: one-shot sessions never registered a workspace cwd
override, so file/terminal tools resolved "current directory" to the
configured default workspace (the last-used project) instead of where the
user ran `hermes -z`. Seed `record_session_cwd(session_id, os.getcwd())`
after agent construction — the seed source `tools/terminal_tool.py`
`get_session_cwd` explicitly documents the process cwd as an intended seed.

Verified: a one-shot creating "a file named cwd-probe.txt in the current
directory" now writes it to the invoking directory (previously: the home
root).

### 3. One-shot ephemeral system prompt surfaces the working directory

Companion to #2: the model itself resolved "current directory" to the home
root by inventing an absolute path, because nothing told it the cwd. The
one-shot ephemeral system prompt now ends with a "Working directory" section
(`Current working directory for this session: <cwd>` + relative-path
resolution guidance).

Verified: same probe now lands in the invoking directory with the model
quoting the correct absolute path.

### 4. skills_guard: exempt agent-plugin roots from the per-skill file-count rule

`tools/skills_guard.py` `_check_structure`: the 50-file `too_many_files`
medium finding applies per-skill, but the plugin install path scans the whole
package as one unit — making every multi-skill portable plugin (44 skills in
our case) un-installable via the CLI without `--force`. A directory
containing `plugin.json` is an agent-plugin root and now skips the
file-count finding; the per-skill size, executable, and content rules still
apply.

Verified: the 44-skill package scans as safe verdict with the
`too_many_files` finding gone; `should_allow_install` returns True.

## Commits

- 212b862137 fix(plugins): loud diagnostics for Cursor-only components in portable manifests
- ac74e42560 fix(oneshot): seed task-session cwd from the invoking process directory
- 0953d35c91 fix(oneshot): surface the working directory in the ephemeral system prompt
- ab6d3b9700 fix(skills_guard): exempt agent-plugin roots from the per-skill file-count rule

## Testing

- `python -m py_compile` on every touched file
- Behavioral verification per change (synthetic manifests + live one-shots +
  real scanner runs), all green on Windows (git install, venv 3.11)
