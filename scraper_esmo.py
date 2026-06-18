"""
ESMO Congress scraper.
- Scrapes current year; if abstract deadline has passed, also checks next year.
- Graceful fallback to hardcoded data if scraping fails.
"""
import re
import logging
from datetime import datetime, date, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from db import init_db, upsert_conference

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# ── Fallback data per year ──────────────────────────────────────────────────
FALLBACKS = {
    2026: {
        "name": "ESMO", "year": 2026,
        "date_start": "2026-10-23", "date_end": "2026-10-27",
        "city": "Madrid", "country": "Spain", "venue": "IFEMA Madrid",
        "abstract_deadline": "2026-05-12",
        "late_breaking_deadline": "2026-09-08",
        "registration_deadline": "2026-09-30",
        "early_registration_deadline": "2026-05-15",
        "website_url": "https://www.esmo.org/meeting-calendar/esmo-congress-2026",
        "submission_url": "https://www.esmo.org/meeting-calendar/esmo-congress-2026/abstracts",
        "notes": "European Society for Medical Oncology Congress 2026. IFEMA Madrid.",
    },
}

MONTH_MAP = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"], 1
)}
DATE_PATTERNS = [
    (r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b",   "dmy"),
    (r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})\b",  "mdy"),
    (r"\b(20\d{2})-(\d{2})-(\d{2})\b",               "iso"),
]


def _parse_date(text: str) -> Optional[str]:
    for pat, fmt in DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        g = m.groups()
        try:
            if fmt == "iso":
                return f"{g[0]}-{g[1]}-{g[2]}"
            elif fmt == "dmy":
                mn = MONTH_MAP.get(g[1].lower())
                return f"{g[2]}-{mn:02d}-{int(g[0]):02d}" if mn else None
            else:
                mn = MONTH_MAP.get(g[0].lower())
                return f"{g[2]}-{mn:02d}-{int(g[1]):02d}" if mn else None
        except Exception:
            pass
    return None


def _scrape(url: str) -> dict:
    data: dict = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Dates
        for kw in ["October", "November", "September"]:
            date_m = re.search(rf"\d{{1,2}}\s+{kw}\s+20\d{{2}}", text, re.I)
            if date_m:
                data["date_start"] = _parse_date(date_m.group())
                break

        # City
        for city in ["Madrid", "Paris", "Barcelona", "Berlin", "Amsterdam", "London"]:
            if city in text:
                data["city"] = city
                break

        # Venue
        for venue in ["IFEMA", "Palacio de Congresos", "CCIB", "Palau de Congressos"]:
            if venue in text:
                data["venue"] = venue
                break

        # Abstract deadline
        for label in ["abstract submission", "abstract deadline", "submission deadline"]:
            idx = text.lower().find(label)
            if idx >= 0:
                chunk = text[idx:idx+120]
                d = _parse_date(chunk)
                if d:
                    data["abstract_deadline"] = d
                    break

        # Late-breaking
        idx = text.lower().find("late-break")
        if idx >= 0:
            chunk = text[idx:idx+120]
            d = _parse_date(chunk)
            if d:
                data["late_breaking_deadline"] = d

        log.info("Scraped %s — found: %s", url, list(data.keys()))
    except requests.RequestException as e:
        log.warning("Network error: %s", e)
    except Exception as e:
        log.warning("Parse error: %s", e)
    return data


def _make_record(year: int, scraped: dict) -> dict:
    fallback = FALLBACKS.get(year, {**FALLBACKS[2026], "year": year,
        "website_url": f"https://www.esmo.org/meeting-calendar/esmo-congress-{year}",
        "submission_url": f"https://www.esmo.org/meeting-calendar/esmo-congress-{year}/abstracts",
        "notes": f"ESMO Congress {year}. Verify dates on official site.",
        "abstract_deadline": None, "late_breaking_deadline": None,
        "date_start": None, "date_end": None,
    })
    result = {**fallback, **{k: v for k, v in scraped.items() if v}}
    result["last_scraped"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return result


def run(year: int = 2026) -> list[dict]:
    """Returns list of conference dicts to upsert (current year, maybe next year)."""
    url = f"https://www.esmo.org/meeting-calendar/esmo-congress-{year}"
    log.info("Scraping ESMO %d from %s", year, url)
    scraped = _scrape(url)
    records = [_make_record(year, scraped)]

    # If current year's abstract deadline has passed, try next year
    deadline = records[0].get("abstract_deadline")
    if deadline:
        try:
            if date.fromisoformat(deadline) < date.today():
                next_year = year + 1
                log.info("Abstract deadline passed — checking ESMO %d", next_year)
                next_url = f"https://www.esmo.org/meeting-calendar/esmo-congress-{next_year}"
                next_scraped = _scrape(next_url)
                if next_scraped.get("date_start") or next_scraped.get("abstract_deadline"):
                    records.append(_make_record(next_year, next_scraped))
                    log.info("Found ESMO %d data", next_year)
        except ValueError:
            pass

    return records


if __name__ == "__main__":
    init_db()
    for conf in run():
        changes = upsert_conference(conf)
        status = "NEW" if changes.get("is_new") else (f"UPDATED {list(changes)}" if changes else "no change")
        log.info("ESMO %d → %s | Abstract: %s", conf["year"], status, conf.get("abstract_deadline"))
