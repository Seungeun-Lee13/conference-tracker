"""Shared SQLite helpers."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "conferences.db"
SCHEMA   = Path(__file__).parent / "schema.sql"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA.read_text())


def upsert_conference(data: dict) -> None:
    """Insert or update a conference row (keyed on name + year)."""
    cols = [
        "name", "year", "date_start", "date_end", "city", "country",
        "abstract_deadline", "late_breaking_deadline",
        "registration_deadline", "early_registration_deadline",
        "website_url", "submission_url", "notes", "last_scraped",
    ]
    row = {c: data.get(c) for c in cols}
    placeholders = ", ".join(f":{c}" for c in cols)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in cols if c not in ("name", "year")
    )
    sql = f"""
        INSERT INTO conferences ({', '.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(name, year) DO UPDATE SET {updates}
    """
    with get_conn() as conn:
        conn.execute(sql, row)
