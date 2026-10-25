"""Refresh data/universe.csv: the five largest S&P 500 companies per GICS sector.

The file is rewritten only if a company entered or left the universe, or
changed sector. Same logic as the "Update S&P 500 data" button of the dashboard.

Usage
    python scripts/build_universe.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from universe_refresh import refresh_universe  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("build_universe")


def main():
    result = refresh_universe()
    if not result.changed:
        log.info("Top 5 per sector unchanged; keeping universe dated %s", result.as_of)
        return
    log.info("Universe updated (%s). Added: %s. Removed: %s",
             result.as_of, ", ".join(result.added) or "none", ", ".join(result.removed) or "none")


if __name__ == "__main__":
    main()
