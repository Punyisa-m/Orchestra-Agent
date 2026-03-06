"""
graph.py  ·  Orchestra-Agent  ·  Hybrid LLM Edition
=====================================================
ENGINE PRIORITY (resolved at call-time, not import-time):

  1. Gemini 1.5 Flash  — if GOOGLE_API_KEY is set
                         Primary for Cloud / HF Spaces (free quota generous)
  2. OpenAI GPT-4o-mini — if OPENAI_API_KEY is set
                         Fallback for Cloud or local power users
  3. Ollama Llama 3.2  — if OLLAMA_HOST is set
                         Local-only, zero API cost

WHY resolve at call-time?
  The user can paste a key into the Streamlit sidebar mid-session.
  If we resolved at import time we'd need a full restart to pick it up.

WHY Gemini first?
  On HF Spaces the free-tier quota (60 req/min) is enough for demo use,
  and langchain-google-genai is lighter than langchain-openai on cold-start.

SECRETS GUIDE (prevents 401 errors):
  Local:        set GOOGLE_API_KEY / OPENAI_API_KEY in your .env file
  Docker:       inject via docker-compose environment: or --env-file
  HF Spaces:    Settings → Variables and secrets → "New secret"
                NEVER commit keys to git — they are redacted by HF anyway
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
# ENVIRONMENT DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def _is_huggingface() -> bool:
    """
    HF Spaces injects SPACE_ID automatically — reliable detection signal.
    Also catches HF_SPACE_ID (older env name) and explicit DEPLOY_ENV.
    """
    return bool(
        os.getenv("SPACE_ID") or
        os.getenv("HF_SPACE_ID") or
        os.getenv("DEPLOY_ENV", "").lower() == "huggingface"
    )


def get_available_engines() -> dict:
    """
    Returns a dict describing which engines are available RIGHT NOW.
    Called by the Streamlit sidebar to build the radio options dynamically.

    Returns:
        {
            "gemini":  bool,
            "openai":  bool,
            "ollama":  bool,
            "default": "gemini" | "openai" | "ollama" | None,
            "on_hf":   bool,   # True when running on Hugging Face
        }
    """
    on_hf   = _is_huggingface()
    gemini  = bool(os.getenv("GOOGLE_API_KEY",  "").strip())
    openai  = bool(os.getenv("OPENAI_API_KEY",  "").strip())
    groq    = bool(os.getenv("GROQ_API_KEY",    "").strip())
    # Ollama hidden on HF — never available in cloud
    ollama  = bool(os.getenv("OLLAMA_HOST", "").strip()) and not on_hf

    # Priority: Gemini → Groq → OpenAI → Ollama
    # (Groq beats OpenAI because it's free + faster + 14k req/day on 8b)
    if gemini:       default = "gemini"
    elif groq:       default = "groq"
    elif openai:     default = "openai"
    elif ollama:     default = "ollama"
    else:            default = None

    return {
        "gemini":  gemini,
        "groq":    groq,
        "openai":  openai,
        "ollama":  ollama,
        "default": default,
        "on_hf":   on_hf,
    }


# ──────────────────────────────────────────────────────────────────────────────
# LLM FACTORY
# ──────────────────────────────────────────────────────────────────────────────

def _build_llm(engine: Optional[str] = None):
    """
    Instantiate an LLM client.

    Args:
        engine: "gemini" | "openai" | "ollama" | None (auto-detect)

    Engine resolution when engine=None:
        1. Gemini 1.5 Flash   (GOOGLE_API_KEY present)
        2. OpenAI GPT-4o-mini (OPENAI_API_KEY present)
        3. Ollama Llama 3.2   (OLLAMA_HOST present, local only)
        raises RuntimeError if nothing is configured

    WHY lazy import inside the function?
        Each LangChain provider package has non-trivial import cost.
        Importing all three at module level would slow cold-start on HF
        even when the user only ever uses Gemini.
    """
    # ── Auto-detect if caller didn't specify ──────────────────────────────────
    if engine is None:
        env = get_available_engines()
        engine = env["default"]

    if engine is None:
        raise RuntimeError(
            "No LLM configured. Set GOOGLE_API_KEY (recommended), "
            "OPENAI_API_KEY, or OLLAMA_HOST in your environment."
        )

    # ── Gemini 1.5 Flash ──────────────────────────────────────────────────────
    if engine == "gemini":
        key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "GOOGLE_API_KEY is empty. "
                "On HF Spaces: Settings → Secrets → GOOGLE_API_KEY. "
                "Locally: add GOOGLE_API_KEY=... to your .env file."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",          # stable, fast, free tier
            google_api_key=key,
            temperature=0.2,
        )

    # ── Groq — Llama 3.1 8B (free, 14,400 req/day) ───────────────────────────
    # WHY Groq over direct Ollama cloud?
    #   Groq runs models on custom LPU hardware — inference is ~10x faster
    #   than GPU. Free tier: llama-3.1-8b-instant = 14,400 req/day, 131k TPM.
    #   Get key: https://console.groq.com/keys
    if engine == "groq":
        key = os.getenv("GROQ_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is empty. "
                "Get a free key at console.groq.com/keys — no credit card needed."
            )
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",   # 14,400 req/day free
            api_key=key,
            temperature=0.2,
            max_tokens=1024,                 # cap output — saves TPM quota
        )

    # ── OpenAI GPT-4o-mini ────────────────────────────────────────────────────
    if engine == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is empty. "
                "Add it to your .env file or paste it in the sidebar."
            )
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=key,
            temperature=0.2,
        )

    # ── Ollama (local only) ───────────────────────────────────────────────────
    if engine == "ollama":
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model="llama3.2",
            base_url=host,
            temperature=0.2,
        )

    raise RuntimeError(f"Unknown engine: {engine!r}")


# ──────────────────────────────────────────────────────────────────────────────
# STATE  (message-bus between all nodes)
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
    engine_used: str          # which engine actually ran (logged for UI)


# ──────────────────────────────────────────────────────────────────────────────
# JSON REPAIR UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    text = re.sub(r"```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```",        "", text)
    text = re.sub(r"\bTrue\b",  "true",  text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b",  "null",  text)
    text = re.sub(r"(?<!\\)\'",  '"',    text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _merge_multiple_arrays(text: str) -> str:
    objects = re.findall(r'\{[^{}]*\}', text, re.DOTALL)
    if not objects:
        raise ValueError("No JSON objects found in LLM output.")
    return "[" + ",".join(objects) + "]"


def _autoclose(text: str) -> str:
    close_map = {"{": "}", "[": "]"}
    stack: list = []
    in_str = False
    escape = False
    for ch in text:
        if escape:          escape = False; continue
        if ch == "\\":      escape = True;  continue
        if ch == '"' and not escape:
            in_str = not in_str; continue
        if in_str: continue
        if ch in ("{", "["):  stack.append(close_map[ch])
        elif ch in ("}", "]") and stack: stack.pop()
    text = re.sub(r",\s*$", "", text.rstrip())
    if in_str: text += '"'
    return text + "".join(reversed(stack))


def _repair_and_parse(raw: str) -> list:
    normalized = _normalize(raw)
    start = normalized.find("[")
    end   = normalized.rfind("]")

    if start != -1 and end > start:
        try: return json.loads(normalized[start : end + 1])
        except json.JSONDecodeError: pass

    if start != -1:
        try:
            result = json.loads(_autoclose(normalized[start:]))
            if isinstance(result, list): return result
        except Exception: pass

    try: return json.loads(_merge_multiple_arrays(normalized))
    except Exception: pass

    if start != -1:
        try:
            chunk = normalized[start:]
            last_comma = max(chunk.rfind(',"'), chunk.rfind(', "'))
            if last_comma > 0:
                result = json.loads(_autoclose(chunk[:last_comma]))
                if isinstance(result, list) and result: return result
        except Exception: pass

    if start != -1 and end > start:
        try:
            import ast
            return ast.literal_eval(normalized[start : end + 1])
        except Exception: pass

    raise ValueError(
        f"Failed to parse LLM output after all repair attempts.\n"
        f"Snippet: {raw[:500]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# NODE 1 — PLANNER
# ──────────────────────────────────────────────────────────────────────────────

_PRIORITY_MAP = {
    "low": "Low", "medium": "Medium", "high": "High", "critical": "Critical",
}

def planner_node(state: AgentState) -> AgentState:
    engine = state.get("engine_used") or None  # set by run_orchestra
    try:
        llm = _build_llm(engine)
    except RuntimeError as e:
        return {**state, "error": str(e), "subtasks": []}

    # Compact prompt — ~120 tokens vs ~200 in verbose version.
    # Keys spelled out once, values enumerated inline.
    # All repair/validation still happens in _repair_and_parse + post-processing.
    _skills = "Python,React,TypeScript,CSS,Figma,FastAPI,Django,PostgreSQL,SQL,Docker,Kubernetes,CI/CD,Terraform,Machine Learning,Pytest,Selenium,Accessibility"
    prompt = (
        f'Output ONLY a JSON array of 3-5 tasks for: "{state['user_request']}"\n'
        f'Each object: title(str) description(1 sentence) '
        f'required_skills(1-3 from:[{_skills}]) '
        f'estimated_hours(0.5-16) difficulty(Low|Medium|High) priority(Low|Medium|High|Critical)\n'
        f'[{{"title":"...","description":"...","required_skills":["..."],'
        f'"estimated_hours":2,"difficulty":"Medium","priority":"High"}}]'
    )

    try:
        raw    = llm.invoke(prompt).content.strip()
        parsed = _repair_and_parse(raw)

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
            if isinstance(skills, str): skills = [skills]
            filtered = [s for s in skills if s.lower() in ALLOWED]
            item["required_skills"] = filtered or skills[:3]
            item["estimated_hours"] = float(item.get("estimated_hours", 2.0))
            item["difficulty"]      = item.get("difficulty", "Medium")
            item["priority"]        = _PRIORITY_MAP.get(
                str(item.get("priority", "Medium")).lower(), "Medium")
            item.setdefault("description", item["title"])
            valid.append(item)  # type: ignore[arg-type]

        if not valid:
            raise ValueError("No valid sub-tasks found in LLM output.")

        return {**state, "subtasks": valid, "llm_raw_response": raw}

    except Exception as e:
        return {**state, "error": f"Planner failed: {e}", "subtasks": []}


# ──────────────────────────────────────────────────────────────────────────────
# NODE 2 — MATCHMAKER  (pure math, zero LLM, zero bias)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_match_score(
    candidate: EmployeeWithSkills,
    required_skills: List[str],
) -> float:
    skill_map = {s.skill_name.lower(): s.proficiency_score for s in candidate.skills}
    matched   = [skill_map.get(r.lower(), 0) for r in required_skills]
    if not matched: return 0.0
    skill_avg = sum(matched) / len(matched)
    coverage  = sum(1 for s in matched if s > 0) / len(matched)
    load_frac = candidate.employee.current_load / 100.0
    raw = skill_avg / 10 * 0.5 + coverage * 0.3
    return round(raw * (1 - load_frac * 0.4), 4)


def matchmaker_node(state: AgentState) -> AgentState:
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

_BUFFER       = {"Low": 1.0, "Medium": 1.25, "High": 1.5}
_HOURS_PER_DAY = 6.0

def scheduler_node(state: AgentState) -> AgentState:
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
    if state.get("error") or not state.get("assigned_tasks"):
        return {**state, "final_report": "No tasks to report."}
    lines = [
        f"# Project Plan\n",
        f"**Goal:** {state['user_request']}  \n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n",
        f"**Engine:** {state.get('engine_used','auto')}  \n",
        "---\n",
    ]
    for i, at in enumerate(state["assigned_tasks"], 1):
        sub  = at["subtask"]
        task = Task(
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


def run_orchestra(user_request: str, engine: Optional[str] = None) -> AgentState:
    """
    Public entry point called by Streamlit.

    Args:
        user_request: plain-English goal string
        engine: "gemini" | "openai" | "ollama" | None (auto)
    """
    graph = build_graph()
    return graph.invoke(AgentState(
        user_request=user_request,
        subtasks=[],
        assigned_tasks=[],
        final_report="",
        error=None,
        llm_raw_response="",
        engine_used=engine or "",   # empty = auto-detect in planner_node
    ))