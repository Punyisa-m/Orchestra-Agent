"""
app.py  ·  Orchestra-Agent v2  ·  Kanban Dashboard
=====================================================
Design system:
  Primary background : #0a0e1a  (deep navy)
  Surface            : #111827  (card backgrounds)
  Accent             : #3b82f6  (electric blue)
  Accent 2           : #6366f1  (indigo)
  Text primary       : #f1f5f9
  Text muted         : #64748b
  Border radius      : 20px (cards), 12px (inputs)
  No emojis — CSS badges / SVG icons only
"""

import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from database import (
    init_db, get_all_tasks, get_workload_distribution,
    get_all_employees_with_skills, update_task_status,
    simulate_actual_hours, reset_demo_data,
)
from graph import run_orchestra
from auth import require_auth, render_user_widget, ROLE_MANAGER

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Manager Dashboard — Orchestra-Agent",
    page_icon="assets/icon.png" if os.path.exists("assets/icon.png") else "O",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ── Auth guard
user = require_auth(ROLE_MANAGER)

# ──────────────────────────────────────────────────────────────────────────────
# DESIGN SYSTEM  (injected once via st.markdown)
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Reset & Base ─────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a !important;
    color: #f1f5f9 !important;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #1e293b;
}
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }

/* ── Typography ──────────────────────────────────────────────────── */
h1,h2,h3,h4 { color: #f1f5f9 !important; letter-spacing: -0.02em; }

/* ── Header Banner ───────────────────────────────────────────────── */
.oa-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #1e3a5f 100%);
    border: 1px solid #3b82f6;
    border-radius: 24px;
    padding: 2.4rem 3rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.oa-header::before {
    content: '';
    position: absolute; top: -60px; right: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(99,102,241,.25) 0%, transparent 70%);
    border-radius: 50%;
}
.oa-header h1 {
    font-size: 2.2rem; font-weight: 800;
    background: linear-gradient(90deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 .4rem;
}
.oa-header p { color: #94a3b8; margin: 0; font-size: 1rem; }

/* ── KPI Strip ───────────────────────────────────────────────────── */
.kpi-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 20px;
    padding: 1.4rem 1.6rem;
    text-align: center;
    transition: border-color .2s;
}
.kpi-card:hover { border-color: #3b82f6; }
.kpi-value { font-size: 2rem; font-weight: 700; color: #60a5fa; line-height:1; }
.kpi-label { font-size: .78rem; color: #64748b; margin-top: .35rem;
             text-transform: uppercase; letter-spacing: .08em; }

/* ── Section Label ───────────────────────────────────────────────── */
.section-label {
    display: inline-block;
    font-size: .7rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #60a5fa;
    background: rgba(59,130,246,.12);
    border: 1px solid rgba(59,130,246,.25);
    border-radius: 6px; padding: 3px 10px; margin-bottom: .6rem;
}
.section-title {
    font-size: 1.5rem; font-weight: 700; color: #f1f5f9;
    margin: 0 0 1.4rem; line-height: 1.2;
}

/* ── Kanban Column ───────────────────────────────────────────────── */
.kanban-col {
    background: #0d1117;
    border: 1px solid #1e293b;
    border-radius: 24px;
    padding: 1.2rem;
    min-height: 400px;
}
.kanban-col-header {
    display: flex; align-items: center; gap: .6rem;
    padding: .5rem .2rem 1rem;
    border-bottom: 1px solid #1e293b;
    margin-bottom: 1rem;
}
.kanban-col-title {
    font-weight: 700; font-size: .95rem; color: #f1f5f9;
}
.kanban-count {
    background: #1e293b; color: #64748b;
    font-size: .72rem; font-weight: 600;
    border-radius: 20px; padding: 2px 9px;
}
.col-dot-todo     { width:10px;height:10px;border-radius:50%;background:#6366f1;flex-shrink:0; }
.col-dot-inprog   { width:10px;height:10px;border-radius:50%;background:#f59e0b;flex-shrink:0; }
.col-dot-done     { width:10px;height:10px;border-radius:50%;background:#10b981;flex-shrink:0; }

/* ── Task Card ───────────────────────────────────────────────────── */
.task-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 20px;
    padding: 1.1rem 1.2rem 1rem;
    margin-bottom: .85rem;
    transition: border-color .2s, transform .15s;
    position: relative;
}
.task-card:hover {
    border-color: #3b82f6;
    transform: translateY(-2px);
}
.task-card-accent-todo   { border-left: 3px solid #6366f1; }
.task-card-accent-inprog { border-left: 3px solid #f59e0b; }
.task-card-accent-done   { border-left: 3px solid #10b981; }
.task-title {
    font-size: .9rem; font-weight: 600; color: #f1f5f9;
    margin: 0 0 .5rem; line-height: 1.4;
}
.task-desc {
    font-size: .78rem; color: #64748b;
    margin: 0 0 .8rem; line-height: 1.5;
}
.task-meta {
    display: flex; flex-wrap: wrap; gap: .4rem;
    align-items: center; margin-bottom: .7rem;
}
.badge {
    font-size: .68rem; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; border-radius: 8px; padding: 3px 9px;
    line-height: 1.4;
}
.badge-low      { background:rgba(16,185,129,.15); color:#34d399; border:1px solid rgba(16,185,129,.3); }
.badge-medium   { background:rgba(245,158,11,.15);  color:#fbbf24; border:1px solid rgba(245,158,11,.3); }
.badge-high     { background:rgba(239,68,68,.15);   color:#f87171; border:1px solid rgba(239,68,68,.3); }
.badge-critical { background:rgba(239,68,68,.25);   color:#ff4444; border:1px solid rgba(239,68,68,.5);
                  animation: pulse-red 2s infinite; }
@keyframes pulse-red {
    0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,.4); }
    50%      { box-shadow: 0 0 0 4px rgba(239,68,68,.0); }
}
.task-footer {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: .6rem; padding-top: .6rem;
    border-top: 1px solid #1e293b;
}
.assignee-chip {
    display: flex; align-items: center; gap: .4rem;
}
.avatar {
    width: 22px; height: 22px; border-radius: 50%;
    background: linear-gradient(135deg,#3b82f6,#6366f1);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: .6rem; font-weight: 700; color: white; flex-shrink: 0;
}
.assignee-name { font-size: .75rem; color: #94a3b8; }
.deadline-chip  { font-size: .72rem; color: #64748b; }
.deadline-chip span { color: #60a5fa; font-weight: 600; }

/* ── Input Area ──────────────────────────────────────────────────── */
.input-panel {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 24px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.5rem;
}
[data-testid="stTextArea"] textarea {
    background: #0d1117 !important;
    border: 1px solid #1e293b !important;
    border-radius: 14px !important;
    color: #f1f5f9 !important;
    font-size: .9rem !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,.2) !important;
}
[data-testid="stButton"] > button {
    background: linear-gradient(135deg,#3b82f6,#6366f1) !important;
    border: none !important;
    border-radius: 14px !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: .9rem !important;
    padding: .65rem 1.8rem !important;
    transition: opacity .2s, transform .15s !important;
}
[data-testid="stButton"] > button:hover {
    opacity: .9 !important; transform: translateY(-1px) !important;
}
[data-testid="stButton"][data-testid*="secondary"] > button {
    background: #1e293b !important;
}

/* ── Status pill (sidebar) ────────────────────────────────────────── */
.load-bar-wrap { margin-bottom:.6rem; }
.load-bar-label {
    display:flex; justify-content:space-between;
    font-size:.75rem; color:#94a3b8; margin-bottom:3px;
}
.load-bar-track {
    height:6px; background:#1e293b; border-radius:20px; overflow:hidden;
}
.load-bar-fill { height:100%; border-radius:20px; }

/* ── Charts ──────────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] { border-radius: 20px; overflow: hidden; }

/* ── Divider ─────────────────────────────────────────────────────── */
hr { border-color: #1e293b !important; margin: 1.8rem 0 !important; }

/* ── Selectbox / multiselect ─────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #0d1117 !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    color: #f1f5f9 !important;
}

/* ── Metric delta ────────────────────────────────────────────────── */
[data-testid="stMetric"] { background: #111827; border-radius: 16px; padding: .8rem; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()


def _load_color(load: float) -> str:
    if load < 40:  return "#10b981"
    if load < 70:  return "#f59e0b"
    return "#ef4444"


def _priority_badge(priority: str) -> str:
    cls = {"Low":"low","Medium":"medium","High":"high","Critical":"critical"}.get(priority,"medium")
    return f'<span class="badge badge-{cls}">{priority}</span>'


def _col_accent(status: str) -> str:
    return {"To-Do":"todo","In Progress":"inprog","Done":"done"}.get(status,"todo")


def _render_card(task: dict) -> str:
    accent  = _col_accent(task.get("status","To-Do"))
    pri     = task.get("priority","Medium") or "Medium"
    name    = task.get("assigned_name") or "Unassigned"
    dl      = task.get("deadline") or "—"
    hours   = task.get("estimated_hours", 0)
    desc    = task.get("description","")
    if len(desc) > 90: desc = desc[:87] + "..."

    return f"""
<div class="task-card task-card-accent-{accent}">
  <div class="task-title">{task['title']}</div>
  <div class="task-desc">{desc}</div>
  <div class="task-meta">
    {_priority_badge(pri)}
    <span class="badge" style="background:rgba(99,102,241,.12);color:#818cf8;
          border:1px solid rgba(99,102,241,.25);">{hours}h</span>
  </div>
  <div class="task-footer">
    <div class="assignee-chip">
      <div class="avatar">{_initials(name)}</div>
      <span class="assignee-name">{name}</span>
    </div>
    <div class="deadline-chip">Due <span>{dl}</span></div>
  </div>
</div>"""


def _workload_chart(df: pd.DataFrame) -> go.Figure:
    df = df.sort_values("current_load", ascending=True)
    colors = [_load_color(v) for v in df["current_load"]]
    fig = go.Figure(go.Bar(
        x=df["current_load"], y=df["name"], orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}%" for v in df["current_load"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Load: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Current Load (%)", xaxis_range=[0,115],
        plot_bgcolor="#111827", paper_bgcolor="#111827",
        font=dict(color="#94a3b8", size=12),
        margin=dict(l=10,r=40,t=20,b=10), height=300,
        xaxis=dict(gridcolor="#1e293b", zerolinecolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b"),
    )
    return fig


def _est_vs_actual_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty or "actual_hours" not in df.columns:
        fig = go.Figure()
        fig.update_layout(
            plot_bgcolor="#111827", paper_bgcolor="#111827",
            font=dict(color="#64748b"),
            annotations=[dict(text="Click 'Simulate Hours' to generate data",
                              showarrow=False, font=dict(color="#475569", size=13))],
            height=300,
        )
        return fig
    df2 = df[df["actual_hours"].notna()].copy()
    if df2.empty:
        return _est_vs_actual_chart(pd.DataFrame())
    df2["label"] = df2["title"].str[:20] + "…"
    fig = go.Figure([
        go.Bar(name="Estimated", x=df2["label"], y=df2["estimated_hours"],
               marker_color="#3b82f6", marker_line_width=0),
        go.Bar(name="Actual",    x=df2["label"], y=df2["actual_hours"],
               marker_color="#6366f1", marker_line_width=0),
    ])
    fig.update_layout(
        barmode="group",
        plot_bgcolor="#111827", paper_bgcolor="#111827",
        font=dict(color="#94a3b8", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10,r=10,t=30,b=80), height=300,
        xaxis=dict(tickangle=-40, gridcolor="#1e293b"),
        yaxis=dict(title="Hours", gridcolor="#1e293b"),
    )
    return fig


def _skill_heatmap(skill_df: pd.DataFrame) -> go.Figure:
    pivot = skill_df.pivot_table(
        index="Employee", columns="Skill", values="Proficiency", fill_value=0)
    fig = px.imshow(
        pivot, color_continuous_scale=[[0,"#0d1117"],[0.4,"#1e3a5f"],[1,"#3b82f6"]],
        aspect="auto",
        labels=dict(color="Score"),
    )
    fig.update_layout(
        plot_bgcolor="#111827", paper_bgcolor="#111827",
        font=dict(color="#94a3b8", size=11),
        margin=dict(l=10,r=10,t=10,b=10), height=320,
        coloraxis_colorbar=dict(tickfont=dict(color="#94a3b8")),
    )
    fig.update_xaxes(tickangle=-40, tickfont=dict(size=10))
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Manager Dashboard")
    st.markdown("<span style='color:#64748b;font-size:.8rem'>AI Task Manager</span>",
                unsafe_allow_html=True)
    st.divider()
    render_user_widget()
    st.divider()

    # LLM engine
    llm_mode = st.radio("AI Engine", ["OpenAI GPT-4o-mini", "Ollama Llama 3.2"])
    if llm_mode.startswith("OpenAI"):
        key = st.text_input("API Key", type="password",
                            value=os.getenv("OPENAI_API_KEY",""))
        if key: os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
        st.caption("Ensure `ollama serve` is running.")

    st.divider()

    # Live load bars
    st.markdown("<div style='font-size:.75rem;font-weight:700;color:#64748b;"
                "text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem'>"
                "Team Workload</div>", unsafe_allow_html=True)

    wl_data = get_workload_distribution()
    for row in wl_data:
        load  = row["current_load"]
        color = _load_color(load)
        st.markdown(f"""
<div class="load-bar-wrap">
  <div class="load-bar-label">
    <span>{row['name'].split()[0]}</span>
    <span style="color:{color};font-weight:700">{load:.0f}%</span>
  </div>
  <div class="load-bar-track">
    <div class="load-bar-fill" style="width:{load}%;background:{color}"></div>
  </div>
</div>""", unsafe_allow_html=True)

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Simulate", use_container_width=True):
            simulate_actual_hours(); st.rerun()
    with col_b:
        if st.button("Reset", use_container_width=True):
            reset_demo_data(); st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="oa-header">
  <h1>Orchestra-Agent</h1>
  <p>Transform any project goal into a fully assigned, scheduled Kanban board — instantly.</p>
</div>
""", unsafe_allow_html=True)

# ── KPI strip ─────────────────────────────────────────────────────────────────
all_tasks = get_all_tasks()
df_all    = pd.DataFrame(all_tasks) if all_tasks else pd.DataFrame()
wl_df     = pd.DataFrame(wl_data)

total   = len(df_all)
todo    = len(df_all[df_all["status"]=="To-Do"])       if not df_all.empty else 0
inprog  = len(df_all[df_all["status"]=="In Progress"]) if not df_all.empty else 0
done    = len(df_all[df_all["status"]=="Done"])        if not df_all.empty else 0
avg_ld  = wl_df["current_load"].mean()                 if not wl_df.empty else 0
bal_score = max(0, 100 - wl_df["current_load"].std())  if not wl_df.empty else 100

k1,k2,k3,k4,k5,k6 = st.columns(6)
for col, val, label in [
    (k1, total,         "Total Tasks"),
    (k2, todo,          "To-Do"),
    (k3, inprog,        "In Progress"),
    (k4, done,          "Done"),
    (k5, f"{avg_ld:.0f}%",  "Avg Load"),
    (k6, f"{bal_score:.0f}", "Balance Score"),
]:
    col.markdown(f"""
<div class="kpi-card">
  <div class="kpi-value">{val}</div>
  <div class="kpi-label">{label}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 — PROJECT INPUT
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="section-label">New Project</div>
<div class="section-title">What do you want to build?</div>
""", unsafe_allow_html=True)

EXAMPLES = [
    "Develop a login page with email verification and Google OAuth",
    "Build a real-time analytics dashboard with role-based access",
    "Set up a CI/CD pipeline for a Python microservice on Kubernetes",
    "Create a machine learning model for customer churn prediction",
    "Design a responsive e-commerce checkout flow with Stripe integration",
]

example = st.selectbox("Quick-start examples", ["— type your own below —"] + EXAMPLES)

user_input = st.text_area(
    "Project goal",
    value=example if example != "— type your own below —" else "",
    height=90,
    placeholder="e.g.  Build a REST API with JWT auth, rate limiting, and Swagger docs",
    label_visibility="collapsed",
)

run_col, _ = st.columns([1, 5])
with run_col:
    run_btn = st.button("Generate Board", type="primary", use_container_width=True)

if run_btn and user_input.strip():
    with st.status("Running Orchestra pipeline...", expanded=True) as status:
        st.write("**[1/4] Planner** — decomposing goal into sub-tasks...")
        time.sleep(0.2)
        st.write("**[2/4] Matchmaker** — scoring employees via Skill Matrix...")
        time.sleep(0.2)
        st.write("**[3/4] Scheduler** — chaining deadlines per employee queue...")
        time.sleep(0.2)
        result = run_orchestra(user_input)
        st.write("**[4/4] Reporter** — writing to database...")
        status.update(label="Board generated.", state="complete")

    if result.get("error"):
        st.error(f"Pipeline error: {result['error']}")
        with st.expander("Debug — raw LLM output"):
            st.code(result.get("llm_raw_response",""), language="text")
    else:
        st.success(f"Created {len(result['assigned_tasks'])} tasks successfully.")
        st.rerun()

elif run_btn:
    st.warning("Please enter a project goal first.")

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 — KANBAN BOARD
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="section-label">Kanban Board</div>
<div class="section-title">Task Assignment Map</div>
""", unsafe_allow_html=True)

COLUMNS = ["To-Do", "In Progress", "Done"]
COL_DOTS = {"To-Do": "col-dot-todo", "In Progress": "col-dot-inprog", "Done": "col-dot-done"}

# Status-move controls sit above the board
if not df_all.empty:
    with st.expander("Move a card between columns"):
        mv1, mv2, mv3 = st.columns(3)
        with mv1:
            task_options = {f"[{r['id']}] {r['title']}": r['id']
                            for r in all_tasks}
            selected_label = st.selectbox("Select task", list(task_options.keys()))
        with mv2:
            new_status = st.selectbox("Move to", COLUMNS, key="mv_status")
        with mv3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Move Card", use_container_width=True):
                tid = task_options[selected_label]
                update_task_status(tid, new_status)
                st.rerun()

# Board columns
board_cols = st.columns(3, gap="medium")

for col_widget, col_name in zip(board_cols, COLUMNS):
    with col_widget:
        col_tasks = [t for t in all_tasks if t.get("status") == col_name]
        dot_cls   = COL_DOTS[col_name]

        st.markdown(f"""
<div class="kanban-col">
  <div class="kanban-col-header">
    <div class="{dot_cls}"></div>
    <span class="kanban-col-title">{col_name}</span>
    <span class="kanban-count">{len(col_tasks)}</span>
  </div>
  {''.join(_render_card(t) for t in col_tasks) if col_tasks
   else '<div style="color:#334155;font-size:.82rem;text-align:center;padding:2rem 0">No tasks</div>'}
</div>""", unsafe_allow_html=True)

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 — ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="section-label">Analytics</div>
<div class="section-title">Performance Overview</div>
""", unsafe_allow_html=True)

an1, an2 = st.columns(2)

with an1:
    st.markdown("**Workload Distribution**")
    st.plotly_chart(_workload_chart(wl_df), width="stretch")

with an2:
    st.markdown("**Estimated vs Actual Hours**")
    st.plotly_chart(_est_vs_actual_chart(df_all), width="stretch")

# Balance score breakdown
if not wl_df.empty:
    std = wl_df["current_load"].std()
    b_score = max(0.0, 100.0 - std)
    mb1, mb2, mb3 = st.columns(3)
    mb1.metric("Balance Score",  f"{b_score:.1f} / 100",  f"Std Dev: {std:.1f}%")
    mb2.metric("Most Loaded",    wl_df.loc[wl_df["current_load"].idxmax(),"name"],
               f"{wl_df['current_load'].max():.0f}%", delta_color="inverse")
    mb3.metric("Most Available", wl_df.loc[wl_df["current_load"].idxmin(),"name"],
               f"{wl_df['current_load'].min():.0f}%")

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 — SKILL MATRIX HEATMAP
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="section-label">Skill Matrix</div>
<div class="section-title">Team Proficiency Heatmap</div>
""", unsafe_allow_html=True)

ews_all = get_all_employees_with_skills()
skill_rows = [
    {"Employee": ew.employee.name, "Department": ew.employee.department,
     "Skill": sk.skill_name, "Proficiency": sk.proficiency_score}
    for ew in ews_all for sk in ew.skills
]

if skill_rows:
    skill_df = pd.DataFrame(skill_rows)
    st.plotly_chart(_skill_heatmap(skill_df), width="stretch")

    with st.expander("Full Skill Matrix Table"):
        # Pure CSS color — no matplotlib, works on pandas 1.x and 2.x+
        def _color_score(val):
            if not isinstance(val, (int, float)):
                return ""
            intensity = int(val / 10 * 180)
            return f"background-color: rgb(30, {60 + intensity}, {130 + intensity//2}); color: white; font-weight: 600"
        try:
            # pandas >= 2.1 renamed applymap → map
            styled = skill_df.style.map(_color_score, subset=["Proficiency"])
        except AttributeError:
            styled = skill_df.style.applymap(_color_score, subset=["Proficiency"])
        st.dataframe(styled, width="stretch", hide_index=True)

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 — FULL TASK LOG
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="section-label">Task Log</div>
<div class="section-title">All Tasks</div>
""", unsafe_allow_html=True)

if df_all.empty:
    st.info("No tasks yet — generate a board above.")
else:
    fl1, fl2, fl3 = st.columns(3)
    with fl1:
        s_filter = st.multiselect("Status", COLUMNS, default=COLUMNS)
    with fl2:
        emp_opts = ["All"] + sorted(df_all["assigned_name"].dropna().unique().tolist())
        e_filter = st.selectbox("Assignee", emp_opts)
    with fl3:
        pri_opts = ["All", "Critical", "High", "Medium", "Low"]
        p_filter = st.selectbox("Priority", pri_opts)

    df_f = df_all[df_all["status"].isin(s_filter)]
    if e_filter != "All":
        df_f = df_f[df_f["assigned_name"] == e_filter]
    if p_filter != "All":
        df_f = df_f[df_f["priority"] == p_filter] if "priority" in df_f.columns else df_f

    show_cols = [c for c in
                 ["id","title","assigned_name","department","priority",
                  "estimated_hours","actual_hours","status","deadline"]
                 if c in df_f.columns]
    st.dataframe(
        df_f[show_cols].rename(columns={
            "id":"ID","title":"Title","assigned_name":"Assignee",
            "department":"Dept","priority":"Priority",
            "estimated_hours":"Est h","actual_hours":"Actual h",
            "status":"Status","deadline":"Deadline",
        }),
        width="stretch", hide_index=True, height=400,
    )
    st.caption(f"{len(df_f)} of {len(df_all)} tasks shown.")

# ──────────────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;padding:2rem 0 1rem;color:#334155;font-size:.8rem">
  Orchestra-Agent &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; SQLite &nbsp;·&nbsp; Streamlit
  <br>Bias-free assignment via Skill-to-Workload ratio algorithm
</div>
""", unsafe_allow_html=True)