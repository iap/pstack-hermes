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
NON_RUNNING_FLAGS = re.compile(
    r"(?:^|\s)(?:--collect-only|--co|--help|-h|--version|-V)(?:\s|$)"
)


def load_tool_calls(db_path: Path, session_id: str | None = None) -> list[dict] | None:
    """Ordered tool calls from one session (default: newest), or None when unreadable.

    Each item: {"name": str, "args": dict, "exit_code": int | None}.
    ``exit_code`` is filled from the matching terminal result when present.
    """
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        if session_id is None:
            row = conn.execute(
                "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            session_id = row[0] if row else None
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
    for role, _content, tool_calls, _tool_name, _call_id in rows:
        if role != "assistant" or not tool_calls:
            continue
        try:
            parsed = json.loads(tool_calls)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, list):
            continue
        for item in parsed:
            fn = (item or {}).get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (TypeError, ValueError):
                args = {}
            call_id = item.get("call_id") or item.get("id")
            calls.append(
                {
                    "name": name,
                    "args": args if isinstance(args, dict) else {},
                    "exit_code": exits.get(call_id),
                }
            )
    return calls


def _verification_segment(command: str) -> str | None:
    """The last shell segment when it is a test run, else None.

    Only the last segment counts because that is the one whose exit status the
    session records. `pytest -q || true` and `pytest | tee out` end in another
    command, so a zero status says nothing about pytest — those must not verify
    a claim.
    """
    segments = [seg.strip() for seg in re.split(r"&&|\|\||[;|\n]", command or "") if seg.strip()]
    if not segments:
        return None
    last = segments[-1]
    if not TEST_COMMAND_PATTERN.search(last):
        return None
    # Collection-only, help and version invocations exit 0 without running a
    # test; accepting them would let "all tests pass" claim a run that never ran.
    if NON_RUNNING_FLAGS.search(last):
        return None
    return last


def _is_test_command(command: str) -> bool:
    return _verification_segment(command) is not None


def _masked_test(command: str) -> bool:
    """A test-looking segment whose status the shell does not report.

    `pytest -q || true` and `pytest | tee out` contain a test but end in another
    command. Neither proves anything, and neither is proof of failure either.
    """
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
    for call in calls:
        if call["name"] != "terminal":
            continue
        segment = _verification_segment(str(call["args"].get("command") or ""))
        if segment:
            test_calls.append((call, segment))
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


def _no_banned_tool(calls: list[dict] | None) -> dict:
    gate = "no_banned_tool"
    if calls is None:
        return {"gate": gate, "status": "unavailable", "detail": "no readable session record"}
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


def grade(expectations: dict, calls: list[dict], final_text: str, project: Path) -> list[dict]:
    """Grade the declared gates. Unknown gate names are a harness error."""
    results = []
    for gate in expectations.get("gates", []):
        if gate == "read_before_write":
            results.append(_read_before_write(calls, project))
        elif gate == "verify_before_claim":
            results.append(_verify_before_claim(calls, final_text))
        elif gate == "no_banned_tool":
            results.append(_no_banned_tool(calls))
        else:
            results.append(
                {"gate": gate, "status": "unavailable", "detail": "unknown gate name"}
            )
    return results
