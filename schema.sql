CREATE TABLE IF NOT EXISTS conferences (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    name                      TEXT NOT NULL,
    year                      INTEGER NOT NULL,
    date_start                TEXT,          -- ISO 8601 YYYY-MM-DD
    date_end                  TEXT,
    city                      TEXT,
    country                   TEXT,
    abstract_deadline         TEXT,          -- ISO 8601 YYYY-MM-DD
    late_breaking_deadline    TEXT,
    registration_deadline     TEXT,
    early_registration_deadline TEXT,
    website_url               TEXT,
    submission_url            TEXT,
    notes                     TEXT,
    last_scraped              TEXT,          -- ISO 8601 datetime
    UNIQUE(name, year)
);

CREATE INDEX IF NOT EXISTS idx_abstract_deadline ON conferences(abstract_deadline);
CREATE INDEX IF NOT EXISTS idx_year              ON conferences(year);
