MIGRATIONS = ["""
/* ===================== staff ===================== */

CREATE TABLE staff_staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    timezone TEXT NOT NULL,
    schedule TEXT NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_blacklisted BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_department (
    key TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    head INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (head) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE staff_staff_departments (
    staff_id INTEGER NOT NULL,
    department_key TEXT NOT NULL,
    on_trial BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (staff_id, department_key),
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (department_key) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE staff_accounts (
    account_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_staff_accounts (
    account_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id, staff_id),
    FOREIGN KEY (account_id) REFERENCES staff_accounts (account_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE staff_server_departments (
    server_id INTEGER NOT NULL,
    department_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (server_id, department_key),
    FOREIGN KEY (server_id) REFERENCES assets_discord_server (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (department_key) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE CASCADE
);

/* ===================== assets ===================== */

CREATE TABLE assets_discord_server (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    configuration TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assets_server_roles (
    id INTEGER PRIMARY KEY,
    server_id INTEGER NOT NULL,
    department_ownership TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES assets_discord_server (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (department_ownership) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE assets_roblox_discord_roles (
    roblox_id INTEGER NOT NULL,
    discord_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (roblox_id, discord_id),
    FOREIGN KEY (roblox_id) REFERENCES department_roblox_roles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (discord_id) REFERENCES assets_server_roles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

/* ===================== department ===================== */

CREATE TABLE department_roblox_roles (
    id INTEGER PRIMARY KEY,
    department_ownership TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_ownership) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE department_tester_reports (
    id INTEGER PRIMARY KEY,
    author INTEGER NOT NULL,
    content TEXT,
    decision INTEGER NOT NULL DEFAULT 0,
    asignee INTEGER,
    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    fixer INTEGER NOT NULL,
    fixed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (fixer) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE department_instructor_instructions (
    id INTEGER PRIMARY KEY,
    claimer INTEGER NOT NULL,
    verifier INTEGER NOT NULL,
    closed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (claimer) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (verifier) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE department_tester_misc_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

/* ===================== indexes ===================== */

CREATE INDEX creation_timestamp_index ON department_tester_reports (created_at ASC);
CREATE INDEX author_stats_index ON department_tester_reports (author, created_at);
CREATE INDEX author_decision_rates ON department_tester_reports (author, decision, created_at);
CREATE INDEX fixer_statistics ON department_tester_reports (fixer, fixed_at);
CREATE INDEX time_to_fix ON department_tester_reports (created_at, fixed_at);
CREATE INDEX asignee_tat ON department_tester_reports (asignee, assigned_at, fixed_at);
    """

]
