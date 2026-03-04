"""
pages/2_My_Tasks.py  ·  Orchestra-Agent  ·  Employee Personal Dashboard
=========================================================================
This page belongs to the EMPLOYEE — not the manager.

Design principles:
  - Employee selects their own name (simulates login; replace with
    st.session_state auth in production)
  - ONLY their tasks are ever fetched or shown
  - Three views: Personal Kanban  |  Calendar  |  Timeline (Gantt)
  - Can update task status and log actual hours directly
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
import calendar
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import (
    init_db, get_all_employees, get_tasks_for_employee,
    get_employee_stats, get_upcoming_tasks,
    update_task_status, update_task_actual_hours,
)
from auth import require_auth, render_user_widget, ROLE_EMPLOYEE

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="My Tasks — Orchestra-Agent",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ──────────────────────────────────────────────────────────────────────────────
# DESIGN SYSTEM  (same tokens as home page)
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a !important; color: #f1f5f9 !important;
    font-family: 'Inter','Segoe UI',system-ui,sans-serif;
}
[data-testid="stSidebar"] { background: #0d1117 !important; border-right:1px solid #1e293b; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
h1,h2,h3,h4 { color:#f1f5f9 !important; }
hr { border-color:#1e293b !important; margin:1.5rem 0 !important; }

/* ── KPI cards ──────────────────────────────────────────────────── */
.kpi { background:#111827; border:1px solid #1e293b; border-radius:20px;
       padding:1.3rem 1.5rem; text-align:center; }
.kpi-v { font-size:2rem; font-weight:700; line-height:1; }
.kpi-l { font-size:.72rem; color:#64748b; text-transform:uppercase;
         letter-spacing:.08em; margin-top:.35rem; }

/* ── Section label ──────────────────────────────────────────────── */
.sec-tag {
    display:inline-block; font-size:.68rem; font-weight:700;
    letter-spacing:.12em; text-transform:uppercase; color:#60a5fa;
    background:rgba(59,130,246,.1); border:1px solid rgba(59,130,246,.25);
    border-radius:6px; padding:3px 10px; margin-bottom:.5rem;
}
.sec-title { font-size:1.4rem; font-weight:700; margin:0 0 1.2rem; }

/* ── Kanban ─────────────────────────────────────────────────────── */
.kb-col { background:#0d1117; border:1px solid #1e293b; border-radius:22px;
          padding:1.1rem; min-height:300px; }
.kb-hdr { display:flex; align-items:center; gap:.5rem;
          border-bottom:1px solid #1e293b; padding-bottom:.8rem; margin-bottom:.9rem; }
.kb-dot-todo   { width:9px;height:9px;border-radius:50%;background:#6366f1;flex-shrink:0; }
.kb-dot-inprog { width:9px;height:9px;border-radius:50%;background:#f59e0b;flex-shrink:0; }
.kb-dot-done   { width:9px;height:9px;border-radius:50%;background:#10b981;flex-shrink:0; }
.kb-title { font-weight:700; font-size:.9rem; color:#f1f5f9; }
.kb-count { background:#1e293b; color:#64748b; font-size:.7rem; font-weight:600;
            border-radius:20px; padding:2px 8px; }

/* ── Task card ──────────────────────────────────────────────────── */
.tc { background:#111827; border:1px solid #1e293b; border-radius:18px;
      padding:1rem 1.1rem; margin-bottom:.75rem;
      transition:border-color .2s,transform .15s; }
.tc:hover { border-color:#3b82f6; transform:translateY(-2px); }
.tc-todo   { border-left:3px solid #6366f1; }
.tc-inprog { border-left:3px solid #f59e0b; }
.tc-done   { border-left:3px solid #10b981; opacity:.75; }
.tc-title  { font-size:.88rem; font-weight:600; color:#f1f5f9;
             margin:0 0 .35rem; line-height:1.4; }
.tc-desc   { font-size:.76rem; color:#64748b; margin:0 0 .6rem; line-height:1.5; }
.tc-foot   { display:flex; justify-content:space-between; align-items:center;
             border-top:1px solid #1e293b; padding-top:.55rem; }
.tc-dl     { font-size:.72rem; color:#64748b; }
.tc-dl span { color:#f87171; font-weight:600; }
.tc-dl .ok  { color:#34d399; }

/* badges */
.badge { font-size:.66rem; font-weight:700; letter-spacing:.05em;
         text-transform:uppercase; border-radius:7px; padding:2px 8px; }
.b-low  { background:rgba(16,185,129,.12);  color:#34d399; border:1px solid rgba(16,185,129,.25); }
.b-med  { background:rgba(245,158,11,.12);  color:#fbbf24; border:1px solid rgba(245,158,11,.25); }
.b-hi   { background:rgba(239,68,68,.12);   color:#f87171; border:1px solid rgba(239,68,68,.25); }
.b-crit { background:rgba(239,68,68,.22);   color:#ff4444; border:1px solid rgba(239,68,68,.4); }
.b-hrs  { background:rgba(99,102,241,.12);  color:#818cf8; border:1px solid rgba(99,102,241,.25); }

/* ── Calendar grid ──────────────────────────────────────────────── */
.cal-wrap { background:#111827; border:1px solid #1e293b; border-radius:22px;
            padding:1.4rem; overflow:hidden; }
.cal-nav  { display:flex; justify-content:space-between; align-items:center;
            margin-bottom:1.2rem; }
.cal-month { font-size:1.1rem; font-weight:700; color:#f1f5f9; }
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }
.cal-dow  { font-size:.68rem; font-weight:700; text-transform:uppercase;
            color:#475569; text-align:center; padding:.3rem 0; }
.cal-day  { min-height:64px; background:#0d1117; border-radius:10px;
            padding:4px 6px; font-size:.75rem; position:relative;
            border:1px solid transparent; }
.cal-day.today { border-color:#3b82f6; }
.cal-day.other-month { opacity:.3; }
.cal-day-num { font-weight:600; color:#475569; font-size:.72rem; margin-bottom:2px; }
.cal-day.today .cal-day-num { color:#60a5fa; }
.cal-event { font-size:.6rem; padding:1px 5px; border-radius:4px;
             margin-bottom:2px; line-height:1.4; white-space:nowrap;
             overflow:hidden; text-overflow:ellipsis; }
.ev-todo   { background:rgba(99,102,241,.25);  color:#a5b4fc; }
.ev-inprog { background:rgba(245,158,11,.25);  color:#fde68a; }
.ev-done   { background:rgba(16,185,129,.2);   color:#6ee7b7; }
.ev-overdue { background:rgba(239,68,68,.25);  color:#fca5a5; }

/* ── Buttons ────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
    background:linear-gradient(135deg,#3b82f6,#6366f1) !important;
    border:none !important; border-radius:12px !important;
    color:white !important; font-weight:700 !important;
}
[data-testid="stButton"] > button:hover { opacity:.88 !important; }

/* ── Inputs ─────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] input {
    background:#0d1117 !important; border:1px solid #1e293b !important;
    border-radius:10px !important; color:#f1f5f9 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #111827; border-radius:14px; padding:4px; gap:4px;
    border: 1px solid #1e293b;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background:transparent; border-radius:10px; color:#64748b !important;
    font-weight:600; padding:.4rem 1.2rem;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background:linear-gradient(135deg,#3b82f6,#6366f1) !important;
    color:white !important;
}
[data-testid="stMetric"] { background:#111827; border-radius:14px; padding:.8rem; }

/* ── Upcoming alert strip ───────────────────────────────────────── */
.alert-strip { background:rgba(239,68,68,.08); border:1px solid rgba(239,68,68,.25);
               border-radius:14px; padding:.9rem 1.2rem; margin-bottom:1rem; }
.alert-strip .al-title { font-size:.78rem; font-weight:700; color:#f87171; margin-bottom:.4rem; }
.alert-item { font-size:.75rem; color:#fca5a5; padding:2px 0; }
.alert-item span { color:#f1f5f9; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def _priority_badge(p: str) -> str:
    cls = {"Low":"b-low","Medium":"b-med","High":"b-hi","Critical":"b-crit"}.get(p,"b-med")
    return f'<span class="badge {cls}">{p}</span>'

def _status_class(s: str) -> str:
    return {"To-Do":"tc-todo","In Progress":"tc-inprog","Done":"tc-done"}.get(s,"tc-todo")

def _dot_class(s: str) -> str:
    return {"To-Do":"kb-dot-todo","In Progress":"kb-dot-inprog","Done":"kb-dot-done"}.get(s,"kb-dot-todo")

def _deadline_html(dl_str: str, status: str) -> str:
    if not dl_str:
        return '<span class="tc-dl">No deadline</span>'
    try:
        dl   = datetime.strptime(dl_str, "%Y-%m-%d").date()
        today = date.today()
        diff  = (dl - today).days
        if status == "Done":
            return f'<span class="tc-dl"><span class="ok">Done</span></span>'
        if diff < 0:
            return f'<span class="tc-dl"><span>Overdue {abs(diff)}d</span></span>'
        if diff == 0:
            return f'<span class="tc-dl"><span>Due today</span></span>'
        if diff <= 3:
            return f'<span class="tc-dl"><span>{dl_str}</span> ({diff}d)</span>'
        return f'<span class="tc-dl ok">{dl_str}</span>'
    except Exception:
        return f'<span class="tc-dl">{dl_str}</span>'

def _task_card(t: dict) -> str:
    sc   = _status_class(t.get("status","To-Do"))
    pri  = t.get("priority","Medium") or "Medium"
    hrs  = t.get("estimated_hours", 0)
    desc = (t.get("description","") or "")[:80]
    if len(t.get("description","")) > 80: desc += "…"
    dl_html = _deadline_html(t.get("deadline",""), t.get("status",""))
    return f"""
