"""
ESMO 2026 scraper.
Falls back gracefully to manual values if the website structure changes.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from db import init_db, upsert_conference

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Hardcoded fallback (updated manually each year) ────────────────────────
FALLBACK = {
    "name":                       "ESMO",
    "year":                       2026,
    "date_start":                 "2026-09-11",
    "date_end":                   "2026-09-15",
    "city":                       "Berlin",
    "country":                    "Germany",
    "abstract_deadline":          "2026-04-14",
    "late_breaking_deadline":     "2026-06-30",
    "registration_deadline":      None,
    "early_registration_deadline": "2026-05-15",
    "website_url":                "https://www.esmo.org/meetings/esmo-congress-2026",
    "submission_url":             "https://www.esmo.org/meetings/esmo-congress-2026/abstract-submission",
    "notes":                      "ESMO Congress 2026. Fallback data — verify via official site.",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

DATE_PATTERNS = [
    r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b",   # 14 April 2026
    r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})\b",  # April 14, 2026
    r"\b(20\d{2})-(\d{2})-(\d{2})\b",               # 2026-04-14
]
MONTH_MAP = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"], 1
)}


def _parse_date(text: str) -> Optional[str]:
    """Try to extract ISO date from a string."""
    t = text.strip()
    for pat in DATE_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            g = m.groups()
            try:
                if re.match(r"\d{4}", g[0]):        # ISO pattern
                    return f"{g[0]}-{g[1]}-{g[2]}"
                elif re.match(r"\d{1,2}", g[0]):    # day-month-year
                    month_num = MONTH_MAP.get(g[1].lower())
                    if month_num:
                        return f"{g[2]}-{month_num:02d}-{int(g[0]):02d}"
                else:                               # month-day-year
                    month_num = MONTH_MAP.get(g[0].lower())
                    if month_num:
                        return f"{g[2]}-{month_num:02d}-{int(g[1]):02d}"
            except Exception:
                pass
    return None


def _scrape_esmo(url: str) -> dict:
    """Attempt live scrape; return dict with whatever we can find."""
    data: dict = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Conference dates ---
        date_block = soup.find(string=re.compile(r"(September|October|November)\s+20\d{2}", re.I))
        if date_block:
            dates = re.findall(r"\d{1,2}\s+\w+\s+20\d{2}", date_block, re.I)
            if len(dates) >= 2:
                data["date_start"] = _parse_date(dates[0])
                data["date_end"]   = _parse_date(dates[-1])
            elif dates:
                data["date_start"] = _parse_date(dates[0])

        # --- Location ---
        loc = soup.find(string=re.compile(r"\b(Berlin|Paris|Madrid|Barcelona|Amsterdam)\b", re.I))
        if loc:
            city_m = re.search(r"\b(Berlin|Paris|Madrid|Barcelona|Amsterdam)\b", str(loc), re.I)
            if city_m:
                data["city"] = city_m.group(1)

        # --- Abstract deadline ---
        for label in ["abstract submission", "abstract deadline", "submission deadline"]:
            node = soup.find(string=re.compile(label, re.I))
            if node:
                parent_text = node.find_parent().get_text(" ", strip=True) if node.find_parent() else ""
                d = _parse_date(parent_text)
                if d:
                    data["abstract_deadline"] = d
                    break

        # --- Late-breaking ---
        lb = soup.find(string=re.compile(r"late.?breaking", re.I))
        if lb:
            parent_text = lb.find_parent().get_text(" ", strip=True) if lb.find_parent() else ""
            d = _parse_date(parent_text)
            if d:
                data["late_breaking_deadline"] = d

        log.info("Scrape succeeded; found keys: %s", list(data.keys()))
    except requests.RequestException as exc:
        log.warning("Network error during scrape: %s", exc)
    except Exception as exc:
        log.warning("Parse error during scrape: %s", exc)

    return data


def run() -> dict:
    url = FALLBACK["website_url"]
    log.info("Scraping ESMO 2026 from %s", url)

    scraped = _scrape_esmo(url)

    # Merge: scraped values take priority over fallback
    result = {**FALLBACK, **{k: v for k, v in scraped.items() if v}}
    result["last_scraped"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["country"] = result.get("country") or "Germany"

    return result


if __name__ == "__main__":
    init_db()
    conference = run()
    upsert_conference(conference)
    log.info("Saved: %s %s", conference["name"], conference["year"])
    log.info("Abstract deadline: %s", conference.get("abstract_deadline"))
