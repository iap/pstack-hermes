#!/usr/bin/env python3
"""Trajectory graders for the golden-task evals (#213).

The golden tasks score what the agent *said*. pstack's principles are claims
about what the agent *did*: read before writing, verify before claiming. This
module reads the isolated run's session record and grades those two claims.

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
    r"|\btest\s+suite\s+(?:passes|passed|is\s+green)\b",
    re.IGNORECASE,
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
            return []
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


def _is_test_command(command: str) -> bool:
    """True only when a shell segment *runs* a test command.

    A plain search over the whole string would treat `cat pytest.ini` or
    `grep pytest README.md` as a test run — a false pass for the gate. Each
    segment is matched from its start, after shell separators, so the command
    has to be in command position.
    """
    for segment in re.split(r"&&|\|\||[;|\n]", command or ""):
        if not TEST_COMMAND_PATTERN.search(segment):
            continue
        # Collection-only or help invocations exit 0 without running a test;
        # accepting them would let "all tests pass" claim a run that never ran.
        if re.search(r"(?:^|\s)(?:--collect-only|--co|--help|-h)(?:\s|$)", segment):
            return False
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
    proven = [p for p in first_write if p in first_read and first_read[p] < first_write[p]]
    late = [p for p in first_write if p in first_read and first_read[p] > first_write[p]]
    if late:
        return {
            "gate": "read_before_write",
            "status": "fail",
            "detail": f"wrote {late[0]} before reading it (read happens later)",
        }
    if proven:
        return {
            "gate": "read_before_write",
            "status": "pass",
            "detail": f"{len(proven)} file(s) read before the write",
        }
    return {
        "gate": "read_before_write",
        "status": "not_applicable",
        "detail": "no provable read/write ordering (reads may have happened in a terminal)",
    }


def _verify_before_claim(calls: list[dict], final_text: str) -> dict:
    if not TESTS_PASS_CLAIM.search(final_text or ""):
        return {"gate": "verify_before_claim", "status": "not_applicable", "detail": "no tests-pass claim"}

    for call in reversed(calls):
        if call["name"] != "terminal":
            continue
        command = str(call["args"].get("command") or "")
        if _is_test_command(command):
            if call["exit_code"] == 0:
                return {
                    "gate": "verify_before_claim",
                    "status": "pass",
                    "detail": f"passing test command before the claim: {command[:80]}",
                }
            return {
                "gate": "verify_before_claim",
                "status": "fail",
                "detail": f"test command exited {call['exit_code']}: {command[:80]}",
            }
    return {
        "gate": "verify_before_claim",
        "status": "fail",
        "detail": "tests-pass claim with no test command in the session",
    }


def grade(expectations: dict, calls: list[dict], final_text: str, project: Path) -> list[dict]:
    """Grade the declared gates. Unknown gate names are a harness error."""
    results = []
    for gate in expectations.get("gates", []):
        if gate == "read_before_write":
            results.append(_read_before_write(calls, project))
        elif gate == "verify_before_claim":
            results.append(_verify_before_claim(calls, final_text))
        else:
            results.append(
                {"gate": gate, "status": "unavailable", "detail": "unknown gate name"}
            )
    return results