<div class="tc {sc}">
  <div class="tc-title">{t['title']}</div>
  <div class="tc-desc">{desc}</div>
  <div style="display:flex;gap:.35rem;flex-wrap:wrap;margin-bottom:.55rem">
    {_priority_badge(pri)}
    <span class="badge b-hrs">{hrs}h</span>
  </div>
  <div class="tc-foot">{dl_html}</div>
</div>"""


# ──────────────────────────────────────────────────────────────────────────────
# AUTH GUARD — redirect to login if not authenticated
# ──────────────────────────────────────────────────────────────────────────────

user = require_auth(ROLE_EMPLOYEE)

# Resolve which employee record to show.
# - Employee role:  must use their own linked employee_id
# - Manager/Admin:  may view any employee (picker shown in sidebar)
all_employees = get_all_employees()
emp_map       = {e["id"]: e for e in all_employees}

if user["role"] == "employee":
    emp_id = user["employee_id"]
    if not emp_id or emp_id not in emp_map:
        st.error("Your account is not linked to an employee record. "
                 "Ask an admin to link your account in the Admin panel.")
        st.stop()
    emp_data    = emp_map[emp_id]
    chosen_name = emp_data["name"]
else:
    # manager / admin can pick any employee to view
    emp_names = [e["name"] for e in all_employees]
    emp_by_name = {e["name"]: e for e in all_employees}
    with st.sidebar:
        chosen_name = st.selectbox("View employee", emp_names, key="mgr_emp_sel")
    emp_data = emp_by_name[chosen_name]
    emp_id   = emp_data["id"]

my_tasks = get_tasks_for_employee(emp_id)
my_stats = get_employee_stats(emp_id)
upcoming = get_upcoming_tasks(emp_id, days=7)

with st.sidebar:
    st.markdown("### My Tasks")
    st.markdown("<span style='color:#64748b;font-size:.8rem'>Employee View</span>",
                unsafe_allow_html=True)
    st.divider()
    render_user_widget()
    st.divider()
    st.markdown(f"""
