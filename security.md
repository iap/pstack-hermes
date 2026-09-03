# Security Policy

## Supported versions

The `main` branch is the only supported line. The package is content-only
(markdown skills + config); the tooling (`tools/`) is Python 3.11.

## Reporting a vulnerability

Please use **GitHub's private vulnerability reporting** on this repository
(Security tab → Report a vulnerability). Reports stay private until a fix is
ready.

## Scope notes

- The shipped package (`pstack/`) performs no network calls, no telemetry,
  and no code execution beyond the scripts documented in each skill.
- The install-scanner contract (community-source safety verdict) is enforced
  in CI; the banned-construct list lives in `.github/workflows/ci.yml`.
- Upstream (pstack, MIT © Lauren Tan) issues that also affect the original
  should be reported upstream first:
  <https://github.com/cursor/plugins/tree/main/pstack>
