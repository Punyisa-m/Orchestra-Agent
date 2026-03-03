"""
database.py  ·  Orchestra-Agent v2
====================================
Data layer: SQLite schema, Pydantic contracts, and all query helpers.

WHY SQLite?
  Zero-config, single-file, ships inside the project folder.
  The connection helper uses row_factory=sqlite3.Row so every
  column is addressable by name — no brittle index math.

WHY Pydantic models here?
  They act as the typed contract between the DB and LangGraph nodes.
  Every node receives a validated object, never a raw dict, which
  prevents silent type-coercion bugs at runtime.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

DB_PATH = os.path.join(os.path.dirname(__file__), "orchestra.db")

# ──────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS  (typed contracts flowing between nodes)
# ──────────────────────────────────────────────────────────────────────────────

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
    match_score: float = 0.0          # computed by Matchmaker, not stored


class Task(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    estimated_hours: float = 1.0
    actual_hours: Optional[float] = None
    priority: str = "Medium"          # Low | Medium | High | Critical
    status: str = "To-Do"             # To-Do | In Progress | Done
    deadline: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ──────────────────────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# INIT + SEED
# ──────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Idempotent — safe to call on every startup."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            department   TEXT    NOT NULL,
            current_load REAL    NOT NULL DEFAULT 0
                       CHECK(current_load BETWEEN 0 AND 100)
        );

        CREATE TABLE IF NOT EXISTS skills (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id       INTEGER NOT NULL REFERENCES employees(id),
            skill_name        TEXT    NOT NULL,
            proficiency_score INTEGER NOT NULL
                             CHECK(proficiency_score BETWEEN 1 AND 10)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            assigned_to     INTEGER REFERENCES employees(id),
            estimated_hours REAL    NOT NULL DEFAULT 1.0,
            actual_hours    REAL,
            priority        TEXT    NOT NULL DEFAULT 'Medium'
                            CHECK(priority IN ('Low','Medium','High','Critical')),
            status          TEXT    NOT NULL DEFAULT 'To-Do'
                            CHECK(status IN ('To-Do','In Progress','Done')),
            deadline        TEXT,
            created_at      TEXT    NOT NULL
        );
    """)

    if cur.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        _seed(cur)

    conn.commit()
    conn.close()


def _seed(cur: sqlite3.Cursor) -> None:
    """8-person cross-functional team with intentionally varied loads."""
    employees = [
        ("Alice Chen",    "Engineering",  30),
        ("Bob Martinez",  "Engineering",  75),
        ("Carol White",   "Design",       20),
        ("David Kim",     "Engineering",  50),
        ("Eva Patel",     "QA",           40),
        ("Frank Osei",    "DevOps",       65),
        ("Grace Liu",     "Engineering",  15),
        ("Hamid Raza",    "Design",       85),
    ]
    cur.executemany(
        "INSERT INTO employees (name, department, current_load) VALUES (?,?,?)",
        employees,
    )

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
    cur.executemany(
        "INSERT INTO skills (employee_id, skill_name, proficiency_score) VALUES (?,?,?)",
        skills,
    )


# ──────────────────────────────────────────────────────────────────────────────
# QUERIES  (called by LangGraph nodes + Streamlit UI)
# ──────────────────────────────────────────────────────────────────────────────

