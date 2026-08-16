MIGRATIONS: list[str] = [
    """
/* ===================== fresh setup =============== */
PRAGMA page_size = 4096;

/* ===================== staff ===================== */

CREATE TABLE staff_staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT,
    timezone TEXT,
    schedule BLOB NOT NULL DEFAULT (jsonb('{}')),
    discord_id INT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    is_blacklisted BOOLEAN NOT NULL DEFAULT 0 CHECK (is_blacklisted IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_department (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    head INTEGER NOT NULL,
    configuration BLOB NOT NULL DEFAULT (jsonb('{}')),
    servers BLOB NOT NULL DEFAULT (jsonb('[]')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (head) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE staff_staff_department (
    staff_id INTEGER NOT NULL,
    department_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
    FOREIGN KEY (department_key) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE RESTRICT
    PRIMARY KEY (staff_id, department_key)
);

/* ===================== department ===================== */

CREATE TABLE department_tester_reports (
    id INTEGER PRIMARY KEY,
    author INTEGER NOT NULL,
    content TEXT,
    decision INTEGER NOT NULL DEFAULT 0 CHECK (decision IN (-1,0,1)),
    severity INTEGER CHECK (severity IS NULL OR severity BETWEEN 0 AND 4),
    triager INTEGER,
    triaged_at TEXT,
    asignee INTEGER,
    assigned_at TEXT,
    fixer INTEGER,
    fixed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (fixer) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
    FOREIGN KEY (triager) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (asignee) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE department_instructor_instructions (
    id INTEGER PRIMARY KEY,
    claimer INTEGER NOT NULL,
    is_finished INTEGER CHECK (is_finished IN (0,1)),
    verifier INTEGER,
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
CREATE INDEX idx_staff_staff_discord_id ON staff_staff(discord_id);

CREATE INDEX idx_department_tester_reports_tester_statistics ON department_tester_reports(author, created_at, decision);
CREATE INDEX idx_department_tester_reports_developer_statistics ON department_tester_reports(fixer, fixed_at, decision);
CREATE INDEX idx_department_tester_reports_report_severity ON department_tester_reports(severity);

CREATE INDEX idx_department_instructor_instructions_instructor_points ON department_instructor_instructions(claimer, closed_at);
/* ===================== views ======================= */

/* ===================== triggers ===================== */
CREATE TRIGGER update_staff_staff_edited_at
AFTER UPDATE ON staff_staff
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE staff_staff SET edited_at = CURRENT_TIMESTAMP WHERE staff_id = OLD.staff_id;
END;

CREATE TRIGGER update_staff_department_edited_at
AFTER UPDATE ON staff_department
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE staff_department SET edited_at = CURRENT_TIMESTAMP WHERE key = OLD.key;
END;

CREATE TRIGGER update_staff_staff_department_edited_at
AFTER UPDATE ON staff_staff_department
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE staff_staff_department SET edited_at = CURRENT_TIMESTAMP WHERE staff_id = OLD.staff_id AND department_key = OLD.department_key;
END;

CREATE TRIGGER update_department_tester_reports_edited_at
AFTER UPDATE ON department_tester_reports
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE department_tester_reports SET edited_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER update_department_instructor_instructions_edited_at
AFTER UPDATE ON department_instructor_instructions
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE department_instructor_instructions SET edited_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER update_department_tester_misc_performance_edited_at
AFTER UPDATE ON department_tester_misc_performance
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE department_tester_misc_performance SET edited_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

/* =====================prebuilt data ================ */
INSERT INTO staff_staff (staff_id, name, discord_id) 
    VALUES (0, 'isaac', 1244953844451119157);

INSERT INTO staff_department (key, name, head) VALUES
    ('bod', 'Board of Directors', 0),
    ('dept', 'Department Heads', 0),
    ('dev', 'Development Department', 0),
    ('ad', 'Administration Department', 0),
    ('cr', 'Community Relations', 0),
    ('sys', 'Systems Department', 0),
    ('qa', 'Testing Team', 0),
    ('cont', 'Contributors', 0),
    ('inst', 'Instruction Department', 0);
    """,
    """
CREATE TABLE staff_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    note TEXT NOT NULL,
    noter INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (noter) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE staff_strikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    striker INTEGER NOT NULL,
    department TEXT NOT NULL,
    strike_end TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (striker) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (department) REFERENCES staff_department (key)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE asset_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#808080',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    tagged_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (tag_id) REFERENCES asset_tags (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (tagged_by) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);
""",
    """
DROP TRIGGER update_staff_staff_department_edited_at;

CREATE TRIGGER update_staff_staff_department_edited_at
AFTER UPDATE ON staff_staff_department
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
    UPDATE staff_staff_department SET edited_at = CURRENT_TIMESTAMP WHERE staff_id = OLD.staff_id AND department_key = OLD.department_key;
END;

INSERT INTO staff_department (key, name, head) VALUES
    ('wiki', 'Wiki Department', 0);

ALTER TABLE staff_department
    ADD COLUMN staff_level INTEGER NOT NULL DEFAULT 0;

UPDATE staff_department 
SET staff_level = CASE key
    WHEN 'bod'  THEN 1 
    WHEN 'dept' THEN 2 
    WHEN 'dev'  THEN 3 
    WHEN 'ad'   THEN 4
    WHEN 'cr'   THEN 5
    WHEN 'sys'  THEN 6
    WHEN 'qa'   THEN 7
    WHEN 'wiki' THEN 8
    WHEN 'cont' THEN 9 
    WHEN 'inst' THEN 10
END;
""",
    """
CREATE UNIQUE INDEX idx_staff_tags_unique_assignment ON staff_tags(staff_id, tag_id);
DELETE FROM staff_staff_department WHERE department_key='wiki';
DELETE FROM staff_department WHERE key='wiki';
""",
    """
CREATE UNIQUE INDEX idx_asset_tags_unique_name ON asset_tags(name);
""",
"""
CREATE TABLE department_systems_trainee_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    feedback TEXT NOT NULL,
    feedback_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (feedback_by) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE UNIQUE INDEX idx_dstf_staff_feedback_by
    ON department_systems_trainee_feedback (staff_id, feedback_by);
CREATE TRIGGER department_systems_trainee_feedback_edited_at
AFTER UPDATE ON department_systems_trainee_feedback
FOR EACH ROW WHEN NEW.edited_at IS OLD.edited_at
BEGIN
  UPDATE department_systems_trainee_feedback SET edited_at = CURRENT_TIMESTAMP WHERE staff_id = OLD.staff_id;
END;
""",

]
