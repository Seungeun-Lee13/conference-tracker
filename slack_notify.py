"""
Send Slack alerts for upcoming abstract deadlines.

Trigger windows (days before deadline): 180, 90, 30, 7
Reads conferences.json (or SQLite if --db flag passed).
Uses SLACK_WEBHOOK_URL environment variable.
"""
import json
import os
import sys
import logging
from datetime import datetime, timezone, date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

JSON_PATH    = Path(__file__).parent / "conferences.json"
ALERT_WINDOWS = [180, 90, 30, 7]   # days before deadline


def _load_conferences() -> list[dict]:
    if JSON_PATH.exists():
        return json.loads(JSON_PATH.read_text())
    # Fallback: read from SQLite
    try:
        from db import init_db, get_conn
        init_db()
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM conferences").fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.error("Could not load data: %s", exc)
        return []


def _days_until(date_str: str) -> int | None:
    if not date_str:
        return None
    try:
        deadline = date.fromisoformat(date_str)
        return (deadline - date.today()).days
    except ValueError:
        return None


def _build_message(conf: dict, days: int) -> dict:
    name     = conf.get("name", "Unknown")
    year     = conf.get("year", "")
    deadline = conf.get("abstract_deadline", "")
    city     = conf.get("city", "")
    country  = conf.get("country", "")
    sub_url  = conf.get("submission_url") or conf.get("website_url") or ""

    try:
        dl_fmt = datetime.fromisoformat(deadline).strftime("%b %d, %Y")
    except Exception:
        dl_fmt = deadline

    location = ", ".join(filter(None, [city, country]))
    link_part = f" | 🔗 <{sub_url}|Submit>" if sub_url else ""

    urgency = (
        "🚨" if days <= 7 else
        "⏰" if days <= 30 else
        "📅"
    )

    text = (
        f"{urgency} *[{name} {year}]* Abstract deadline in *{days} days* ({dl_fmt})\n"
        f"📍 {location}{link_part}"
    )

    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            }
        ]
    }


def _send(webhook_url: str, payload: dict, dry_run: bool = False) -> bool:
    if dry_run:
        log.info("[DRY RUN] Would send:\n%s", payload["text"])
        return True
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        log.error("Slack send failed: %s", exc)
        return False


def run(dry_run: bool = False) -> int:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url and not dry_run:
        log.error("SLACK_WEBHOOK_URL not set. Pass --dry-run to test without sending.")
        return 1

    conferences = _load_conferences()
    if not conferences:
        log.warning("No conferences found.")
        return 0

    sent = 0
    for conf in conferences:
        days = _days_until(conf.get("abstract_deadline"))
        if days is None:
            continue
        if days < 0:
            continue    # already passed

        # Alert if today lands exactly on a trigger window (±0 days)
        if days in ALERT_WINDOWS:
            msg = _build_message(conf, days)
            log.info("Sending alert: %s %s — %d days", conf.get("name"), conf.get("year"), days)
            if _send(webhook_url, msg, dry_run):
                sent += 1

    log.info("Sent %d alert(s).", sent)
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(run(dry_run=dry_run))
