"""Run all available scrapers and export to conferences.json."""
import importlib
import logging
import sys
from pathlib import Path

from db import init_db, upsert_conference
from export_json import export

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SCRAPERS = [
    "scraper_esmo",
    # Add new scrapers here: "scraper_asco", "scraper_aacr", etc.
]


def run_all() -> int:
    init_db()
    success, failed = 0, 0

    for module_name in SCRAPERS:
        try:
            log.info("── Running %s ──", module_name)
            mod = importlib.import_module(module_name)
            data = mod.run()
            upsert_conference(data)
            log.info("  ✓ %s %s saved", data["name"], data["year"])
            success += 1
        except Exception as exc:
            log.error("  ✗ %s failed: %s", module_name, exc)
            failed += 1

    log.info("\n%d scraper(s) succeeded, %d failed", success, failed)
    export()
    return failed   # non-zero exit if any scraper failed


if __name__ == "__main__":
    sys.exit(run_all())
