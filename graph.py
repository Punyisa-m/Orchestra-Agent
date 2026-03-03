"""
graph.py  ·  Orchestra-Agent v2
=================================
LangGraph orchestration: 4 nodes wired into a linear StateGraph.

NODE FLOW:
  planner_node → matchmaker_node → scheduler_node → reporter_node

WHY LangGraph?
  Models the pipeline as an explicit, inspectable directed graph.
  Each node has one responsibility and returns an updated copy of the
  shared AgentState — making the flow easy to test, extend, and debug.
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, TypedDict, Any

from langgraph.graph import StateGraph, END

from database import (
    EmployeeWithSkills, Task,
    get_all_employees_with_skills,
    insert_task,
    update_employee_load,
)

# ──────────────────────────────────────────────────────────────────────────────
# LLM FACTORY
# ──────────────────────────────────────────────────────────────────────────────

def _build_llm():
    """
    Returns the LLM client.  Reads OPENAI_API_KEY from env;
    falls back to Ollama if the key is absent.
    """
    if os.getenv("OPENAI_API_KEY", "").strip():
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    from langchain_ollama import ChatOllama
    return ChatOllama(model="llama3.2", temperature=0.2)


# ──────────────────────────────────────────────────────────────────────────────
# STATE  (the message-bus between all nodes)
# ──────────────────────────────────────────────────────────────────────────────

class SubTask(TypedDict):
    title: str
    description: str
    required_skills: List[str]
    estimated_hours: float
    difficulty: str       # Low | Medium | High
    priority: str         # Low | Medium | High | Critical


class AssignedTask(TypedDict):
    subtask: SubTask
    assigned_employee_id: int
    assigned_employee_name: str
    match_score: float
    deadline: Optional[str]
    db_task_id: Optional[int]


class AgentState(TypedDict):
    user_request: str
    subtasks: List[SubTask]
    assigned_tasks: List[AssignedTask]
    final_report: str
    error: Optional[str]
    llm_raw_response: str


# ──────────────────────────────────────────────────────────────────────────────
# JSON REPAIR UTILITIES  (make Planner resilient to LLM formatting quirks)
# ──────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """
    Shared cleanup: strips fences, normalises Python literals,
    fixes single quotes, removes trailing commas.
    """
    text = re.sub(r"```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```",        "", text)
    text = re.sub(r"\bTrue\b",  "true",  text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b",  "null",  text)
    text = re.sub(r"(?<!\\)\'",  '"''"',     text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _merge_multiple_arrays(text: str) -> str:
    """
    Ollama sometimes outputs multiple arrays in a row or truncates mid-array.
    Strategy: harvest every {...} object and merge into one array.
    """
    objects = re.findall(r'\{[^{}]*\}', text, re.DOTALL)
    if not objects:
        raise ValueError("No JSON objects found in LLM output.")
    return "[" + ",".join(objects) + "]"


def _autoclose(text: str) -> str:
    """Append missing closing brackets/braces for truncated JSON."""
    close_map = {"{": "}", "[": "]"}
    stack: list = []
    in_str = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"''"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            stack.append(close_map[ch])
        elif ch in ("}", "]") and stack:
            stack.pop()
    text = re.sub(r",\s*$", "", text.rstrip())
    if in_str:
        text += '"'
    return text + "".join(reversed(stack))


def _repair_and_parse(raw: str) -> list:
    """
    Four-pass parser (least → most destructive repair):
      1. Normalize + direct json.loads on first complete [...] block
      2. Normalize + autoclose truncated output + json.loads
      3. Harvest all {...} objects anywhere in text and merge
      4. ast.literal_eval as last resort
    Covers: fences, prose, trailing commas, truncation, multiple arrays.
    """
    normalized = _normalize(raw)
    start = normalized.find("[")
    end   = normalized.rfind("]")

    # Pass 1 — straight parse
    if start != -1 and end > start:
        try:
            return json.loads(normalized[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Pass 2 — autoclose truncated JSON
    if start != -1:
        try:
            closed = _autoclose(normalized[start:])
            result = json.loads(closed)
            if isinstance(result, list):
                return result
        except Exception:
            pass

    # Pass 3 — merge all objects found anywhere
    try:
        return json.loads(_merge_multiple_arrays(normalized))
    except Exception:
        pass

    # Pass 3b — trim to last complete key-value pair then autoclose
    # Handles deeply truncated output like: [{"title":"X","req
    if start != -1:
        try:
            chunk = normalized[start:]
            # Trim back to last complete field (last ," or ,:)
            last_comma = max(chunk.rfind(',"'), chunk.rfind(', "'))
            if last_comma > 0:
                trimmed = _autoclose(chunk[:last_comma])
                result = json.loads(trimmed)
                if isinstance(result, list) and result:
                    return result
        except Exception:
            pass

    # Pass 4 — ast fallback
    if start != -1 and end > start:
        try:
            import ast
            return ast.literal_eval(normalized[start : end + 1])
        except Exception:
            pass

    raise ValueError(
        f"Failed to parse LLM output after all repair attempts.\n"
        f"Snippet: {raw[:500]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# NODE 1 — PLANNER
# ──────────────────────────────────────────────────────────────────────────────

_PRIORITY_MAP = {
    "low":    "Low",
    "medium": "Medium",
    "high":   "High",
    "critical": "Critical",
}

def planner_node(state: AgentState) -> AgentState:
    """
    Converts a natural-language goal into 3-5 atomic sub-tasks.
    This is the ONLY node that calls the LLM — all other nodes use
    pure math to keep the pipeline deterministic and auditable.
    """
    llm = _build_llm()

    prompt = f"""You are a senior software project manager. Output ONLY a JSON array.

