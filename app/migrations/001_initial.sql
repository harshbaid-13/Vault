-- 001: the whole v1 schema (docs/TECH_PLAN.md §2).
-- schema_version is created by app/db.py, not here.
-- Timestamps: ISO-8601 UTC text from db.now(). Booleans: INTEGER 0/1.

-- Key/value. Keys used: password_hash, session_version, files_sort (the root folder's sort).
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) STRICT;

CREATE TABLE folders (
  id         INTEGER PRIMARY KEY,
  parent_id  INTEGER REFERENCES folders(id) ON DELETE CASCADE,   -- NULL = root
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
  sort       TEXT NOT NULL DEFAULT 'name'
             CHECK (sort IN ('name','-name','date','-date','size','-size','type','-type')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
-- Unique name per parent, case-insensitive. IFNULL because NULLs never collide in a UNIQUE index.
CREATE UNIQUE INDEX folders_parent_name ON folders (IFNULL(parent_id, 0), name COLLATE NOCASE);

CREATE TABLE files (
  id         TEXT PRIMARY KEY CHECK (length(id) = 32),             -- uuid4().hex, also the disk name
  folder_id  INTEGER REFERENCES folders(id) ON DELETE CASCADE,     -- NULL = root
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255), -- display text only
  size       INTEGER NOT NULL CHECK (size >= 0),
  sha256     TEXT NOT NULL CHECK (length(sha256) = 64),            -- hashed while streaming
  mime       TEXT NOT NULL,                                        -- from the extension
  kind       TEXT NOT NULL CHECK (kind IN ('image','video','audio','pdf','text','other')),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at TEXT NOT NULL,                                        -- upload time
  updated_at TEXT NOT NULL
) STRICT;
CREATE INDEX files_folder   ON files (folder_id, name COLLATE NOCASE);
CREATE INDEX files_recent   ON files (created_at DESC);
CREATE INDEX files_photos   ON files (kind, created_at DESC);
CREATE INDEX files_favorite ON files (favorite) WHERE favorite = 1;

CREATE TABLE notes (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 200),
  body       TEXT NOT NULL DEFAULT '' CHECK (length(body) <= 1000000),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE INDEX notes_list ON notes (favorite DESC, updated_at DESC);

CREATE TABLE clips (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '' CHECK (length(title) <= 200),
  content    TEXT NOT NULL DEFAULT '' CHECK (length(content) <= 100000),
  hidden     INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE INDEX clips_list ON clips (favorite DESC, updated_at DESC);

CREATE TABLE links (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  url         TEXT NOT NULL
              CHECK (length(url) <= 2000 AND (url LIKE 'http://%' OR url LIKE 'https://%')),
  description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 1000),
  favorite    INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX links_list ON links (favorite DESC, created_at DESC);
