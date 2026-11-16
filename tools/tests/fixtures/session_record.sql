-- Sanitized session-record fixture.
--
-- The CREATE TABLE statements below are copied from a real Hermes v0.22.5
-- `$HERMES_HOME/state.db` (indexes, triggers and FTS tables omitted: the
-- parser reads only these columns). Rows are synthetic: relative paths and
-- fake commands. The point is to exercise the parser against the real column
-- layout, so a schema change that breaks it fails a test instead of silently
-- degrading the eval.
--
-- Loading: sqlite3 <db> < tools/tests/fixtures/session_record.sql

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    user_id TEXT,
    model TEXT,
    model_config TEXT,
    system_prompt TEXT,
    parent_session_id TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    billing_provider TEXT,
    billing_base_url TEXT,
    billing_mode TEXT,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    cost_status TEXT,
    cost_source TEXT,
    pricing_version TEXT,
    title TEXT,
    api_call_count INTEGER DEFAULT 0,
    handoff_state TEXT,
    handoff_platform TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,
    tool_name TEXT,
    timestamp REAL NOT NULL,
    token_count INTEGER,
    finish_reason TEXT,
    reasoning TEXT,
    reasoning_content TEXT,
    reasoning_details TEXT,
    codex_reasoning_items TEXT,
    codex_message_items TEXT,
    platform_message_id TEXT,
    observed INTEGER DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    compacted INTEGER NOT NULL DEFAULT 0,
    compaction_epoch INTEGER DEFAULT 0,
    effect_disposition TEXT,
    api_content TEXT,
    display_kind TEXT,
    display_metadata TEXT,
    _compressed_summary INTEGER NOT NULL DEFAULT 0,
    display_identity BLOB,
    display_order INTEGER,
    message_uid TEXT,
    absorbed_message_uids TEXT,
    tool_call_uids TEXT,
    tool_call_uid TEXT
);

INSERT INTO sessions (id, source, started_at, model) VALUES ('fixture-session', 'cli', 1.0, 'fixture-model');

INSERT INTO messages (session_id, role, content, timestamp) VALUES
    ('fixture-session', 'user', 'Fix the failing test in calc.py.', 1.0);

INSERT INTO messages (session_id, role, tool_calls, timestamp) VALUES
    ('fixture-session', 'assistant',
     '[{"id": "c1", "call_id": "c1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"calc.py\"}"}}]',
     2.0);

INSERT INTO messages (session_id, role, tool_calls, timestamp) VALUES
    ('fixture-session', 'assistant',
     '[{"id": "c2", "call_id": "c2", "type": "function", "function": {"name": "patch", "arguments": "{\"path\": \"calc.py\", \"old_string\": \"a - b\", \"new_string\": \"a + b\"}"}}]',
     3.0);

INSERT INTO messages (session_id, role, tool_calls, timestamp) VALUES
    ('fixture-session', 'assistant',
     '[{"id": "c3", "call_id": "c3", "type": "function", "function": {"name": "terminal", "arguments": "{\"command\": \"pytest -q\"}"}}]',
     4.0);

INSERT INTO messages (session_id, role, content, tool_name, tool_call_id, timestamp) VALUES
    ('fixture-session', 'tool', '{"output": "1 passed", "exit_code": 0}', 'terminal', 'c3', 5.0);

INSERT INTO messages (session_id, role, content, timestamp) VALUES
    ('fixture-session', 'assistant', 'All tests pass — 1 passed.', 6.0);
