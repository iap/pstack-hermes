#!/usr/bin/env python3
"""Model-slug drift check: configured panel slugs vs the provider catalog.

The panel (tools/assets/model-panel.json) and the shipped config
(pstack/config/models.json) name provider model slugs that were verified
against the catalog when written. Providers deprecate slugs (free tiers
especially), so this tool re-verifies them periodically:

    uv run --frozen tools/slug_drift.py                       # live catalog
    uv run --frozen tools/slug_drift.py --catalog-file <json> # offline/tests

Exit codes: 0 = every configured slug present; 1 = missing slug(s);
2 = tool error (catalog unreachable or unparseable). The weekly
model-drift-watch workflow turns exit 1 into one tracking issue.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # tools/
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_PANEL = SCRIPT_DIR / "assets" / "model-panel.json"
DEFAULT_CONFIG = REPO_ROOT / "pstack" / "config" / "models.json"
DEFAULT_CATALOG_URL = "https://openrouter.ai/api/v1/models"
USER_AGENT = "pstack-hermes-model-drift-watch"
SELECTOR = "inherit-parent"  # always valid; not a provider slug


def collect_slugs(path: Path) -> dict[str, list[str]]:
    """role -> provider slugs (arrays flattened; selectors/non-strings skipped)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    roles = payload.get("roles", {})
    if not isinstance(roles, dict):
        raise ValueError(f"{path}: 'roles' is not an object")
    out: dict[str, list[str]] = {}
    for role, value in roles.items():
        raw = value if isinstance(value, list) else [value]
        out[str(role)] = [s for s in raw if isinstance(s, str) and s != SELECTOR]
    return out


def catalog_ids(payload: dict) -> set[str]:
    """Extract model ids from an OpenRouter-style {"data": [{"id": ...}]} payload."""
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise ValueError("catalog payload 'data' is not a list")
    return {m["id"] for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)}


def load_catalog_file(path: Path) -> set[str]:
    return catalog_ids(json.loads(path.read_text(encoding="utf-8")))


def load_catalog_url(url: str, timeout: float = 30.0) -> set[str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return catalog_ids(json.loads(resp.read().decode("utf-8")))


def check(paths: list[Path], ids: set[str]) -> tuple[list[str], int]:
    """Return (findings, slugs_checked). A finding per missing slug."""
    findings: list[str] = []
    checked = 0
    for path in paths:
        if not path.is_file():
            findings.append(f"{path}: file not found")
            continue
        for role, slugs in collect_slugs(path).items():
            for slug in slugs:
                checked += 1
                if slug not in ids:
                    findings.append(f"{path}: role '{role}' slug '{slug}' "
                                    "is not in the provider catalog")
    return findings, checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--panel", default=str(DEFAULT_PANEL),
                    help="repo-owned model panel (default: tools/assets/model-panel.json)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG),
                    help="shipped config (default: pstack/config/models.json)")
    ap.add_argument("--catalog-url", default=DEFAULT_CATALOG_URL)
    ap.add_argument("--catalog-file", default=None,
                    help="read catalog ids from a JSON file instead of the network")
    args = ap.parse_args()

    try:
        if args.catalog_file:
            ids = load_catalog_file(Path(args.catalog_file))
        else:
            ids = load_catalog_url(args.catalog_url)
    except Exception as exc:
        print(f"slug drift: catalog unavailable: {exc}", file=sys.stderr)
        return 2

    paths = [Path(args.panel), Path(args.config)]
    findings, checked = check(paths, ids)
    for f in findings:
        print(f"MISSING {f}")
    if findings:
        print(f"slug drift: {len(findings)} configured slug(s) missing from the catalog",
              file=sys.stderr)
        return 1
    print(f"model slugs: OK ({checked} configured slug(s) all present; "
          f"{len(ids)} catalog ids checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
