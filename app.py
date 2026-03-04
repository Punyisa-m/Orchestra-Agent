"""
app.py  ·  Orchestra-Agent  ·  Login Gate + Home
==================================================
Flow:
  Not logged in → show login form (full-screen, no sidebar)
  Logged in     → show home/nav hub with role-appropriate cards
"""

import streamlit as st
from database import init_db, get_all_employees, get_workload_distribution
from database import get_user_by_username, record_login
from auth import (
    verify_password, login, is_logged_in, current_user,
    render_user_widget, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE, ROLE_COLORS,
)

st.set_page_config(
    page_title="Orchestra-Agent",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="collapsed",
)
init_db()

# ── Shared CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{
  background:#0a0e1a!important;color:#f1f5f9!important;
  font-family:'Inter','Segoe UI',system-ui,sans-serif;}
[data-testid="stSidebar"]{background:#0d1117!important;border-right:1px solid #1e293b;}
[data-testid="stSidebar"] *{color:#cbd5e1!important;}
h1,h2,h3{color:#f1f5f9!important;}
hr{border-color:#1e293b!important;}
[data-testid="stButton"]>button{
  background:linear-gradient(135deg,#3b82f6,#6366f1)!important;
  border:none!important;border-radius:12px!important;
  color:white!important;font-weight:700!important;
  transition:opacity .2s,transform .15s!important;}
[data-testid="stButton"]>button:hover{opacity:.88!important;}
[data-testid="stTextInput"] input{
  background:#0d1117!important;border:1px solid #1e293b!important;
  border-radius:10px!important;color:#f1f5f9!important;font-size:.95rem!important;}
[data-testid="stTextInput"] input:focus{
  border-color:#3b82f6!important;
  box-shadow:0 0 0 3px rgba(59,130,246,.2)!important;}
.nav-card{
  background:#111827;border:1px solid #1e293b;border-radius:24px;
  padding:2.2rem 2rem;text-align:center;height:100%;
  transition:border-color .2s,transform .15s;}
.nav-card:hover{border-color:#3b82f6;transform:translateY(-3px);}
.nav-card h3{color:#f1f5f9;margin:.5rem 0 .4rem;font-size:1.15rem;}
.nav-card p{color:#64748b;font-size:.83rem;line-height:1.6;margin:0;}
.chip{display:inline-block;padding:3px 12px;border-radius:20px;
  font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;margin-top:.9rem;}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_login() -> None:
    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("""
<div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);
  border:1px solid #3b82f6;border-radius:28px;padding:3rem 2.5rem;
  margin-top:4rem;text-align:center;position:relative;overflow:hidden">
  <div style="position:absolute;top:-60px;right:-60px;width:220px;height:220px;
    background:radial-gradient(circle,rgba(99,102,241,.2) 0%,transparent 70%);
    border-radius:50%;pointer-events:none"></div>
  <div style="width:64px;height:64px;border-radius:20px;margin:0 auto 1.2rem;
    background:linear-gradient(135deg,#3b82f6,#6366f1);
    display:flex;align-items:center;justify-content:center;
    font-size:1.4rem;font-weight:900;color:white">OA</div>
  <h1 style="font-size:1.8rem;font-weight:800;
    background:linear-gradient(90deg,#60a5fa,#a78bfa);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;margin:0 0 .25rem">Orchestra-Agent</h1>
  <p style="color:#475569;font-size:.85rem;margin:0">AI-Powered Task Manager</p>
</div>
""", unsafe_allow_html=True)

        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Enter your username",
                                 key="login_user")
        password = st.text_input("Password", type="password",
                                 placeholder="Enter your password",
                                 key="login_pass")
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

        if st.button("Sign In", use_container_width=True, key="sign_in_btn"):
            if not username.strip() or not password.strip():
                st.error("Please enter both username and password.")
            else:
                user_row = get_user_by_username(username.strip())
                if user_row and verify_password(password, user_row["password_hash"]):
                    login(user_row)
                    record_login(user_row["id"])
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        st.markdown("""
<div style="margin-top:1.4rem;padding:.9rem 1.1rem;background:#0d1117;
  border:1px solid #1e293b;border-radius:12px;font-size:.74rem;color:#475569;
  line-height:1.8">
  <strong style="color:#64748b;display:block;margin-bottom:.3rem">
    Demo accounts</strong>
  admin / admin123 &nbsp;&nbsp;&#183;&nbsp;&nbsp; manager / mgr123<br>
  <span style="color:#334155;font-size:.7rem">
    Employee accounts are created in the Admin panel.</span>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_home() -> None:
    user = current_user()
    role = user["role"]
    bg, fg = ROLE_COLORS.get(role, ("#334155", "#94a3b8"))
    name = user["display_name"] or user["username"]

    with st.sidebar:
        st.markdown("### Orchestra-Agent")
        st.caption("Home")
        st.divider()
        render_user_widget()

    # Hero banner
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#1e3a5f 100%);
  border:1px solid #3b82f6;border-radius:24px;padding:2.5rem 3rem;
  margin-bottom:2rem;position:relative;overflow:hidden">
  <div style="position:absolute;top:-70px;right:-70px;width:260px;height:260px;
    background:radial-gradient(circle,rgba(99,102,241,.2) 0%,transparent 70%);
    border-radius:50%;pointer-events:none"></div>
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.14em;
    text-transform:uppercase;color:#60a5fa;background:rgba(59,130,246,.1);
    border:1px solid rgba(59,130,246,.22);border-radius:6px;
    display:inline-block;padding:3px 12px;margin-bottom:.9rem">Welcome back</div>
  <h1 style="font-size:2.2rem;font-weight:800;
    background:linear-gradient(90deg,#60a5fa,#a78bfa);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;margin:0 0 .3rem">Hello, {name}</h1>
  <p style="color:#64748b;margin:0;font-size:.92rem">
    Signed in as &nbsp;
    <span style="background:{bg}22;color:{fg};border:1px solid {bg}44;
      border-radius:6px;font-size:.68rem;font-weight:700;
      letter-spacing:.08em;text-transform:uppercase;padding:2px 9px">{role}</span>
  </p>
</div>
""", unsafe_allow_html=True)

    # Navigation cards — filtered by role
    st.markdown("<h2 style='margin-bottom:1.4rem'>Where do you want to go?</h2>",
                unsafe_allow_html=True)

    cards = []
    if role in (ROLE_MANAGER, ROLE_ADMIN):
        cards.append(dict(
            icon="&#9783;", icon_bg="linear-gradient(135deg,#1e3a5f,#1e293b)",
            title="Manager Dashboard",
            desc="Generate AI task plans, assign work via the Skill Matrix, "
                 "and monitor the full team Kanban board.",
            chip="Team Leads", chip_col="#3b82f6",
            page="pages/1_Manager.py", btn="Open Manager Dashboard", btn_key="go_mgr",
        ))
    if role in (ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_ADMIN):
        cards.append(dict(
            icon="&#128197;", icon_bg="linear-gradient(135deg,#2d1b4b,#1e293b)",
            title="My Tasks",
            desc="See your assigned tasks, track progress, view your schedule "
                 "on a calendar and Gantt timeline, and log hours.",
            chip="Team Members", chip_col="#6366f1",
            page="pages/2_My_Tasks.py", btn="Open My Tasks", btn_key="go_emp",
        ))
    if role == ROLE_ADMIN:
        cards.append(dict(
            icon="&#9881;", icon_bg="linear-gradient(135deg,#1a2a1a,#1e293b)",
            title="Admin Panel",
            desc="Manage employees, skills, and user accounts without touching code.",
            chip="Admin Only", chip_col="#10b981",
            page="pages/3_Admin.py", btn="Open Admin Panel", btn_key="go_admin",
        ))

    cols = st.columns(len(cards), gap="large")
    for col, card in zip(cols, cards):
        with col:
            st.markdown(f"""
<div class="nav-card">
  <div style="width:54px;height:54px;border-radius:16px;margin:0 auto 1rem;
    background:{card['icon_bg']};display:flex;align-items:center;
    justify-content:center;font-size:1.6rem">{card['icon']}</div>
  <h3>{card['title']}</h3>
  <p>{card['desc']}</p>
  <div class="chip" style="background:{card['chip_col']}22;
    color:{card['chip_col']};border:1px solid {card['chip_col']}44">
    {card['chip']}</div>
</div>""", unsafe_allow_html=True)
            if st.button(card["btn"], key=card["btn_key"], use_container_width=True):
                st.switch_page(card["page"])

    # Team snapshot (manager/admin only)
    if role in (ROLE_MANAGER, ROLE_ADMIN):
        st.divider()
        st.markdown("<h3 style='margin-bottom:1rem'>Team Snapshot</h3>",
                    unsafe_allow_html=True)
        employees = get_all_employees()
        wl_data   = get_workload_distribution()
        wl_map    = {r["name"]: r for r in wl_data}
        cols      = st.columns(min(len(employees), 4))
        for i, emp in enumerate(employees):
            wl    = wl_map.get(emp["name"], {})
            load  = emp["current_load"]
            color = "#10b981" if load < 40 else "#f59e0b" if load < 70 else "#ef4444"
            tasks = wl.get("task_count", 0)
            inits = (emp["name"].split()[0][0] + emp["name"].split()[-1][0]).upper()
            with cols[i % 4]:
                st.markdown(f"""
<div style="background:#111827;border:1px solid #1e293b;border-radius:20px;
  padding:1.1rem;text-align:center;margin-bottom:.7rem">
  <div style="width:40px;height:40px;border-radius:50%;margin:0 auto .5rem;
    background:linear-gradient(135deg,#3b82f6,#6366f1);
    display:flex;align-items:center;justify-content:center;
    font-weight:700;font-size:.85rem;color:white">{inits}</div>
  <div style="font-weight:600;font-size:.85rem;color:#f1f5f9">{emp['name'].split()[0]}</div>
  <div style="font-size:.68rem;color:#475569;margin:.15rem 0 .55rem">{emp['department']}</div>
  <div style="height:4px;background:#1e293b;border-radius:10px;overflow:hidden;margin-bottom:.35rem">
    <div style="height:100%;width:{load}%;background:{color};border-radius:10px"></div></div>
  <div style="font-size:.68rem;color:{color};font-weight:700">{load:.0f}%</div>
  <div style="font-size:.65rem;color:#334155;margin-top:.15rem">{tasks} task{'s' if tasks!=1 else ''}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div style="text-align:center;padding:2rem 0 .5rem;color:#1e293b;font-size:.78rem">
  Orchestra-Agent · LangGraph · SQLite · Streamlit
</div>""", unsafe_allow_html=True)


# ── Router ─────────────────────────────────────────────────────────────────────
if not is_logged_in():
    show_login()
else:
    show_home()