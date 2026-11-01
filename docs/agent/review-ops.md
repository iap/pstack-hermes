# Reviewer-bot threads

How to handle automated review findings (CodeRabbit, Qodo, and similar) without
weakening the port contract.

## Tooling

- **Inspect threads deeply.** Prefer `gh api graphql` to fetch PR review threads (thread ID, resolution state, outdated hunks, and replies) before deciding fix/dismiss/duplicate.
- **Reply to the correct thread.** Use the thread ID from GraphQL when replying (or the correct `pullRequestReviewThread` endpoint).
- **Fallback gracefully.** If GraphQL is blocked by auth/scopes, fall back to `gh pr view`/REST and note that limitation when replying or reporting checks.

## Process

1. **Inspect before changing.** Check each finding against the pre-change
   contract, current code, callers, tests, and the current review thread.
   Decide whether it is already fixed, duplicated, outdated, incorrect, or
   blocked.
2. **Valid finding.** Implement the compatible fix and run the relevant checks.
   If it conflicts with the contract or needs a product decision, explain the
   conflict and seek clarification — do **not** weaken a contract to satisfy a
   bot.
3. **Reply in the same thread with evidence.**
   - **If you change code:** state what changed, why, commit/code reference, and verification results (including honest `not run` + cause if blocked).
   - **If you do not change code (false positive, duplicate, already fixed, already resolved, or already discussed):** reply with **What** (file:line + a short quote of the finding), **Why** (specific reason tied to the contract/diff/outdated hunk), **Evidence** (commit SHA, prior comment/thread link, current code/diff, `validate.py`/tests, or a concrete summary of the discussion), and **Verification** if checks are relevant. Avoid generic phrases like "already discussed" alone.
   Report any unresolved blocker.
4. **Do not mark threads resolved with the resolver.** A maintainer decides
   thread status after reading the reply. If a reply cannot be sent, report
   that limitation rather than claiming it was posted.

5. **Comment style.** Prefer replying as a comment linked to the bot's comment
   rather than a standalone normal post (e.g. `Fix on: #<post-number> What: <short what> Why: <short why>`). If the fix needs follow-up on another PR, leave a short `{"what": ..., "why": ...}` comment pointing to that PR instead. Leave the resolve button to trigger automatically by the bot; fallback to manual resolution only when needed.

## Common false pressures on this repo

| Bot nudge | Contract response |
|---|---|
| Hand-edit generated `skills/` / `config/` / package README to "fix" prose | Rebuild from converter / assets instead |
| Reintroduce Cursor tool names for "clarity" | Banned — use hermes vocabulary |
| Clean up / modernize `agents/` or re-add excluded `benny` / `make-bot-ui` | Leave as-is (scanner / dual-load contract) |
| Implement GitLab stack provider because docs mention `glab` | Halted |
| Treat missing Graphite as a hard CI/product failure | GitHub fallback is intentional |
| Mutate installed stock skills via learning / `skill_manage` | Forbidden as durable source of truth |
