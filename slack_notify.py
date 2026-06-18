"""
Slack alerts for two scenarios:
1. Deadline approaching: 180 / 90 / 30 / 7 days before abstract deadline
2. New announcement: a new conference or updated dates/deadlines detected
"""
import json
import os
import sys
import logging
from datetime import date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

JSON_PATH     = Path(__file__).parent / "conferences.json"
ALERT_WINDOWS = [180, 90, 30, 7]


def _load() -> list[dict]:
    if JSON_PATH.exists():
        return json.loads(JSON_PATH.read_text())
    try:
        from db import init_db, get_conn
        init_db()
        with get_conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM conferences")]
    except Exception as e:
        log.error("Cannot load data: %s", e)
        return []


def _days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return (date.fromisoformat(date_str) - date.today()).days
    except ValueError:
        return None


def _fmt_date(date_str: str | None) -> str:
    if not date_str:
        return "TBD"
    try:
        from datetime import datetime
        return datetime.fromisoformat(date_str).strftime("%b %d, %Y")
    except Exception:
        return date_str


def _send(webhook_url: str, text: str, dry_run: bool = False) -> bool:
    if dry_run:
        log.info("[DRY RUN]\n%s", text)
        return True
    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Slack send failed: %s", e)
        return False


def send_deadline_alerts(webhook_url: str, dry_run: bool = False) -> int:
    """Alert when today is exactly N days before a deadline."""
    sent = 0
    for conf in _load():
        days = _days_until(conf.get("abstract_deadline"))
        if days is None or days < 0:
            continue
        if days not in ALERT_WINDOWS:
            continue

        name  = conf.get("name", "?")
        year  = conf.get("year", "")
        dl    = _fmt_date(conf.get("abstract_deadline"))
        loc   = ", ".join(filter(None, [conf.get("city"), conf.get("country")]))
        sub   = conf.get("submission_url") or conf.get("website_url") or ""
        icon  = "🚨" if days <= 7 else "⏰" if days <= 30 else "📅"

        text = (
            f"{icon} *[{name} {year}]* Abstract deadline in *{days} days* ({dl})\n"
            f"📍 {loc}" + (f" | 🔗 <{sub}|Submit>" if sub else "")
        )
        if _send(webhook_url, text, dry_run):
            sent += 1
    return sent


def send_new_announcement(
    conf: dict, changes: dict,
    webhook_url: str = "", dry_run: bool = False
) -> None:
    """Call this from run_scrapers.py when a change is detected."""
    if not webhook_url:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url and not dry_run:
        return

    name = conf.get("name", "?")
    year = conf.get("year", "")
    loc  = ", ".join(filter(None, [conf.get("city"), conf.get("country")]))
    url  = conf.get("website_url", "")

    if changes.get("is_new"):
        text = (
            f"🆕 *[{name} {year}]* New conference announced!\n"
            f"📍 {loc}\n"
            f"📅 {_fmt_date(conf.get('date_start'))} – {_fmt_date(conf.get('date_end'))}\n"
            f"✏️  Abstract deadline: {_fmt_date(conf.get('abstract_deadline'))}"
            + (f"\n🔗 <{url}|More info>" if url else "")
        )
    else:
        lines = [f"🔄 *[{name} {year}]* Conference info updated:"]
        field_labels = {
            "date_start": "Conference start",
            "date_end": "Conference end",
            "abstract_deadline": "Abstract deadline",
            "late_breaking_deadline": "Late-breaking deadline",
            "venue": "Venue",
            "city": "City",
            "country": "Country",
        }
        for field, vals in changes.items():
            label = field_labels.get(field, field)
            old = vals.get("old") or "TBD"
            new = vals.get("new") or "TBD"
            lines.append(f"  • {label}: `{old}` → `{new}`")
        if url:
            lines.append(f"🔗 <{url}|More info>")
        text = "\n".join(lines)

    _send(webhook_url, text, dry_run)


def run(dry_run: bool = False) -> int:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url and not dry_run:
        log.error("SLACK_WEBHOOK_URL not set. Use --dry-run to test.")
        return 1
    sent = send_deadline_alerts(webhook_url, dry_run)
    log.info("Sent %d deadline alert(s).", sent)
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(run(dry_run=dry_run))