def get_all_employees_with_skills() -> List[EmployeeWithSkills]:
    """Full candidate pool for the Matchmaker node."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM employees").fetchall()
    result = []
    for r in rows:
        emp    = Employee(**dict(r))
        skills = [Skill(**dict(s)) for s in
                  conn.execute("SELECT * FROM skills WHERE employee_id=?",
                               (emp.id,)).fetchall()]
        result.append(EmployeeWithSkills(employee=emp, skills=skills))
    conn.close()
    return result


def insert_task(task: Task) -> int:
    """Persist a Task and return its new DB id."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO tasks
            (title, description, assigned_to, estimated_hours,
             actual_hours, priority, status, deadline, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (task.title, task.description, task.assigned_to,
          task.estimated_hours, task.actual_hours,
          task.priority, task.status, task.deadline, task.created_at))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_all_tasks() -> List[dict]:
    """All tasks with the assigned employee's name (LEFT JOIN)."""
    conn  = get_connection()
    rows  = conn.execute("""
        SELECT t.*, e.name AS assigned_name, e.department
        FROM   tasks t
        LEFT JOIN employees e ON t.assigned_to = e.id
        ORDER BY t.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_employee_load(employee_id: int, additional_hours: float) -> None:
    """
    Increment load after assignment so subsequent tasks see the live value.
    WHY update immediately? Prevents pile-on within a single planning session.
    """
    conn = get_connection()
    conn.execute("""
        UPDATE employees
        SET    current_load = MIN(100, current_load + ?)
        WHERE  id = ?
    """, (additional_hours * 2.5, employee_id))
    conn.commit()
    conn.close()


def update_task_status(task_id: int, new_status: str) -> None:
    """Move a Kanban card between columns."""
    conn = get_connection()
    conn.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
    conn.commit()
    conn.close()


def get_workload_distribution() -> List[dict]:
    """Per-employee stats for the analytics chart."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.name, e.department, e.current_load,
               COUNT(t.id)                           AS task_count,
               COALESCE(SUM(t.estimated_hours), 0)  AS total_hours
        FROM   employees e
        LEFT JOIN tasks t ON t.assigned_to = e.id AND t.status != 'Done'
        GROUP BY e.id
        ORDER BY e.current_load DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def simulate_actual_hours() -> None:
    """Add ±25 % variance to estimated hours for analytics demo."""
    import random
    conn = get_connection()
    for t in conn.execute(
            "SELECT id, estimated_hours FROM tasks WHERE actual_hours IS NULL"
    ).fetchall():
        conn.execute("UPDATE tasks SET actual_hours=? WHERE id=?",
                     (round(t["estimated_hours"] * random.uniform(0.75, 1.25), 2),
                      t["id"]))
    conn.commit()
    conn.close()


def reset_demo_data() -> None:
    """Wipe all tasks and partially restore employee loads."""
    conn = get_connection()
    conn.execute("DELETE FROM tasks")
    conn.execute("UPDATE employees SET current_load = current_load * 0.25")
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# EMPLOYEE-SPECIFIC QUERIES  (used by the Employee Dashboard page)
# ──────────────────────────────────────────────────────────────────────────────

def get_all_employees() -> List[dict]:
    """Return all employees as plain dicts for the selector UI."""
    conn  = get_connection()
    rows  = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tasks_for_employee(employee_id: int) -> List[dict]:
    """
    Fetch all tasks assigned to a specific employee only.
    WHY separate? Employee page must NEVER see other people's tasks —
    enforcing data isolation without a real auth layer.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, e.name AS assigned_name, e.department
        FROM   tasks t
        JOIN   employees e ON t.assigned_to = e.id
        WHERE  t.assigned_to = ?
        ORDER BY
            CASE t.status
                WHEN 'In Progress' THEN 1
                WHEN 'To-Do'       THEN 2
                WHEN 'Done'        THEN 3
            END,
            t.deadline ASC
    """, (employee_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_task_actual_hours(task_id: int, actual_hours: float) -> None:
    """Employee logs how long a task actually took."""
    conn = get_connection()
    conn.execute("UPDATE tasks SET actual_hours=? WHERE id=?",
                 (actual_hours, task_id))
    conn.commit()
    conn.close()


def get_employee_stats(employee_id: int) -> dict:
    """Aggregated stats for one employee's personal dashboard header."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT status,
               COUNT(*)                          AS cnt,
               COALESCE(SUM(estimated_hours), 0) AS est_h,
               COALESCE(SUM(actual_hours),    0) AS act_h
        FROM   tasks
        WHERE  assigned_to = ?
        GROUP BY status
    """, (employee_id,)).fetchall()
    conn.close()
    stats = {"To-Do": 0, "In Progress": 0, "Done": 0,
             "est_hours": 0.0, "act_hours": 0.0}
    for r in rows:
        stats[r["status"]] = r["cnt"]
        stats["est_hours"] += r["est_h"]
        stats["act_hours"] += r["act_h"]
    stats["total"] = stats["To-Do"] + stats["In Progress"] + stats["Done"]
    return stats


def get_upcoming_tasks(employee_id: int, days: int = 7) -> List[dict]:
    """Tasks due within the next N days for this employee."""
    from datetime import datetime, timedelta
    today  = datetime.now().date()
    cutoff = (today + timedelta(days=days)).isoformat()
    conn   = get_connection()
    rows   = conn.execute("""
        SELECT * FROM tasks
        WHERE  assigned_to = ?
          AND  deadline IS NOT NULL
          AND  deadline <= ?
          AND  status != 'Done'
        ORDER BY deadline ASC
    """, (employee_id, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]