PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,

    website_domain TEXT,
    ticker TEXT,

    sector TEXT,
    segment TEXT,
    subsegment TEXT,

    universe_flag INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_normalized_name
ON companies(normalized_name);


CREATE TABLE IF NOT EXISTS company_aliases (
    alias_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,

    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,

    alias_type TEXT NOT NULL DEFAULT 'manual',
    confidence REAL NOT NULL DEFAULT 1.0,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id)
        REFERENCES companies(company_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aliases_normalized
ON company_aliases(normalized_alias);


CREATE TABLE IF NOT EXISTS news_events (
    event_id TEXT PRIMARY KEY,

    event_type TEXT NOT NULL,
    headline TEXT,
    summary TEXT,
    event_date TEXT,

    relevance_use TEXT,

    verified INTEGER NOT NULL DEFAULT 0,
    confidence REAL,

    dedupe_key TEXT UNIQUE,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS event_companies (
    event_id TEXT NOT NULL,
    company_id TEXT NOT NULL,

    relationship_type TEXT DEFAULT 'mentioned',
    match_confidence REAL,
    match_method TEXT,

    PRIMARY KEY (event_id, company_id),

    FOREIGN KEY (event_id)
        REFERENCES news_events(event_id)
        ON DELETE CASCADE,

    FOREIGN KEY (company_id)
        REFERENCES companies(company_id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,

    event_id TEXT,

    url TEXT UNIQUE,
    publisher TEXT,
    published_at TEXT,
    source_type TEXT,
    source_title TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (event_id)
        REFERENCES news_events(event_id)
        ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,

    event_id TEXT,
    company_id TEXT,
    source_id TEXT,

    fact_type TEXT,
    metric_name TEXT,

    value_numeric REAL,
    value_text TEXT,
    currency TEXT,
    period TEXT,

    verified INTEGER NOT NULL DEFAULT 0,
    confidence REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (event_id)
        REFERENCES news_events(event_id)
        ON DELETE CASCADE,

    FOREIGN KEY (company_id)
        REFERENCES companies(company_id)
        ON DELETE CASCADE,

    FOREIGN KEY (source_id)
        REFERENCES sources(source_id)
        ON DELETE SET NULL
);


CREATE TABLE IF NOT EXISTS ingestion_log (
    gmail_message_id TEXT PRIMARY KEY,

    gmail_thread_id TEXT,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pipeline_version TEXT,
    status TEXT,
    error TEXT
);
