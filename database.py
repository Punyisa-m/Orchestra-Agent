"""
database.py  ·  Orchestra-Agent  ·  Production Edition
========================================================
Connection management rule:
  EVERY function opens a connection, does its work, and closes it
  in a try/finally block — guaranteed close even on exception.

  WHY NOT `with conn:`?
    sqlite3.Connection.__exit__ only commits/rolls back — it does NOT
    close the connection. Using it as a sole context manager leaks handles,
    which causes "database is locked" on Streamlit re-runs.

  CORRECT pattern used here:
    conn = get_connection()
    try:
        ...
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()          ← always executes
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Generator
from pydantic import BaseModel, Field

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_DATA_DIR, "orchestra.db")


# ── Pydantic models ────────────────────────────────────────────────────────────

class Employee(BaseModel):
    id: int
    name: str
    department: str
    current_load: float = Field(ge=0, le=100)

class Skill(BaseModel):
    id: int
    employee_id: int
    skill_name: str
    proficiency_score: int = Field(ge=1, le=10)

class EmployeeWithSkills(BaseModel):
    employee: Employee
    skills: List[Skill]
    match_score: float = 0.0

class Task(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    estimated_hours: float = 1.0
    actual_hours: Optional[float] = None
    priority: str = "Medium"
    status: str = "To-Do"
    deadline: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys  = ON")
    conn.execute("PRAGMA journal_mode  = WAL")
    conn.execute("PRAGMA busy_timeout  = 30000")
    return conn


# ── Schema init ────────────────────────────────────────────────────────────────

def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL UNIQUE,
                department   TEXT    NOT NULL,
                current_load REAL    NOT NULL DEFAULT 0
                           CHECK(current_load BETWEEN 0 AND 100)
            );
            CREATE TABLE IF NOT EXISTS skills (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id       INTEGER NOT NULL REFERENCES employees(id)
                                  ON DELETE CASCADE,
                skill_name        TEXT    NOT NULL,
                proficiency_score INTEGER NOT NULL
                                 CHECK(proficiency_score BETWEEN 1 AND 10)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT    NOT NULL,
                description     TEXT    NOT NULL,
                assigned_to     INTEGER REFERENCES employees(id)
                                ON DELETE SET NULL,
                estimated_hours REAL    NOT NULL DEFAULT 1.0,
                actual_hours    REAL,
                priority        TEXT    NOT NULL DEFAULT 'Medium'
                                CHECK(priority IN ('Low','Medium','High','Critical')),
                status          TEXT    NOT NULL DEFAULT 'To-Do'
                                CHECK(status IN ('To-Do','In Progress','Done')),
                deadline        TEXT,
                created_at      TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
            CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_skills_emp     ON skills(employee_id);
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT    NOT NULL,
                display_name  TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'employee'
                              CHECK(role IN ('admin','manager','employee')),
                employee_id   INTEGER REFERENCES employees(id) ON DELETE SET NULL,
                created_at    TEXT    NOT NULL,
                last_login    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """)
        _migrate_schema(conn)
        if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            _seed_demo(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """
    Additive migrations — safe to run on old databases, idempotent.
    Runs on EVERY startup inside init_db(), so every fix here
    is applied automatically the next time the app starts.
    """
    # M1: Unique index on skills
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_skills_emp_name ON skills(employee_id, skill_name)
    """)

    # M2: users table — add it if the old DB doesn't have it yet
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT    NOT NULL,
            display_name  TEXT    NOT NULL,
            role          TEXT    NOT NULL DEFAULT 'employee'
                          CHECK(role IN ('admin','manager','employee')),
            employee_id   INTEGER REFERENCES employees(id) ON DELETE SET NULL,
            created_at    TEXT    NOT NULL,
            last_login    TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
    """)

    # M3: seed default accounts if users table is empty
    # This handles old DBs that already have employee data
    # (so _seed_demo never ran) but have no user accounts yet.
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        _seed_users(conn)


