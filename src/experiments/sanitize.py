"""Rewrite JSONL rows so their error fields hold only what is safe to publish.

    uv run python -m experiments.sanitize experiments/data/*.jsonl

New runs already write clean errors. This is for rows written before that, and it is safe to run
twice. It also relabels the rows where a non-string intent was recorded as a provider error.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from experiments.records import clean_row


def sanitize_file(path: Path) -> int:
    """Rewrite one file in place. Returns how many rows changed."""
    changed = 0
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        clean = clean_row(row)
        changed += clean != row
        lines.append(json.dumps(clean, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    paths = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print("usage: python -m experiments.sanitize FILE.jsonl ...")
        return 2
    for path in paths:
        print(f"{path}: {sanitize_file(path)} rows changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
