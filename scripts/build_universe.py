"""Refresh data/universe.csv: the five largest S&P 500 companies per GICS sector.

The file is rewritten only if a company entered or left the universe, or
changed sector. Same logic as the "Update S&P 500 data" button of the dashboard.
The universe table in README.md is regenerated from the active universe so the
documentation always matches the data.

Used by the scheduled GitHub Actions workflow (.github/workflows/update-universe.yml).

Usage
    python scripts/build_universe.py
"""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from stock_universe import render_universe_table  # noqa: E402
from universe_refresh import refresh_universe  # noqa: E402

README_PATH = ROOT / "README.md"
README_START = "<!-- universe:start -->"
README_END = "<!-- universe:end -->"

log = logging.getLogger("build_universe")


def replace_universe_section(readme, table):
    """Replace the text between the universe markers of the README with ``table``."""
    start, end = readme.find(README_START), readme.find(README_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"README must contain the {README_START} / {README_END} markers")
    return f"{readme[:start + len(README_START)]}\n{table}\n{readme[end:]}"


def update_readme(universe, path=README_PATH):
    readme = path.read_text(encoding="utf-8")
    updated = replace_universe_section(readme, render_universe_table(universe))
    if updated != readme:
        path.write_text(updated, encoding="utf-8")
        log.info("README universe table updated")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = refresh_universe()
    if result.changed:
        log.info("Universe updated (%s). Added: %s. Removed: %s",
                 result.as_of, ", ".join(result.added) or "none", ", ".join(result.removed) or "none")
    else:
        log.info("Top 5 per sector unchanged; keeping universe dated %s", result.as_of)
    update_readme(result.universe)


if __name__ == "__main__":
    main()
