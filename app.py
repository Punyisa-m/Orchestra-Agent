"""
app.py  ·  Orchestra-Agent  ·  Home / Navigation Hub
======================================================
Streamlit multi-page apps work by placing extra pages inside a
`pages/` folder next to app.py. Streamlit auto-discovers them and
adds them to the sidebar. This file is the entry point / home screen.

Page structure:
  app.py                   →  Home (this file)
  pages/1_Manager.py       →  Manager Dashboard (Kanban + AI planner)
  pages/2_My_Tasks.py      →  Employee View (personal Kanban + calendar)
"""

import streamlit as st
from database import init_db, get_all_employees, get_workload_distribution
import pandas as pd

st.set_page_config(
    page_title="Orchestra-Agent",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ── Global design tokens injected once ────────────────────────────────────────
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a !important; color: #f1f5f9 !important;
    font-family: 'Inter','Segoe UI',system-ui,sans-serif;
}
[data-testid="stSidebar"] { background: #0d1117 !important; border-right:1px solid #1e293b; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
h1,h2,h3 { color: #f1f5f9 !important; }
hr { border-color: #1e293b !important; }
[data-testid="stButton"] > button {
    background: linear-gradient(135deg,#3b82f6,#6366f1) !important;
    border:none !important; border-radius:14px !important;
    color:white !important; font-weight:700 !important;
    padding:.65rem 2rem !important;
}
[data-testid="stButton"] > button:hover { opacity:.88 !important; }
.nav-card {
    background: #111827; border: 1px solid #1e293b;
    border-radius: 24px; padding: 2.4rem 2rem;
    text-align: center; cursor: pointer;
    transition: border-color .2s, transform .15s;
    height: 100%;
}
.nav-card:hover { border-color: #3b82f6; transform: translateY(-3px); }
.nav-icon {
    width:60px; height:60px; border-radius:18px; margin: 0 auto 1.2rem;
    display:flex; align-items:center; justify-content:center;
    font-size:1.6rem;
}
.nav-card h3 { color:#f1f5f9; margin:.4rem 0; font-size:1.2rem; }
.nav-card p  { color:#64748b; font-size:.85rem; line-height:1.6; margin:0; }
.chip {
    display:inline-block; padding:3px 12px; border-radius:20px;
    font-size:.72rem; font-weight:700; text-transform:uppercase;
    letter-spacing:.06em; margin-top:1rem;
}
.chip-blue   { background:rgba(59,130,246,.15);  color:#60a5fa; border:1px solid rgba(59,130,246,.3); }
.chip-indigo { background:rgba(99,102,241,.15);  color:#818cf8; border:1px solid rgba(99,102,241,.3); }
.stat-row { display:flex; gap:1rem; justify-content:center; margin-top:.8rem; }
.stat-pill { background:#1e293b; border-radius:20px; padding:4px 14px;
             font-size:.75rem; color:#94a3b8; }
.stat-pill span { color:#60a5fa; font-weight:700; }
</style>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#1e3a5f 100%);
            border:1px solid #3b82f6; border-radius:24px; padding:3rem;
            margin-bottom:2rem; text-align:center; position:relative; overflow:hidden;">
  <div style="position:absolute;top:-80px;right:-80px;width:300px;height:300px;
              background:radial-gradient(circle,rgba(99,102,241,.2) 0%,transparent 70%);
              border-radius:50%;"></div>
  <div style="font-size:.75rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;
              color:#60a5fa;background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.2);
              border-radius:6px;display:inline-block;padding:3px 14px;margin-bottom:1rem;">
    AI-Powered Task Manager
  </div>
  <h1 style="font-size:3rem;font-weight:800;background:linear-gradient(90deg,#60a5fa,#a78bfa);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             background-clip:text;margin:.4rem 0;">Orchestra-Agent</h1>
  <p style="color:#94a3b8;font-size:1.05rem;max-width:540px;margin:0 auto;">
    From a single sentence to a fully assigned, scheduled team board — automatically.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Navigation cards ───────────────────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;margin-bottom:1.5rem'>Where do you want to go?</h2>",
            unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
<div class="nav-card">
  <div class="nav-icon" style="background:linear-gradient(135deg,#1e3a5f,#1e293b);">
    <span style="font-size:1.8rem;">&#9783;</span>
  </div>
  <h3>Manager Dashboard</h3>
  <p>Generate AI task plans, assign work via the Skill Matrix,
     manage the team Kanban board, and monitor workload distribution.</p>
  <div class="chip chip-blue">For Team Leads</div>
</div>""", unsafe_allow_html=True)
    if st.button("Open Manager Dashboard", key="go_mgr", use_container_width=True):
        st.switch_page("pages/1_Manager.py")

with c2:
    st.markdown("""
<div class="nav-card">
  <div class="nav-icon" style="background:linear-gradient(135deg,#2d1b4b,#1e293b);">
    <span style="font-size:1.8rem;">&#128197;</span>
  </div>
  <h3>My Tasks</h3>
  <p>See only your own assignments. Track progress on a personal Kanban,
     view your schedule on a calendar, and log actual hours per task.</p>
  <div class="chip chip-indigo">For Team Members</div>
</div>""", unsafe_allow_html=True)
    if st.button("Open My Tasks", key="go_emp", use_container_width=True):
        st.switch_page("pages/2_My_Tasks.py")

st.divider()

# ── Live team snapshot ─────────────────────────────────────────────────────────
st.markdown("<h3 style='margin-bottom:1rem'>Team Snapshot</h3>", unsafe_allow_html=True)

employees = get_all_employees()
wl_data   = get_workload_distribution()
wl_map    = {r["name"]: r for r in wl_data}

cols = st.columns(min(len(employees), 4))
for i, emp in enumerate(employees):
    wl  = wl_map.get(emp["name"], {})
    load = emp["current_load"]
    color = "#10b981" if load < 40 else "#f59e0b" if load < 70 else "#ef4444"
    tasks = wl.get("task_count", 0)

    with cols[i % 4]:
        initials = (emp["name"].split()[0][0] + emp["name"].split()[-1][0]).upper()
        st.markdown(f"""
<div style="background:#111827;border:1px solid #1e293b;border-radius:20px;
            padding:1.2rem;text-align:center;margin-bottom:.8rem">
  <div style="width:44px;height:44px;border-radius:50%;margin:0 auto .7rem;
              background:linear-gradient(135deg,#3b82f6,#6366f1);
              display:flex;align-items:center;justify-content:center;
              font-weight:700;font-size:.9rem;color:white">{initials}</div>
  <div style="font-weight:600;font-size:.9rem;color:#f1f5f9">{emp['name'].split()[0]}</div>
  <div style="font-size:.72rem;color:#475569;margin:.2rem 0 .7rem">{emp['department']}</div>
  <div style="height:5px;background:#1e293b;border-radius:10px;overflow:hidden;margin-bottom:.5rem">
    <div style="height:100%;width:{load}%;background:{color};border-radius:10px"></div>
  </div>
  <div style="font-size:.72rem;color:{color};font-weight:700">{load:.0f}% load</div>
  <div style="font-size:.7rem;color:#475569;margin-top:.25rem">{tasks} active task{'s' if tasks != 1 else ''}</div>
</div>""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:2rem 0 .5rem;color:#334155;font-size:.8rem">
  Orchestra-Agent &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; SQLite &nbsp;·&nbsp; Streamlit
</div>
""", unsafe_allow_html=True)