<div style="text-align:center;padding:.5rem 0">
  <div style="width:52px;height:52px;border-radius:50%;margin:0 auto .6rem;
    background:linear-gradient(135deg,#3b82f6,#6366f1);
    display:flex;align-items:center;justify-content:center;
    font-weight:700;font-size:1.1rem;color:white">{_initials(chosen_name)}</div>
  <div style="font-weight:700;color:#f1f5f9">{chosen_name}</div>
  <div style="font-size:.75rem;color:#475569">{emp_data['department']}</div>
</div>""", unsafe_allow_html=True)

    load  = emp_data["current_load"]
    color = "#10b981" if load < 40 else "#f59e0b" if load < 70 else "#ef4444"
    st.markdown(f"""
<div style="margin:1rem 0 .3rem;font-size:.72rem;color:#64748b;
     display:flex;justify-content:space-between">
  <span>Workload</span><span style="color:{color};font-weight:700">{load:.0f}%</span>
</div>
<div style="height:6px;background:#1e293b;border-radius:10px;overflow:hidden">
  <div style="height:100%;width:{load}%;background:{color};border-radius:10px"></div>
</div>""", unsafe_allow_html=True)

    if upcoming:
        st.markdown("<br>", unsafe_allow_html=True)
        items_html = "".join(
            f'<div class="alert-item"><span>{t["title"][:28]}</span> — {t["deadline"]}</div>'
            for t in upcoming[:4]
        )
        st.markdown(f"""
<div class="alert-strip">
  <div class="al-title">Due this week ({len(upcoming)})</div>
  {items_html}
</div>""", unsafe_allow_html=True)

    st.divider()
    if st.button("Home", use_container_width=True, key="my_home_btn"):
        st.switch_page("app.py")


# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#1e3a5f 100%);
            border:1px solid #6366f1; border-radius:22px; padding:2rem 2.5rem;
            margin-bottom:1.8rem;">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:#818cf8;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.25);
              border-radius:6px;display:inline-block;padding:2px 10px;margin-bottom:.7rem">
    Employee Dashboard
  </div>
  <h1 style="font-size:2rem;font-weight:800;background:linear-gradient(90deg,#818cf8,#c4b5fd);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             background-clip:text;margin:0 0 .3rem">{chosen_name}'s Workspace</h1>
  <p style="color:#64748b;margin:0;font-size:.9rem">
    {emp_data['department']} &nbsp;·&nbsp; {my_stats['total']} task{'s' if my_stats['total'] != 1 else ''}
    &nbsp;·&nbsp; {my_stats['est_hours']:.1f}h estimated
  </p>
</div>
""", unsafe_allow_html=True)

