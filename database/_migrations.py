MIGRATIONS: list[str] = [
    """
/* ===================== staff ===================== */

CREATE TABLE staff_staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT,
    timezone TEXT,
    schedule TEXT NOT NULL DEFAULT '{}',
    discord_id INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_blacklisted BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_department (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    head INTEGER NOT NULL,
    configuration TEXT NOT NULL DEFAULT '{}',
    servers TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (head) REFERENCES staff_staff (staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE staff_staff_department (
    staff_id INTEGER NOT NULL,
    department_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at INTEGER NOT NULL DEFAULT CURRENT_TIMESTAMP
);

/* ===================== department ===================== */

CREATE TABLE department_tester_reports (
    id INTEGER PRIMARY KEY,
    author INTEGER NOT NULL,
    content TEXT,
    decision INTEGER NOT NULL DEFAULT 0,
    severity INTEGER,
    triaged_by INTEGER,
    triaged_at INTEGER,
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

/* ===================== views ======================= */

/* ===================== triggers ===================== */
CREATE TRIGGER update_staff_staff_edited_at
AFTER UPDATE ON staff_staff FOR EACH ROW
BEGIN
  UPDATE staff_staff SET edited_at = CURRENT_TIMESTAMP WHERE staff_id = OLD.staff_id;
END;

CREATE TRIGGER update_staff_department_edited_at 
AFTER UPDATE ON staff_department
FOR EACH ROW
BEGIN
  UPDATE staff_department SET edited_at = CURRENT_TIMESTAMP WHERE key = OLD.key;
END;

CREATE TRIGGER update_department_tester_reports_edited_at 
AFTER UPDATE ON department_tester_reports
FOR EACH ROW
BEGIN
  UPDATE department_tester_reports SET edited_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER update_department_instructor_instructions_edited_at 
AFTER UPDATE ON department_instructor_instructions
FOR EACH ROW
BEGIN
  UPDATE department_instructor_instructions SET edited_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER update_department_tester_misc_performance_edited_at
AFTER UPDATE ON department_tester_misc_performance
FOR EACH ROW
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
    """
]
