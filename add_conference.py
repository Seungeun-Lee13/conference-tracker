#!/usr/bin/env python3
"""Interactive CLI for adding or editing conference entries."""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from db import init_db, upsert_conference, get_conn

JSON_PATH = Path(__file__).parent / "conferences.json"

FIELDS = [
    ("name",                        "Conference name (e.g. ASCO)",          True),
    ("year",                        "Year (e.g. 2027)",                      True),
    ("date_start",                  "Start date (YYYY-MM-DD)",               False),
    ("date_end",                    "End date   (YYYY-MM-DD)",               False),
    ("city",                        "City",                                  False),
    ("country",                     "Country",                               False),
    ("abstract_deadline",           "Abstract deadline (YYYY-MM-DD)",        False),
    ("late_breaking_deadline",      "Late-breaking deadline (YYYY-MM-DD)",   False),
    ("registration_deadline",       "Registration deadline (YYYY-MM-DD)",    False),
    ("early_registration_deadline", "Early-reg deadline (YYYY-MM-DD)",       False),
    ("website_url",                 "Website URL",                           False),
    ("submission_url",              "Submission URL",                        False),
    ("notes",                       "Notes (free text)",                     False),
]

DATE_FIELDS = {
    "date_start", "date_end",
    "abstract_deadline", "late_breaking_deadline",
    "registration_deadline", "early_registration_deadline",
}


def _prompt(label: str, required: bool, current: str = "") -> str:
    hint = f" [{current}]" if current else (" (required)" if required else " (optional, Enter to skip)")
    while True:
        val = input(f"  {label}{hint}: ").strip()
        if not val and current:
            return current
        if not val and required:
            print("  This field is required.")
            continue
        return val or ""


def _validate_date(val: str, field: str) -> str:
    if not val:
        return val
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except ValueError:
        print(f"  Warning: '{val}' is not a valid YYYY-MM-DD date for {field}. Saved as-is.")
        return val


def _load_json() -> list:
    if JSON_PATH.exists():
        return json.loads(JSON_PATH.read_text())
    return []


def _save_json(records: list) -> None:
    JSON_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False))


def _find_existing(name: str, year: int) -> dict | None:
    records = _load_json()
    for r in records:
        if r.get("name", "").upper() == name.upper() and r.get("year") == year:
            return r
    return None


def _sync_to_json(data: dict) -> None:
    records = _load_json()
    for i, r in enumerate(records):
        if r.get("name", "").upper() == data["name"].upper() and r.get("year") == data["year"]:
            records[i] = data
            _save_json(records)
            return
    records.append(data)
    _save_json(records)


def _list_conferences() -> None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, year, city, country, abstract_deadline "
            "FROM conferences ORDER BY abstract_deadline"
        ).fetchall()
    if not rows:
        print("No conferences in database yet.")
        return
    print(f"\n{'Name':<10} {'Year':<6} {'Location':<20} {'Abstract Deadline'}")
    print("-" * 60)
    for r in rows:
        loc = f"{r['city'] or ''}, {r['country'] or ''}".strip(", ")
        print(f"{r['name']:<10} {r['year']:<6} {loc:<20} {r['abstract_deadline'] or 'N/A'}")
    print()


def _add_or_edit() -> None:
    print("\n── Add / Edit Conference ──────────────────────────────────")
    name = input("  Conference name (e.g. ASCO): ").strip().upper()
    if not name:
        print("Name is required.")
        return
    year_str = input("  Year (e.g. 2027): ").strip()
    if not year_str.isdigit():
        print("Invalid year.")
        return
    year = int(year_str)

    existing = _find_existing(name, year)
    if existing:
        print(f"\n  Existing entry found for {name} {year}. Press Enter to keep current value.")
    else:
        existing = {}

    data: dict = {"name": name, "year": year}
    for key, label, required in FIELDS:
        if key in ("name", "year"):
            continue
        current = str(existing.get(key) or "")
        val = _prompt(label, required, current)
        if key in DATE_FIELDS:
            val = _validate_date(val, key)
        data[key] = val or None

    data["last_scraped"] = None

    init_db()
    upsert_conference(data)
    _sync_to_json(data)
    print(f"\n  ✓ Saved {name} {year} to database and conferences.json")


def _delete() -> None:
    name = input("  Conference name to delete: ").strip().upper()
    year_str = input("  Year: ").strip()
    if not year_str.isdigit():
        print("Invalid year.")
        return
    year = int(year_str)
    confirm = input(f"  Delete {name} {year}? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM conferences WHERE name=? AND year=?", (name, year))
    records = [r for r in _load_json()
               if not (r.get("name", "").upper() == name and r.get("year") == year)]
    _save_json(records)
    print(f"  ✓ Deleted {name} {year}")


def main() -> None:
    print("═══════════════════════════════════════")
    print("  Conference Tracker — Manual Entry CLI")
    print("═══════════════════════════════════════")

    while True:
        print("\nOptions:")
        print("  1. Add / Edit conference")
        print("  2. List conferences")
        print("  3. Delete conference")
        print("  4. Quit")
        choice = input("\nChoice [1-4]: ").strip()

        if choice == "1":
            _add_or_edit()
        elif choice == "2":
            init_db()
            _list_conferences()
        elif choice == "3":
            init_db()
            _delete()
        elif choice == "4" or choice.lower() in ("q", "quit", "exit"):
            print("Bye.")
            sys.exit(0)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
