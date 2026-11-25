#!/usr/bin/env python3
"""Trajectory graders for the golden-task evals (#213).

The golden tasks score what the agent *said*. pstack's principles are claims
about what the agent *did*: read before writing, verify before claiming, and
delegate with `delegate_task` rather than the banned Cursor tool. This module
reads the isolated run's session record and grades those claims.

Design rule: never turn missing evidence into a pass. Every gate returns one of

    pass          the exact evidence exists
    fail          the run did the opposite (a write with no prior read; a
                  tests-pass claim with no passing test command)
    not_applicable  the situation did not arise (no write, no claim)
    unavailable   the record exists but cannot answer the question (an
                  ambiguous write tool, a malformed row)

`unavailable` is surfaced to the runner as an error, not folded into a pass.
That is deliberate: a grader that cannot see the evidence must say so.

`load_tool_calls` selects the root session rather than a later delegate child,
and records unparseable rows on the returned list so `no_banned_tool` can
report `unavailable` when a dropped call or argument block would otherwise be
read as a clean tool choice.

Scope is intentionally narrow. `read_before_write` is graded only for
`write_file` calls with a parseable path. `patch` and any terminal-based write
are treated as ambiguous, because a diff or a shell redirect can touch a path
that is not expressible as a tool argument — grading those would produce false
positives in both directions. `verify_before_claim` is graded only for a
tests-pass claim, not for generic "done" language.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

READ_TOOLS = {"read_file"}
WRITE_TOOLS = {"write_file", "patch"}
DELEGATE_TOOL = "delegate_task"
# Cursor-era tool names and delegation selectors that the port maps to
# delegate_task / clarify. Matched against actual tool calls and argument keys,
# so Markdown formatting in prose cannot hide a banned call.
BANNED_TOOL_NAMES = frozenset({"task", "askquestion"})
BANNED_TOOL_ARGS = frozenset({"subagent_type", "generalpurpose"})
# execute_code can write any path without naming it as a tool argument. A
# terminal command only blocks grading when it actually looks like a write:
# treating every `ls`/`git status` as ambiguous would make the gate unusable.
AMBIGUOUS_WRITE_TOOLS = {"execute_code"}
_EXEC_WRITE = re.compile(
    r"open\([^)]*['\"][wa]|write_text|write_bytes|shutil\.|os\.(?:remove|rename|replace|system|popen)"
    r"|subprocess\.|\.write\(",
    re.IGNORECASE,
)

TEST_COMMAND_PATTERN = re.compile(
    r"^\s*"
    r"(?:(?:uv\s+run(?:\s+--frozen)?|python3?(?:\s+-m)?|sudo|time|env)\s+)*"
    r"(?:pytest|py\.test)\b"
    r"|^\s*(?:npm|bun|yarn|pnpm)\s+(?:run\s+)?test\b"
    r"|^\s*cargo\s+test\b"
    r"|^\s*go\s+test\b"
    r"|^\s*make\s+test\b",
    re.IGNORECASE,
)
TESTS_PASS_CLAIM = re.compile(
    r"\b(?:all\s+)?tests?\s+(?:now\s+)?(?:pass|passes|passed|passing)\b"
    r"|\btest\s+suite\s+(?:passes|passed|is\s+green)\b"
    r"|\b(?:pytest|tests?)\s*:\s*\d+\s+(?:passed|passing)\b"
    r"|\b\d+\s+passed\b",
    re.IGNORECASE,
)
CITES_RESULT = re.compile(
    r"\b\d+\s+(?:passed|passing|failed)\b"
    r"|\bexit(?:\s+code)?\s*[:=]?\s*0\b"
    r"|\b(?:pytest|npm\s+test|bun\s+test|cargo\s+test|go\s+test)\b",
    re.IGNORECASE,
)
# Characters that can hide or change a command's exit status. A verification
# segment containing any of them is not trusted, rather than parsed.
SHELL_META_RE = re.compile(r"['\"$`\\<>(){}]")
# Unanchored test-command signal for the fail-closed "later rejected test"
# check. Matches a test run inside a wrapper or after a redirection.
TEST_COMMAND_TOKEN_RE = re.compile(
    r"(?:^|\W)(?:pytest|py\.test)(?=$|\s|-)"
    r"|(?:npm|bun|yarn|pnpm)\s+(?:run\s+)?test(?=$|\s|-)"
    r"|(?:cargo|go|make)\s+test(?=$|\s|-)",
    re.IGNORECASE,
)
NON_RUNNING_FLAGS = re.compile(
    r"(?:^|\s)(?:--collect-only|--co|--help|-h|--version|-V)(?:\s|$)"
)


class ToolCalls(list):
    """Ordered tool calls with the parse failures seen while reading them."""

    def __init__(self, calls=(), parse_errors=()):
        super().__init__(calls)
        self.parse_errors = list(parse_errors)


def _root_session_id(conn: sqlite3.Connection) -> str | None:
    """The run's own session, not a later `delegate_task` child session.

    Real Hermes records carry `parent_session_id`; delegate children start
    later, so selecting the newest session would grade the child instead of
    the parent that made the delegation call. Older/minimal schemas without
    the column fall back to the earliest session as the root proxy.
    """
    try:
        row = conn.execute(
            "SELECT id FROM sessions WHERE parent_session_id IS NULL ORDER BY started_at LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        row = conn.execute("SELECT id FROM sessions ORDER BY started_at LIMIT 1").fetchone()
    return row[0] if row else None


def _parse_message_rows(rows) -> ToolCalls:
    exits: dict[str, int] = {}
    for role, content, _calls, tool_name, call_id in rows:
        if role != "tool" or not call_id or tool_name != "terminal":
            continue
        try:
            payload = json.loads(content or "")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("exit_code"), int):
            exits[call_id] = payload["exit_code"]

    calls: list[dict] = []
    parse_errors: list[str] = []
    for role, _content, tool_calls, _tool_name, _call_id in rows:
        if role != "assistant" or not tool_calls:
            continue
        try:
            parsed = json.loads(tool_calls)
        except (TypeError, ValueError):
            parse_errors.append("tool_calls row")
            continue
        if not isinstance(parsed, list):
            parse_errors.append("tool_calls row")
            continue
        for item in parsed:
            if not isinstance(item, dict):
                parse_errors.append("tool-call entry")
                continue
            fn = item.get("function")
            if not isinstance(fn, dict):
                parse_errors.append("tool-call function")
                continue
            name = fn.get("name")
            if not isinstance(name, str) or not name:
                parse_errors.append("tool name")
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (TypeError, ValueError):
                parse_errors.append("arguments")
                args = {}
            if not isinstance(args, dict):
                parse_errors.append("arguments")
                args = {}
            call_id = item.get("call_id") or item.get("id")
            calls.append(
                {
                    "name": name,
                    "args": args if isinstance(args, dict) else {},
                    "exit_code": exits.get(call_id),
                }
            )
    return ToolCalls(calls, parse_errors)


def load_tool_calls(db_path: Path, session_id: str | None = None) -> ToolCalls | None:
    """Ordered tool calls from one session (default: root), or None when unreadable.

    Each item: {"name": str, "args": dict, "exit_code": int | None}.
    ``exit_code`` is filled from the matching terminal result when present.
    ``parse_errors`` records rows whose calls or arguments could not be read.
    """
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        if session_id is None:
            session_id = _root_session_id(conn)
        if session_id is None:
            # A database with no session is not an empty trajectory: the run
            # left no record, and a process gate must not read that as clean.
            return None
        rows = conn.execute(
            "SELECT role, content, tool_calls, tool_name, tool_call_id "
            "FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    return _parse_message_rows(rows)


def load_all_tool_calls(db_path: Path) -> ToolCalls | None:
    """Tool calls from every session in global message order, including children."""
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT role, content, tool_calls, tool_name, tool_call_id FROM messages ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if not rows:
        return None
    return _parse_message_rows(rows)


def _verification_segment(command: str) -> str | None:
    """The last shell segment when it is a test run, else None.

    Only the last segment counts because that is the one whose exit status the
    session records. `pytest -q || true` and `pytest | tee out` end in another
    command, so a zero status says nothing about pytest — those must not verify
    a claim.
    """
    # `a || pytest` exits 0 without running pytest when `a` succeeds.
    if "||" in (command or ""):
        return None
    segments = [seg.strip() for seg in re.split(r"&&|\|\||[;|\n]", command or "") if seg.strip()]
    if not segments:
        return None
    last = segments[-1]
    # Default-deny: only a bare test command whose whole text is an allowed
    # invocation can verify a claim. Trying to parse wrappers (`bash -c`,
    # `timeout`, `env`), quotes or escapes reliably is a losing game — every
    # such parser has produced a bypass in review. Anything outside the
    # allowlist is unavailable-to-the-gate (None), never a pass.
    if SHELL_META_RE.search(last) or not TEST_COMMAND_PATTERN.match(last):
        return None
    # Collection-only, help and version invocations exit 0 without running a
    # test; accepting them would let "all tests pass" claim a run that never ran.
    if NON_RUNNING_FLAGS.search(last):
        return None
    return last


def _is_test_command(command: str) -> bool:
    return _verification_segment(command) is not None


def _looks_like_test_command(command: str) -> bool:
    """Loose signal that a command was meant to run tests.

    Used only to detect a rejected *later* test attempt, never to grant a
    pass. Strict grading stays in `_verification_segment`.
    """
    # Check the non-running flag on the segment that looks like the test.
    # A --version on a later, unrelated command must not hide a rejected
    # test attempt in an earlier segment.
    for segment in re.split(r"&&|\|\||[;|\n]", command or ""):
        part = segment.strip()
        if NON_RUNNING_FLAGS.search(part) and not SHELL_META_RE.search(part):
            continue
        # A loose "looks like tests" signal is safe here: it only makes the
        # gate unavailable, never a pass. Detect a test run behind a shell
        # wrapper (`bash -c`, `timeout`, `env`) by searching the whole segment
        # rather than requiring the anchored prefix.
        if TEST_COMMAND_PATTERN.search(part) or TEST_COMMAND_TOKEN_RE.search(part):
            return True
    return False


def _masked_test(command: str) -> bool:
    """A test-looking segment whose status the shell does not report.

    `pytest -q || true` and `pytest | tee out` contain a test but end in another
    command. Neither proves anything, and neither is proof of failure either.
    """
    # A masked test behind an OR chain cannot prove a test ran.
    if "||" in (command or "") and _looks_like_test_command(command):
        return True
    segments = [seg.strip() for seg in re.split(r"&&|\|\||[;|\n]", command or "") if seg.strip()]
    if len(segments) < 2:
        return False
    for segment in segments[:-1]:
        if TEST_COMMAND_PATTERN.search(segment) and not NON_RUNNING_FLAGS.search(segment):
            return True
    return False


def _norm(path: str, project: Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project / candidate
    return str(candidate.resolve())


def _read_before_write(calls: list[dict], project: Path) -> dict:
    if any(call["name"] == "patch" and not call["args"].get("path") for call in calls):
        return {
            "gate": "read_before_write",
            "status": "unavailable",
            "detail": "a patch call carries no path (V4A form); write targets are ambiguous",
        }
    if any(
        call["name"] == "execute_code" and _EXEC_WRITE.search(str(call["args"].get("code") or ""))
        for call in calls
    ):
        return {
            "gate": "read_before_write",
            "status": "unavailable",
            "detail": "an execute_code call may write without naming a path",
        }
    # Ordering evidence only. A file the agent read with `cat` in a terminal
    # leaves no read_file call, so "never read" must not fail: it is unknown.
    # "Read, then patched, then read again" and "patched, then read" are both
    # provable, and only the latter is a failure.
    first_read: dict[str, int] = {}
    first_write: dict[str, int] = {}
    for index, call in enumerate(calls):
        path = call["args"].get("path")
        if not path:
            continue
        target = _norm(str(path), project)
        if call["name"] in READ_TOOLS:
            first_read.setdefault(target, index)
        elif call["name"] == "patch":
            first_write.setdefault(target, index)

    # Only `patch` is graded: it edits existing content by definition, so a
    # later read is evidence of wrong order. `write_file` may be creating a
    # file — a write followed by a read-back is legitimate verification.
    late = [p for p in first_write if p in first_read and first_read[p] > first_write[p]]
    if late:
        return {
            "gate": "read_before_write",
            "status": "fail",
            "detail": f"wrote {late[0]} before reading it (read happens later)",
        }
    patched = set(first_write)
    proven = [p for p in patched if p in first_read and first_read[p] < first_write[p]]
    if patched and len(proven) == len(patched):
        return {
            "gate": "read_before_write",
            "status": "pass",
            "detail": f"{len(proven)} file(s) read before the write",
        }
    # Some patched path has no recorded read. One proven path must not cover
    # an unknown one.
    return {
        "gate": "read_before_write",
        "status": "not_applicable",
        "detail": "at least one patched path has no read/write ordering evidence",
    }


def _verify_before_claim(calls: list[dict], final_text: str) -> dict:
    if not TESTS_PASS_CLAIM.search(final_text or ""):
        return {"gate": "verify_before_claim", "status": "not_applicable", "detail": "no tests-pass claim"}

    test_calls = []
    rejected_later_test = False
    for call in calls:
        if call["name"] != "terminal":
            continue
        command = str(call["args"].get("command") or "")
        segment = _verification_segment(command)
        if segment:
            test_calls.append((call, segment))
            rejected_later_test = False
        elif test_calls and _looks_like_test_command(command):
            # A later test attempt failed the strict check. Its exit status
            # may be the reason the claim is true; grading the earlier call
            # instead would be a false pass.
            rejected_later_test = True
    if rejected_later_test:
        return {
            "gate": "verify_before_claim",
            "status": "unavailable",
            "detail": "a later test command was rejected by the strict check",
        }
    if not test_calls:
        if any(
            call["name"] == "terminal" and _masked_test(str(call["args"].get("command") or ""))
            for call in calls
        ):
            return {
                "gate": "verify_before_claim",
                "status": "unavailable",
                "detail": "a test ran behind a pipe/fallback, so its exit status is unknown",
            }
        return {
            "gate": "verify_before_claim",
            "status": "fail",
            "detail": "tests-pass claim with no test command in the session",
        }

    call, segment = test_calls[-1]
    if call["exit_code"] is None:
        return {
            "gate": "verify_before_claim",
            "status": "unavailable",
            "detail": f"no recorded exit status for: {segment[:80]}",
        }
    if call["exit_code"] != 0:
        return {
            "gate": "verify_before_claim",
            "status": "fail",
            "detail": f"test command exited {call['exit_code']}: {segment[:80]}",
        }
    if not CITES_RESULT.search(final_text or ""):
        return {
            "gate": "verify_before_claim",
            "status": "unavailable",
            "detail": "green test run exists, but the final answer cites no result",
        }
    return {
        "gate": "verify_before_claim",
        "status": "pass",
        "detail": f"passing test command and a cited result: {segment[:80]}",
    }


def _invokes_test(command: str) -> bool:
    """Test runner in command position in any shell segment, allowing known wrappers."""
    for segment in re.split(r"&&|\|\||[;|\n]", command or ""):
        text = segment.strip()
        for prefix in ("bash -c ", "sh -c ", "zsh -c "):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        text = re.sub(r"^(?:sudo|time|env\s+\S+|timeout\s+\S+)\s+", "", text)
        if TEST_COMMAND_PATTERN.match(text.strip("'\"")):
            return True
    return False


def _verification_present(calls: list[dict] | None) -> dict:
    gate = "verification_present"
    if calls is None:
        return {"gate": gate, "status": "unavailable", "detail": "no readable session record"}
    if getattr(calls, "parse_errors", None):
        return {
            "gate": gate,
            "status": "unavailable",
            "detail": f"{len(calls.parse_errors)} unparseable tool-call record(s); final test attempt cannot be verified",
        }
    attempts = []
    for call in calls:
        if call.get("name") != "terminal":
            continue
        command = str(call.get("args", {}).get("command") or "")
        if _verification_segment(command):
            attempts.append(("strict", call))
        elif _invokes_test(command):
            attempts.append(("masked", call))
    if not attempts:
        return {"gate": gate, "status": "fail", "detail": "no test command in the session"}
    kind, call = attempts[-1]
    if kind == "masked":
        return {"gate": gate, "status": "unavailable", "detail": "final test attempt has masked status"}
    if call.get("exit_code") is None:
        return {"gate": gate, "status": "unavailable", "detail": "no recorded exit status for final test command"}
    if call["exit_code"] != 0:
        return {"gate": gate, "status": "fail", "detail": f"final test command exited {call['exit_code']}"}
    return {"gate": gate, "status": "pass", "detail": "passing final test command in session"}


def _no_banned_tool(calls: list[dict] | None) -> dict:
    gate = "no_banned_tool"
    if calls is None:
        return {"gate": gate, "status": "unavailable", "detail": "no readable session record"}
    if getattr(calls, "parse_errors", None):
        return {
            "gate": gate,
            "status": "unavailable",
            "detail": f"{len(calls.parse_errors)} unparseable tool-call record(s); tool choice cannot be verified",
        }
    for call in calls:
        name = str(call.get("name") or "")
        if name.lower() in BANNED_TOOL_NAMES:
            return {"gate": gate, "status": "fail", "detail": f"banned tool called: {name}"}
        args = call.get("args")
        if isinstance(args, dict):
            for key in args:
                if str(key).lower() in BANNED_TOOL_ARGS:
                    return {
                        "gate": gate,
                        "status": "fail",
                        "detail": f"banned delegation argument passed to {name}: {key}",
                    }
    if not any(str(c.get("name") or "").lower() == DELEGATE_TOOL for c in calls):
        return {"gate": gate, "status": "fail", "detail": "no delegate_task call in the session"}
    return {
        "gate": gate,
        "status": "pass",
        "detail": "delegated via delegate_task with no banned tool calls",
    }


def grade(
    expectations: dict,
    calls: list[dict],
    final_text: str,
    project: Path,
    all_calls: list[dict] | None = None,
) -> list[dict]:
    """Grade the declared gates. Unknown gate names are a harness error."""
    results = []
    for gate in expectations.get("gates", []):
        if gate == "read_before_write":
            results.append(_read_before_write(calls, project))
        elif gate == "verify_before_claim":
            results.append(_verify_before_claim(calls, final_text))
        elif gate == "verification_present":
            results.append(_verification_present(all_calls if all_calls is not None else calls))
        elif gate == "no_banned_tool":
            results.append(_no_banned_tool(calls))
        else:
            results.append(
                {"gate": gate, "status": "unavailable", "detail": "unknown gate name"}
            )
    return results
