"""Shared SQLite helpers."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "conferences.db"
SCHEMA   = Path(__file__).parent / "schema.sql"

COLS = [
    "name", "year", "date_start", "date_end", "city", "country", "venue",
    "abstract_deadline", "late_breaking_deadline",
    "registration_deadline", "early_registration_deadline",
    "website_url", "submission_url", "notes", "last_scraped",
]

CHANGE_WATCHED = {
    "date_start", "date_end", "abstract_deadline",
    "late_breaking_deadline", "venue", "city", "country",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA.read_text())
        # Safe migration: add venue if missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(conferences)")}
        if "venue" not in cols:
            conn.execute("ALTER TABLE conferences ADD COLUMN venue TEXT")


def get_existing(name: str, year: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conferences WHERE name=? AND year=?", (name, year)
        ).fetchone()
    return dict(row) if row else None


def detect_changes(old: dict | None, new: dict) -> dict:
    """Return dict of changed fields; 'is_new' key if no old record."""
    if old is None:
        return {"is_new": True}
    changed = {}
    for field in CHANGE_WATCHED:
        old_val = old.get(field) or ""
        new_val = new.get(field) or ""
        if old_val != new_val and new_val:
            changed[field] = {"old": old_val, "new": new_val}
    return changed


def upsert_conference(data: dict) -> dict:
    """Insert or update conference. Returns change dict."""
    existing = get_existing(data["name"], data["year"])
    changes  = detect_changes(existing, data)

    row = {c: data.get(c) for c in COLS}
    placeholders = ", ".join(f":{c}" for c in COLS)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in COLS if c not in ("name", "year")
    )
    sql = f"""
        INSERT INTO conferences ({', '.join(COLS)})
        VALUES ({placeholders})
        ON CONFLICT(name, year) DO UPDATE SET {updates}
    """
    with get_conn() as conn:
        conn.execute(sql, row)
    return changes