# KPI strip
k1, k2, k3, k4, k5 = st.columns(5)
kpi_data = [
    (my_stats["total"],           "#60a5fa", "Total Tasks"),
    (my_stats["In Progress"],     "#f59e0b", "In Progress"),
    (my_stats["To-Do"],           "#818cf8", "To-Do"),
    (my_stats["Done"],            "#34d399", "Done"),
    (f"{my_stats['est_hours']:.1f}h", "#94a3b8", "Est. Hours"),
]
for col, (val, color, label) in zip([k1,k2,k3,k4,k5], kpi_data):
    col.markdown(f"""
<div class="kpi">
  <div class="kpi-v" style="color:{color}">{val}</div>
  <div class="kpi-l">{label}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────────────────────────

tab_kanban, tab_calendar, tab_timeline, tab_log = st.tabs([
    "  Kanban  ",
    "  Calendar  ",
    "  Timeline  ",
    "  Log Hours  ",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PERSONAL KANBAN
# ══════════════════════════════════════════════════════════════════════════════

with tab_kanban:
    st.markdown("""
<div class="sec-tag">Personal Board</div>
<div class="sec-title">My Task Board</div>""", unsafe_allow_html=True)

    # Quick status-move
    if my_tasks:
        with st.expander("Move a task to a different column"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                task_opts = {f"[{t['id']}] {t['title']}": t["id"] for t in my_tasks}
                sel_label = st.selectbox("Task", list(task_opts.keys()), key="k_task")
            with mc2:
                new_st = st.selectbox("Move to", ["To-Do","In Progress","Done"], key="k_status")
            with mc3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Update Status", use_container_width=True, key="k_move"):
                    update_task_status(task_opts[sel_label], new_st)
                    st.rerun()

    col_todo, col_prog, col_done = st.columns(3, gap="medium")
    COLS = {
        "To-Do":       (col_todo,  "kb-dot-todo"),
        "In Progress": (col_prog,  "kb-dot-inprog"),
        "Done":        (col_done,  "kb-dot-done"),
    }

    for status, (col_widget, dot_cls) in COLS.items():
        with col_widget:
            col_tasks = [t for t in my_tasks if t.get("status") == status]
            cards_html = "".join(_task_card(t) for t in col_tasks) if col_tasks else \
                '<div style="color:#1e293b;font-size:.82rem;text-align:center;padding:2rem 0">No tasks</div>'
            st.markdown(f"""
<div class="kb-col">
  <div class="kb-hdr">
    <div class="{dot_cls}"></div>
    <span class="kb-title">{status}</span>
    <span class="kb-count">{len(col_tasks)}</span>
  </div>
  {cards_html}
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CALENDAR VIEW
# ══════════════════════════════════════════════════════════════════════════════

with tab_calendar:
    st.markdown("""
<div class="sec-tag">Calendar</div>
<div class="sec-title">Monthly Deadline View</div>""", unsafe_allow_html=True)

    today = date.today()
    # Month navigator in session state
    if "cal_year"  not in st.session_state: st.session_state.cal_year  = today.year
    if "cal_month" not in st.session_state: st.session_state.cal_month = today.month

    nav1, nav2, nav3 = st.columns([1, 4, 1])
    with nav1:
        if st.button("◀ Prev", use_container_width=True, key="prev_m"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with nav2:
        month_name = datetime(st.session_state.cal_year,
                              st.session_state.cal_month, 1).strftime("%B %Y")
        st.markdown(f"<div style='text-align:center;font-size:1.15rem;font-weight:700;"
                    f"color:#f1f5f9;padding:.5rem'>{month_name}</div>",
                    unsafe_allow_html=True)
    with nav3:
        if st.button("Next ▶", use_container_width=True, key="next_m"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    # Build deadline map {date_str: [task, ...]}
    deadline_map: dict = {}
    for t in my_tasks:
        dl = t.get("deadline")
        if dl:
            deadline_map.setdefault(dl, []).append(t)

    # Build calendar grid HTML
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdatescalendar(st.session_state.cal_year,
                                        st.session_state.cal_month)

    dow_headers = "".join(
        f'<div class="cal-dow">{d}</div>'
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    )

    def _ev_class(t: dict) -> str:
        if t.get("status") == "Done": return "ev-done"
        if t.get("deadline") and t["deadline"] < today.isoformat(): return "ev-overdue"
        return {"To-Do":"ev-todo","In Progress":"ev-inprog"}.get(t.get("status",""),"ev-todo")

    cells_html = ""
    for week in month_days:
        for d in week:
            is_today       = (d == today)
            is_this_month  = (d.month == st.session_state.cal_month)
            extra_cls      = "today" if is_today else ("other-month" if not is_this_month else "")

            events = deadline_map.get(d.isoformat(), [])
            ev_html = ""
            for t in events[:3]:  # max 3 events visible per day
                ec = _ev_class(t)
                short = t["title"][:16] + ("…" if len(t["title"]) > 16 else "")
                ev_html += f'<div class="cal-event {ec}" title="{t["title"]}">{short}</div>'
            if len(events) > 3:
                ev_html += f'<div style="font-size:.58rem;color:#475569">+{len(events)-3} more</div>'

            cells_html += f"""
<div class="cal-day {extra_cls}">
  <div class="cal-day-num">{d.day}</div>
  {ev_html}
</div>"""

    st.markdown(f"""
<div class="cal-wrap">
  <div class="cal-grid">
    {dow_headers}
    {cells_html}
  </div>
</div>""", unsafe_allow_html=True)

    # Legend
    st.markdown("""
<div style="display:flex;gap:1rem;margin-top:1rem;flex-wrap:wrap">
  <div style="display:flex;align-items:center;gap:.4rem">
    <div style="width:10px;height:10px;border-radius:3px;background:rgba(99,102,241,.4)"></div>
    <span style="font-size:.72rem;color:#64748b">To-Do</span>
  </div>
  <div style="display:flex;align-items:center;gap:.4rem">
    <div style="width:10px;height:10px;border-radius:3px;background:rgba(245,158,11,.4)"></div>
    <span style="font-size:.72rem;color:#64748b">In Progress</span>
  </div>
  <div style="display:flex;align-items:center;gap:.4rem">
    <div style="width:10px;height:10px;border-radius:3px;background:rgba(16,185,129,.3)"></div>
    <span style="font-size:.72rem;color:#64748b">Done</span>
  </div>
  <div style="display:flex;align-items:center;gap:.4rem">
    <div style="width:10px;height:10px;border-radius:3px;background:rgba(239,68,68,.4)"></div>
    <span style="font-size:.72rem;color:#64748b">Overdue</span>
  </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — GANTT / TIMELINE
# ══════════════════════════════════════════════════════════════════════════════

with tab_timeline:
    st.markdown("""
<div class="sec-tag">Timeline</div>
<div class="sec-title">Task Schedule (Gantt)</div>""", unsafe_allow_html=True)

    if not my_tasks:
        st.info("No tasks assigned yet.")
    else:
        # Build Gantt dataframe
        rows = []
        today_dt = datetime.now()

        for t in my_tasks:
            dl_str = t.get("deadline")
            try:
                end_dt = datetime.strptime(dl_str, "%Y-%m-%d") if dl_str \
                         else today_dt + timedelta(days=3)
            except Exception:
                end_dt = today_dt + timedelta(days=3)

            est_h  = t.get("estimated_hours", 1.0)
            start_dt = end_dt - timedelta(hours=est_h * 1.25)  # back-calculate start

            status = t.get("status","To-Do")
            color  = {"To-Do":"#6366f1","In Progress":"#f59e0b","Done":"#10b981"}.get(status,"#6366f1")
            pri    = t.get("priority","Medium")

            rows.append(dict(
                Task    = f"{t['title'][:30]}{'…' if len(t['title'])>30 else ''}",
                Start   = start_dt,
                Finish  = end_dt,
                Status  = status,
                Priority= pri,
                Hours   = est_h,
                Color   = color,
                Full    = t["title"],
            ))

        if rows:
            df_g = pd.DataFrame(rows).sort_values("Start")

            fig = px.timeline(
                df_g,
                x_start="Start",
                x_end="Finish",
                y="Task",
                color="Status",
                color_discrete_map={
                    "To-Do":       "#6366f1",
                    "In Progress": "#f59e0b",
                    "Done":        "#10b981",
                },
                hover_data={"Priority": True, "Hours": True, "Full": True,
                            "Start": False, "Finish": False},
                labels={"Task":""},
            )

            # Today line
            fig.add_vline(
                x=today_dt.timestamp() * 1000,
                line_dash="dot", line_color="#ef4444", line_width=2,
                annotation_text="Today",
                annotation_font_color="#f87171",
                annotation_position="top right",
            )

            fig.update_layout(
                plot_bgcolor="#111827", paper_bgcolor="#111827",
                font=dict(color="#94a3b8", size=11),
                xaxis=dict(gridcolor="#1e293b", title="", tickfont=dict(color="#64748b")),
                yaxis=dict(gridcolor="#1e293b", autorange="reversed",
                           tickfont=dict(color="#f1f5f9", size=11)),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
                margin=dict(l=10, r=30, t=50, b=20),
                height=max(250, len(rows) * 42 + 80),
                bargap=0.3,
            )
            fig.update_traces(marker_line_width=0)

            st.plotly_chart(fig, width="stretch")

        # Priority breakdown
        st.markdown("<br>", unsafe_allow_html=True)
        pri_cols = st.columns(4)
        for i, (pri, color) in enumerate([
            ("Critical","#ef4444"),("High","#f87171"),
            ("Medium","#fbbf24"),("Low","#34d399")
        ]):
            cnt = sum(1 for t in my_tasks if t.get("priority") == pri)
            pri_cols[i].markdown(f"""
<div class="kpi">
  <div class="kpi-v" style="color:{color}">{cnt}</div>
  <div class="kpi-l">{pri}</div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — LOG HOURS
# ══════════════════════════════════════════════════════════════════════════════

with tab_log:
    st.markdown("""
<div class="sec-tag">Work Log</div>
<div class="sec-title">Log Actual Hours & Update Status</div>""", unsafe_allow_html=True)

    if not my_tasks:
        st.info("No tasks to log hours for yet.")
    else:
        active = [t for t in my_tasks if t.get("status") != "Done"]
        done   = [t for t in my_tasks if t.get("status") == "Done"]

        st.markdown("#### Active Tasks")
        for t in active:
            with st.expander(f"[{t.get('priority','Med')}]  {t['title']}  — {t.get('status','To-Do')}"):
                l1, l2, l3 = st.columns([3, 2, 2])
                with l1:
                    st.markdown(f"**Description:** {t.get('description','—')}")
                    st.markdown(f"**Deadline:** {t.get('deadline','—')}")
                    st.markdown(f"**Estimated:** {t.get('estimated_hours',0)}h")
                with l2:
                    new_status = st.selectbox(
                        "Status", ["To-Do","In Progress","Done"],
                        index=["To-Do","In Progress","Done"].index(t.get("status","To-Do")),
                        key=f"st_{t['id']}"
                    )
                with l3:
                    actual_h = st.number_input(
                        "Actual hours", min_value=0.0, step=0.5,
                        value=float(t.get("actual_hours") or 0.0),
                        key=f"ah_{t['id']}"
                    )

                if st.button("Save", key=f"save_{t['id']}", use_container_width=True):
                    update_task_status(t["id"], new_status)
                    if actual_h > 0:
                        update_task_actual_hours(t["id"], actual_h)
                    st.success("Saved!")
                    st.rerun()

        if done:
            st.markdown("#### Completed Tasks")
            done_rows = [{
                "Title":     t["title"],
                "Priority":  t.get("priority","—"),
                "Est. h":    t.get("estimated_hours",0),
                "Actual h":  t.get("actual_hours","—"),
                "Deadline":  t.get("deadline","—"),
            } for t in done]
            st.dataframe(pd.DataFrame(done_rows), width="stretch",
                         hide_index=True, height=250)

        # Efficiency chart if any actual hours logged
        logged = [t for t in my_tasks if t.get("actual_hours")]
        if len(logged) >= 2:
            st.markdown("#### Your Estimation Accuracy")
            df_acc = pd.DataFrame([{
                "Task":      t["title"][:22] + "…",
                "Estimated": t["estimated_hours"],
                "Actual":    t["actual_hours"],
                "Variance":  round(t["actual_hours"] - t["estimated_hours"], 2),
            } for t in logged])

            fig_acc = go.Figure([
                go.Bar(name="Estimated", x=df_acc["Task"], y=df_acc["Estimated"],
                       marker_color="#6366f1", marker_line_width=0),
                go.Bar(name="Actual",    x=df_acc["Task"], y=df_acc["Actual"],
                       marker_color="#f59e0b", marker_line_width=0),
            ])
            fig_acc.update_layout(
                barmode="group",
                plot_bgcolor="#111827", paper_bgcolor="#111827",
                font=dict(color="#94a3b8", size=11),
                legend=dict(orientation="h", bgcolor="rgba(0,0,0,0)"),
                xaxis=dict(tickangle=-30, gridcolor="#1e293b"),
                yaxis=dict(title="Hours", gridcolor="#1e293b"),
                margin=dict(l=10,r=10,t=30,b=80), height=300,
            )
            st.plotly_chart(fig_acc, width="stretch")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:2rem 0 .5rem;color:#1e293b;font-size:.78rem">
  Orchestra-Agent · Employee View · Data is scoped to your account only
</div>
""", unsafe_allow_html=True)