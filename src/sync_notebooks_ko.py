"""Keep the Korean notebooks in sync with the English ones.

The English notebooks are the source of truth. Each Korean notebook is built from its English twin:

- code cells and their outputs are copied untouched, so the experiment results are identical;
- Markdown cells are replaced by their Korean text from notebooks/ko.json, which maps the exact
  English Markdown text to its Korean translation.

Usage:
    uv run python sync_notebooks_ko.py            # rewrite the *-ko.ipynb files
    uv run python sync_notebooks_ko.py --check    # fail if they are out of date (used by a test)

After re-running an English notebook, run this script to refresh the Korean one. If an English
Markdown cell changed, add its new text to notebooks/ko.json first.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import nbformat

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"
TRANSLATIONS = NOTEBOOKS_DIR / "ko.json"
NAMES = ["01-case01-routing", "02-case02-deepagents", "03-case04-structured-control"]


def build_korean(english: nbformat.NotebookNode, translations: dict[str, str]) -> tuple:
    """Return the Korean notebook and the English Markdown texts that have no translation yet."""
    korean = copy.deepcopy(english)
    missing = []
    for cell in korean.cells:
        if cell.cell_type != "markdown":
            continue
        text = cell.source
        if text in translations:
            cell.source = translations[text]
        else:
            missing.append(text)
    return korean, missing


def main(argv: list[str]) -> int:
    check = "--check" in argv
    translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    problems = 0
    for name in NAMES:
        source = NOTEBOOKS_DIR / f"{name}.ipynb"
        target = NOTEBOOKS_DIR / f"{name}-ko.ipynb"
        english = nbformat.read(source, as_version=4)
        korean, missing = build_korean(english, translations)
        for text in missing:
            print(f"missing Korean text in ko.json for: {text.splitlines()[0]!r}")
        problems += len(missing)
        rendered = nbformat.writes(korean) + "\n"
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                print(f"out of date: {target.name}")
                problems += 1
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"wrote {target.name}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
