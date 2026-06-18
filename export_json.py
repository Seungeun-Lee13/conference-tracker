"""Export SQLite conferences table to conferences.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

from db import init_db, get_conn

JSON_PATH = Path(__file__).parent / "conferences.json"


def export() -> None:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conferences ORDER BY abstract_deadline"
        ).fetchall()

    records = [dict(r) for r in rows]
    # Remove internal id column
    for r in records:
        r.pop("id", None)

    JSON_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"Exported {len(records)} conferences → {JSON_PATH}")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    export()
