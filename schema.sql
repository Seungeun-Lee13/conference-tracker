CREATE TABLE IF NOT EXISTS conferences (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    name                        TEXT NOT NULL,
    year                        INTEGER NOT NULL,
    date_start                  TEXT,
    date_end                    TEXT,
    city                        TEXT,
    country                     TEXT,
    venue                       TEXT,
    abstract_deadline           TEXT,
    late_breaking_deadline      TEXT,
    registration_deadline       TEXT,
    early_registration_deadline TEXT,
    website_url                 TEXT,
    submission_url              TEXT,
    notes                       TEXT,
    last_scraped                TEXT,
    UNIQUE(name, year)
);

CREATE INDEX IF NOT EXISTS idx_abstract_deadline ON conferences(abstract_deadline);
CREATE INDEX IF NOT EXISTS idx_year              ON conferences(year);
