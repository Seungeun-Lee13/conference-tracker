"""Run all scrapers, detect changes, send Slack new-announcement alerts, export JSON."""
import importlib
import json
import logging
import os
import sys
from pathlib import Path

from db import init_db, upsert_conference
from export_json import export

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# Each scraper module must expose run() -> list[dict]
SCRAPERS = [
    "scraper_esmo",
    # "scraper_asco",
    # "scraper_aacr",
    # "scraper_wclc",
    # "scraper_sitc",
    # "scraper_cap",
    # "scraper_uscap",
]


def run_all(dry_run: bool = False) -> int:
    init_db()
    from slack_notify import send_new_announcement
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")

    success, failed = 0, 0
    for module_name in SCRAPERS:
        try:
            log.info("── %s ──", module_name)
            mod = importlib.import_module(module_name)
            records = mod.run()        # returns list[dict]
            if isinstance(records, dict):
                records = [records]    # backwards compat

            for data in records:
                changes = upsert_conference(data)
                label = f"{data['name']} {data['year']}"
                if changes.get("is_new"):
                    log.info("  NEW: %s", label)
                    send_new_announcement(data, changes, webhook, dry_run)
                elif changes:
                    log.info("  UPDATED %s: %s", label, list(changes))
                    send_new_announcement(data, changes, webhook, dry_run)
                else:
                    log.info("  no change: %s", label)
            success += 1
        except Exception as e:
            log.error("  ✗ %s failed: %s", module_name, e)
            failed += 1

    log.info("\n%d scraper(s) OK, %d failed", success, failed)
    export()
    return failed


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(run_all(dry_run=dry_run))