GOAL: "{state['user_request']}"

Break it into 3-5 atomic sub-tasks. Each object must have exactly these keys:
  "title"           – short task name (string)
  "description"     – one clear sentence (string)
  "required_skills" – array of 1-3 strings chosen ONLY from:
      [Python, React, TypeScript, CSS, Figma, FastAPI, Django, PostgreSQL,
       SQL, Docker, Kubernetes, CI/CD, Terraform, Machine Learning, Pytest,
       Selenium, Accessibility]
  "estimated_hours" – realistic number between 0.5 and 16
  "difficulty"      – exactly one of: "Low", "Medium", "High"
  "priority"        – exactly one of: "Low", "Medium", "High", "Critical"

START WITH [ AND END WITH ]. NO prose. NO markdown fences. NO trailing commas.

BEGIN:"""

    try:
        raw      = llm.invoke(prompt).content.strip()
        parsed   = _repair_and_parse(raw)

        ALLOWED = {
            "python","react","typescript","css","figma","fastapi","django",
            "postgresql","sql","docker","kubernetes","ci/cd","terraform",
            "machine learning","pytest","selenium","accessibility",
        }

        valid: List[SubTask] = []
        for item in parsed:
            if not isinstance(item, dict) or "title" not in item:
                continue
            skills = item.get("required_skills", [])
            if isinstance(skills, str):
                skills = [skills]
            filtered = [s for s in skills if s.lower() in ALLOWED]
            item["required_skills"] = filtered or skills[:3]
            item["estimated_hours"] = float(item.get("estimated_hours", 2.0))
            item["difficulty"]      = item.get("difficulty", "Medium")
            item["priority"]        = _PRIORITY_MAP.get(
                str(item.get("priority","Medium")).lower(), "Medium")
            item.setdefault("description", item["title"])
            valid.append(item)   # type: ignore[arg-type]

        if not valid:
            raise ValueError("No valid sub-tasks found in LLM output.")

        return {**state, "subtasks": valid, "llm_raw_response": raw}

    except Exception as e:
        return {**state, "error": f"Planner failed: {e}", "subtasks": []}


# ──────────────────────────────────────────────────────────────────────────────
# NODE 2 — MATCHMAKER  (pure math — zero LLM, zero bias)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_match_score(
    candidate: EmployeeWithSkills,
    required_skills: List[str],
) -> float:
    """
    Skill-to-Workload ratio score (0–1).

    FORMULA:
        skill_score = mean proficiency of required skills present (0–10)
        coverage    = fraction of required skills covered (0–1)
        load_frac   = current_load / 100

        score = (skill_score/10 × 0.5 + coverage × 0.3) × (1 − load_frac × 0.4)

    WHY this formula?
      - Skill score rewards genuine expertise.
      - Coverage penalises partial skill overlap.
      - Load penalty (40 % weight) favours available employees without
        fully blocking busy ones — enforcing fairness without a hard cap.
      - No human override, no LLM opinion → strictly data-driven.
    """
    skill_map = {s.skill_name.lower(): s.proficiency_score
                 for s in candidate.skills}

    matched  = [skill_map.get(r.lower(), 0) for r in required_skills]
    if not matched:
        return 0.0

    skill_avg  = sum(matched) / len(matched)
    coverage   = sum(1 for s in matched if s > 0) / len(matched)
    load_frac  = candidate.employee.current_load / 100.0

    raw = skill_avg / 10 * 0.5 + coverage * 0.3
    return round(raw * (1 - load_frac * 0.4), 4)


def matchmaker_node(state: AgentState) -> AgentState:
    """
    For each sub-task, scores every employee and assigns the top candidate.
    Employee loads are updated immediately after each assignment so that
    subsequent tasks in the same session see the current load — preventing
    a single person from absorbing the entire project.
    """
    if state.get("error") or not state.get("subtasks"):
        return state

    assigned: List[AssignedTask] = []

    for subtask in state["subtasks"]:
        candidates = get_all_employees_with_skills()
        scored = sorted(
            candidates,
            key=lambda c: _compute_match_score(c, subtask["required_skills"]),
            reverse=True,
        )
        best = scored[0]
        best.match_score = _compute_match_score(best, subtask["required_skills"])
        update_employee_load(best.employee.id, subtask["estimated_hours"])

        assigned.append(AssignedTask(
            subtask=subtask,
            assigned_employee_id=best.employee.id,
            assigned_employee_name=best.employee.name,
            match_score=best.match_score,
            deadline=None,
            db_task_id=None,
        ))

    return {**state, "assigned_tasks": assigned}


# ──────────────────────────────────────────────────────────────────────────────
# NODE 3 — SCHEDULER
# ──────────────────────────────────────────────────────────────────────────────

_BUFFER = {"Low": 1.0, "Medium": 1.25, "High": 1.5}
_HOURS_PER_DAY = 6.0

def scheduler_node(state: AgentState) -> AgentState:
    """
    Chains deadlines per employee: task N starts only after task N-1 finishes.
    A difficulty buffer multiplier is applied to cushion estimation errors.
    """
    if state.get("error") or not state.get("assigned_tasks"):
        return state

    base_date: datetime = datetime.now()
    next_free: dict[int, datetime] = {}
    updated: List[AssignedTask] = []

    for at in state["assigned_tasks"]:
        emp_id   = at["assigned_employee_id"]
        hours    = at["subtask"]["estimated_hours"]
        diff     = at["subtask"].get("difficulty", "Medium")
        buffered = hours * _BUFFER.get(diff, 1.0)

        start    = next_free.get(emp_id, base_date)
        deadline = start + timedelta(days=buffered / _HOURS_PER_DAY)
        next_free[emp_id] = deadline

        updated.append({**at, "deadline": deadline.strftime("%Y-%m-%d")})  # type: ignore[misc]

    return {**state, "assigned_tasks": updated}


# ──────────────────────────────────────────────────────────────────────────────
# NODE 4 — REPORTER
# ──────────────────────────────────────────────────────────────────────────────

def reporter_node(state: AgentState) -> AgentState:
    """
    Persists all tasks to SQLite and builds a Markdown summary.
    WHY write here and not in Matchmaker?
      We only write after the Scheduler has computed deadlines, so every
      row lands in the DB complete — no partial / dirty records.
    """
    if state.get("error") or not state.get("assigned_tasks"):
        return {**state, "final_report": "No tasks to report."}

    lines = [
        f"# Project Plan\n",
        f"**Goal:** {state['user_request']}  \n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n",
        "---\n",
    ]

    for i, at in enumerate(state["assigned_tasks"], 1):
        sub   = at["subtask"]
        task  = Task(
            title=sub["title"],
            description=sub["description"],
            assigned_to=at["assigned_employee_id"],
            assigned_name=at["assigned_employee_name"],
            estimated_hours=sub["estimated_hours"],
            priority=sub.get("priority", "Medium"),
            status="To-Do",
            deadline=at["deadline"],
        )
        db_id = insert_task(task)
        at["db_task_id"] = db_id  # type: ignore[typeddict-unknown-key]

        lines.append(
            f"### {i}. {sub['title']}  *(id: {db_id})*\n"
            f"- **Assigned:** {at['assigned_employee_name']}\n"
            f"- **Skills:** {', '.join(sub['required_skills'])}\n"
            f"- **Hours:** {sub['estimated_hours']}h  "
            f"**Priority:** {sub.get('priority','Medium')}  "
            f"**Difficulty:** {sub.get('difficulty','Medium')}\n"
            f"- **Deadline:** {at['deadline']}  "
            f"**Match score:** {at['match_score']:.3f}\n"
        )

    return {**state, "final_report": "\n".join(lines)}


# ──────────────────────────────────────────────────────────────────────────────
# GRAPH ASSEMBLY
# ──────────────────────────────────────────────────────────────────────────────

def build_graph() -> Any:
    wf = StateGraph(AgentState)
    wf.add_node("planner",    planner_node)
    wf.add_node("matchmaker", matchmaker_node)
    wf.add_node("scheduler",  scheduler_node)
    wf.add_node("reporter",   reporter_node)
    wf.set_entry_point("planner")
    wf.add_edge("planner",    "matchmaker")
    wf.add_edge("matchmaker", "scheduler")
    wf.add_edge("scheduler",  "reporter")
    wf.add_edge("reporter",   END)
    return wf.compile()


def run_orchestra(user_request: str) -> AgentState:
    """Public entry point called by the Streamlit app."""
    graph = build_graph()
    return graph.invoke(AgentState(
        user_request=user_request,
        subtasks=[],
        assigned_tasks=[],
        final_report="",
        error=None,
        llm_raw_response="",
    ))