def _seed_demo(conn: sqlite3.Connection) -> None:
    emps = [
        ("Alice Chen","Engineering",30), ("Bob Martinez","Engineering",75),
        ("Carol White","Design",20),     ("David Kim","Engineering",50),
        ("Eva Patel","QA",40),           ("Frank Osei","DevOps",65),
        ("Grace Liu","Engineering",15),  ("Hamid Raza","Design",85),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO employees (name,department,current_load) VALUES(?,?,?)", emps)
    skills = [
        (1,"Python",8),(1,"React",7),(1,"FastAPI",9),(1,"PostgreSQL",7),
        (2,"Python",9),(2,"Django",8),(2,"PostgreSQL",9),(2,"Docker",6),
        (3,"Figma",10),(3,"CSS",9),(3,"React",6),(3,"Accessibility",8),
        (4,"Python",9),(4,"Machine Learning",8),(4,"SQL",7),(4,"FastAPI",6),
        (5,"Pytest",9),(5,"Selenium",8),(5,"CI/CD",7),(5,"Python",6),
        (6,"Docker",10),(6,"Kubernetes",8),(6,"CI/CD",9),(6,"Terraform",7),
        (7,"React",9),(7,"TypeScript",9),(7,"CSS",8),(7,"Figma",5),
        (8,"Figma",9),(8,"CSS",8),(8,"Accessibility",7),(8,"React",5),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO skills (employee_id,skill_name,proficiency_score) VALUES(?,?,?)",
        skills)
    _seed_users(conn)


def _seed_users(conn: sqlite3.Connection) -> None:
    """
    Default accounts for first launch.
    CHANGE THESE PASSWORDS immediately in production via the Admin page.
    admin / admin123  → full access
    manager / mgr123  → manager dashboard
    """
    from auth import hash_password
    defaults = [
        ("admin",   hash_password("admin123"),   "Administrator", "admin",    None),
        ("manager", hash_password("mgr123"),     "Team Manager",  "manager",  None),
    ]
    now = datetime.now().isoformat()
    for username, pw_hash, display, role, emp_id in defaults:
        conn.execute("""
            INSERT OR IGNORE INTO users
              (username,password_hash,display_name,role,employee_id,created_at)
            VALUES (?,?,?,?,?,?)
        """, (username, pw_hash, display, role, emp_id, now))


# ── Generators (memory-efficient reads) ───────────────────────────────────────

def iter_tasks(
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
    batch_size: int = 50,
) -> Generator[dict, None, None]:
    conn   = get_connection()
    where, params = [], []
    if status:      where.append("t.status = ?");      params.append(status)
    if employee_id: where.append("t.assigned_to = ?"); params.append(employee_id)
    sql = """
        SELECT t.*, e.name AS assigned_name, e.department
        FROM   tasks t LEFT JOIN employees e ON t.assigned_to = e.id
        {w} ORDER BY t.created_at DESC
    """.format(w=("WHERE " + " AND ".join(where)) if where else "")
    try:
        cur = conn.execute(sql, params)
        while True:
            batch = cur.fetchmany(batch_size)
            if not batch: break
            for row in batch: yield dict(row)
    finally:
        conn.close()


def iter_employees() -> Generator[dict, None, None]:
    conn = get_connection()
    try:
        for row in conn.execute("SELECT * FROM employees ORDER BY name"):
            yield dict(row)
    finally:
        conn.close()


# ── Standard list queries ──────────────────────────────────────────────────────

def get_all_tasks()             -> List[dict]: return list(iter_tasks())
def get_all_employees()         -> List[dict]: return list(iter_employees())
def get_tasks_for_employee(eid) -> List[dict]: return list(iter_tasks(employee_id=eid))

def get_all_employees_with_skills() -> List[EmployeeWithSkills]:
    conn = get_connection()
    try:
        result = []
        for r in conn.execute("SELECT * FROM employees").fetchall():
            emp    = Employee(**dict(r))
            skills = [Skill(**dict(s)) for s in
                      conn.execute("SELECT * FROM skills WHERE employee_id=?",
                                   (emp.id,)).fetchall()]
            result.append(EmployeeWithSkills(employee=emp, skills=skills))
        return result
    finally:
        conn.close()

def get_skills_for_employee(eid: int) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM skills WHERE employee_id=? ORDER BY skill_name", (eid,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_workload_distribution() -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT e.name, e.department, e.current_load,
                   COUNT(t.id) AS task_count,
                   COALESCE(SUM(t.estimated_hours),0) AS total_hours
            FROM employees e
            LEFT JOIN tasks t ON t.assigned_to=e.id AND t.status!='Done'
            GROUP BY e.id ORDER BY e.current_load DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_employee_stats(eid: int) -> dict:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt,
                   COALESCE(SUM(estimated_hours),0) AS est_h,
                   COALESCE(SUM(actual_hours),0)    AS act_h
            FROM tasks WHERE assigned_to=? GROUP BY status
        """, (eid,)).fetchall()
        s = {"To-Do":0,"In Progress":0,"Done":0,"est_hours":0.0,"act_hours":0.0}
        for r in rows:
            s[r["status"]] = r["cnt"]
            s["est_hours"] += r["est_h"]; s["act_hours"] += r["act_h"]
        s["total"] = s["To-Do"] + s["In Progress"] + s["Done"]
        return s
    finally:
        conn.close()

def get_upcoming_tasks(eid: int, days: int = 7) -> List[dict]:
    cutoff = (datetime.now().date() + timedelta(days=days)).isoformat()
    conn   = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM tasks WHERE assigned_to=?
              AND deadline IS NOT NULL AND deadline<=? AND status!='Done'
            ORDER BY deadline ASC
        """, (eid, cutoff)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_db_stats() -> dict:
    conn = get_connection()
    try:
        return {
            "employees": conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0],
            "skills":    conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
            "tasks":     conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
            "pending":   conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='To-Do'").fetchone()[0],
        }
    finally:
        conn.close()


