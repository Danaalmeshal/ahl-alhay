-- Ahl Al-Hay database schema (Sprint 1)
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS replies;
DROP TABLE IF EXISTS help_requests;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS invitation_codes;
DROP TABLE IF EXISTS join_requests;
DROP TABLE IF EXISTS neighborhoods;

CREATE TABLE neighborhoods (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- PBI 1 / 2A: join requests reviewed by the neighborhood administrator
CREATE TABLE join_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,  -- shown to the applicant as the request number
    name             TEXT NOT NULL,
    phone            TEXT NOT NULL,
    address          TEXT NOT NULL,
    neighborhood_id  INTEGER NOT NULL REFERENCES neighborhoods(id),
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    rejection_reason TEXT,
    welcome_message  TEXT,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at       TEXT
);

-- PBI 3A: one-time invitation code, generated automatically on approval
CREATE TABLE invitation_codes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    join_request_id INTEGER NOT NULL UNIQUE REFERENCES join_requests(id),
    neighborhood_id INTEGER NOT NULL REFERENCES neighborhoods(id),
    used_at         TEXT
);

-- PBI 4A / 5A: accounts (residents and administrators)
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'resident' CHECK (role IN ('resident','admin')),
    neighborhood_id INTEGER NOT NULL REFERENCES neighborhoods(id),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen       TEXT  -- updated while the user is on the site; NULL after logout (activity status)
);

-- PBI 7-10: help requests and their replies
CREATE TABLE help_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    author_id       INTEGER NOT NULL REFERENCES users(id),
    neighborhood_id INTEGER NOT NULL REFERENCES neighborhoods(id),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TEXT
);

CREATE TABLE replies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    help_request_id INTEGER NOT NULL REFERENCES help_requests(id),
    author_id       INTEGER NOT NULL REFERENCES users(id),
    body            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bell notifications. The text is built from `kind` + `params` (JSON) so it can be shown in Arabic or English.
CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    kind       TEXT NOT NULL,
    params     TEXT NOT NULL DEFAULT '{}',
    link       TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at    TEXT
);