# ── Employee CRUD ──────────────────────────────────────────────────────────────

def create_employee(name: str, department: str, load: float = 0.0) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO employees (name,department,current_load) VALUES(?,?,?)",
            (name.strip(), department.strip(), load))
        conn.commit()
        return cur.lastrowid
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def update_employee(eid: int, name: str, department: str, load: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE employees SET name=?,department=?,current_load=? WHERE id=?",
            (name.strip(), department.strip(), load, eid))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def delete_employee(eid: int) -> None:
    """
    Deletes an employee safely on ANY schema version.

    WHY isolation_level=None?
      PRAGMA foreign_keys = OFF is silently ignored inside an active
      transaction in SQLite. We need autocommit mode so the PRAGMA
      takes effect immediately before we start our manual steps.
    """
    # Open in autocommit mode so PRAGMA takes effect outside a transaction
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = OFF")   # must be outside transaction
        conn.execute("BEGIN")
        conn.execute("UPDATE tasks   SET assigned_to  = NULL WHERE assigned_to  = ?", (eid,))
        conn.execute("UPDATE users   SET employee_id  = NULL WHERE employee_id  = ?", (eid,))
        conn.execute("DELETE FROM employees WHERE id = ?", (eid,))
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        try: conn.execute("ROLLBACK")
        except Exception: pass
        raise
    finally:
        conn.close()


# ── Skill CRUD ─────────────────────────────────────────────────────────────────

def upsert_skill(eid: int, skill_name: str, score: int) -> None:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM skills WHERE employee_id=? AND skill_name=?",
            (eid, skill_name.strip())).fetchone()
        if existing:
            conn.execute("UPDATE skills SET proficiency_score=? WHERE id=?",
                         (score, existing["id"]))
        else:
            conn.execute(
                "INSERT INTO skills (employee_id,skill_name,proficiency_score) VALUES(?,?,?)",
                (eid, skill_name.strip(), score))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def delete_skill(skill_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()


# ── Task writes ────────────────────────────────────────────────────────────────

def insert_task(task: Task) -> int:
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO tasks
              (title,description,assigned_to,estimated_hours,actual_hours,
               priority,status,deadline,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (task.title, task.description, task.assigned_to, task.estimated_hours,
              task.actual_hours, task.priority, task.status, task.deadline, task.created_at))
        conn.commit()
        return cur.lastrowid
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def update_task_status(tid: int, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def update_task_actual_hours(tid: int, hours: float) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE tasks SET actual_hours=? WHERE id=?", (hours, tid))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def delete_task(tid: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def update_employee_load(eid: int, additional_hours: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE employees SET current_load=MIN(100,current_load+?) WHERE id=?",
            (additional_hours * 2.5, eid))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def simulate_actual_hours() -> None:
    import random
    conn = get_connection()
    try:
        for t in conn.execute(
            "SELECT id,estimated_hours FROM tasks WHERE actual_hours IS NULL"
        ).fetchall():
            conn.execute("UPDATE tasks SET actual_hours=? WHERE id=?",
                         (round(t["estimated_hours"]*random.uniform(0.75,1.25),2), t["id"]))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def reset_demo_data() -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tasks")
        conn.execute("UPDATE employees SET current_load=current_load*0.25")
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# USER AUTH QUERIES
# ══════════════════════════════════════════════════════════════════════════════

def get_user_by_username(username: str) -> Optional[dict]:
    """Case-insensitive lookup — COLLATE NOCASE handles it in SQL."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username.strip(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def record_login(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET last_login=? WHERE id=?",
                     (datetime.now().isoformat(), user_id))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()


def get_all_users() -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT u.*, e.name AS employee_name
            FROM users u
            LEFT JOIN employees e ON u.employee_id = e.id
            ORDER BY u.role, u.username
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_user(username: str, password_hash: str, display_name: str,
                role: str, employee_id: Optional[int] = None) -> int:
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO users (username,password_hash,display_name,role,employee_id,created_at)
            VALUES (?,?,?,?,?,?)
        """, (username.strip(), password_hash, display_name.strip(),
              role, employee_id, datetime.now().isoformat()))
        conn.commit()
        return cur.lastrowid
    except:
        conn.rollback(); raise
    finally:
        conn.close()


def update_user_password(user_id: int, new_hash: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (new_hash, user_id))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()


def update_user(user_id: int, display_name: str, role: str,
                employee_id: Optional[int]) -> None:
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE users SET display_name=?, role=?, employee_id=? WHERE id=?
        """, (display_name.strip(), role, employee_id, user_id))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()