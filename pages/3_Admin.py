"""
pages/3_Admin.py  ·  Orchestra-Agent  ·  Admin CRUD Panel
===========================================================
This page replaces hard-coded seed data entirely.
Managers/admins can:
  - Add / edit / delete employees
  - Add / edit / delete skills per employee
  - Set proficiency scores visually
  - See the live Skill Matrix heatmap update in real time

No code changes required — ever.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
from database import (
    init_db, get_all_employees, get_skills_for_employee,
    create_employee, update_employee, delete_employee,
    upsert_skill, delete_skill, get_all_employees_with_skills,
    get_all_users, create_user, update_user, delete_user,
    update_user_password,
)
from auth import (
    require_auth, render_user_widget, ROLE_ADMIN, ROLE_MANAGER,
    ROLE_EMPLOYEE, hash_password, verify_password,
)

st.set_page_config(
    page_title="Admin — Orchestra-Agent",
    page_icon="O",
    layout="wide",
)
init_db()

user = require_auth(ROLE_ADMIN)

# ── Design tokens (same system) ────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{
    background:#0a0e1a!important;color:#f1f5f9!important;
    font-family:'Inter','Segoe UI',system-ui,sans-serif;}
[data-testid="stSidebar"]{background:#0d1117!important;border-right:1px solid #1e293b;}
[data-testid="stSidebar"] *{color:#cbd5e1!important;}
h1,h2,h3{color:#f1f5f9!important;}
hr{border-color:#1e293b!important;}
.sec-tag{display:inline-block;font-size:.68rem;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;color:#60a5fa;
  background:rgba(59,130,246,.1);border:1px solid rgba(59,130,246,.25);
  border-radius:6px;padding:3px 10px;margin-bottom:.5rem;}
.sec-title{font-size:1.35rem;font-weight:700;margin:0 0 1.2rem;}
.emp-card{background:#111827;border:1px solid #1e293b;border-radius:18px;
  padding:1.1rem 1.3rem;margin-bottom:.7rem;
  transition:border-color .2s;}
.emp-card:hover{border-color:#3b82f6;}
[data-testid="stButton"]>button{
  background:linear-gradient(135deg,#3b82f6,#6366f1)!important;
  border:none!important;border-radius:11px!important;
  color:white!important;font-weight:700!important;}
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"]>div>div,
[data-testid="stNumberInput"] input{
  background:#0d1117!important;border:1px solid #1e293b!important;
  border-radius:10px!important;color:#f1f5f9!important;}
[data-testid="stExpander"]{background:#111827;border:1px solid #1e293b;
  border-radius:16px;overflow:hidden;}
.danger-btn>button{
  background:#7f1d1d!important;color:#fca5a5!important;}
</style>
""", unsafe_allow_html=True)

DEPARTMENTS = ["Engineering","Design","QA","DevOps","Product","Data","Marketing","Other"]
ALL_SKILLS  = sorted([
    "Python","React","TypeScript","CSS","Figma","FastAPI","Django",
    "PostgreSQL","SQL","Docker","Kubernetes","CI/CD","Terraform",
    "Machine Learning","Pytest","Selenium","Accessibility","Node.js",
    "GraphQL","Redis","AWS","GCP","Azure","Java","Go","Rust",
])

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Admin Panel")
    st.markdown("<span style='color:#64748b;font-size:.8rem'>Team & Skill Management</span>",
                unsafe_allow_html=True)
    st.divider()
    render_user_widget()
    st.divider()
    if st.button("Home", use_container_width=True):
        st.switch_page("app.py")
    st.divider()
    employees = get_all_employees()
    st.markdown(f"**{len(employees)}** employees in database")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0f172a,#1e1b4b,#1e3a5f);
  border:1px solid #3b82f6;border-radius:22px;padding:2rem 2.5rem;margin-bottom:1.8rem">
  <div class="sec-tag">Admin</div>
  <h1 style="font-size:1.9rem;font-weight:800;background:linear-gradient(90deg,#60a5fa,#a78bfa);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;margin:.3rem 0 .2rem">Team & Skill Matrix</h1>
  <p style="color:#64748b;margin:0;font-size:.9rem">
    Add, edit, or remove employees and skills — no code changes required.
  </p>
</div>
""", unsafe_allow_html=True)

tab_list, tab_add, tab_skills, tab_matrix, tab_users = st.tabs([
    "  Employee List  ",
    "  Add Employee  ",
    "  Manage Skills  ",
    "  Skill Matrix  ",
    "  User Accounts  ",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — EMPLOYEE LIST (Read + Edit + Delete)
# ══════════════════════════════════════════════════════════════════════════════

with tab_list:
    st.markdown('<div class="sec-tag">Employees</div>'
                '<div class="sec-title">All Team Members</div>', unsafe_allow_html=True)

    employees = get_all_employees()
    if not employees:
        st.info("No employees yet. Add one in the 'Add Employee' tab.")
    else:
        for emp in employees:
            with st.expander(
                f"{emp['name']}  ·  {emp['department']}  ·  Load: {emp['current_load']:.0f}%"
            ):
                ec1, ec2 = st.columns([3, 1])
                with ec1:
                    new_name = st.text_input("Name",  value=emp["name"],
                                             key=f"n_{emp['id']}")
                    new_dept = st.selectbox("Department", DEPARTMENTS,
                                            index=DEPARTMENTS.index(emp["department"])
                                            if emp["department"] in DEPARTMENTS else 0,
                                            key=f"d_{emp['id']}")
                    new_load = st.slider("Current Load %", 0, 100,
                                         int(emp["current_load"]),
                                         key=f"l_{emp['id']}")
                with ec2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("Save", key=f"save_{emp['id']}", use_container_width=True):
                        update_employee(emp["id"], new_name, new_dept, float(new_load))
                        st.success("Updated!")
                        st.rerun()
                    st.markdown('<div class="danger-btn">', unsafe_allow_html=True)
                    if st.button("Delete", key=f"del_{emp['id']}", use_container_width=True):
                        delete_employee(emp["id"])
                        st.warning(f"Deleted {emp['name']}")
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                # Skills preview for this employee
                skills = get_skills_for_employee(emp["id"])
                if skills:
                    skill_pills = " ".join(
                        f'<span style="background:#1e3a5f;color:#60a5fa;'
                        f'border-radius:6px;padding:2px 9px;font-size:.72rem;'
                        f'margin:2px;display:inline-block">'
                        f'{s["skill_name"]} ({s["proficiency_score"]})</span>'
                        for s in skills
                    )
                    st.markdown(
                        f'<div style="margin-top:.6rem">{skill_pills}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("No skills assigned yet.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ADD EMPLOYEE
# ══════════════════════════════════════════════════════════════════════════════

with tab_add:
    st.markdown('<div class="sec-tag">New Employee</div>'
                '<div class="sec-title">Add Team Member</div>', unsafe_allow_html=True)

    with st.form("add_emp_form", clear_on_submit=True):
        fa1, fa2 = st.columns(2)
        with fa1:
            a_name = st.text_input("Full Name *", placeholder="e.g. Jane Smith")
        with fa2:
            a_dept = st.selectbox("Department *", DEPARTMENTS)
        a_load = st.slider("Starting Workload %", 0, 100, 0)

        st.markdown("---")
        st.markdown("**Initial Skills** *(optional — add more in Manage Skills tab)*")

        sk1, sk2, sk3 = st.columns(3)
        init_skills = []
        for i, col in enumerate([sk1, sk2, sk3]):
            with col:
                sk = st.selectbox(f"Skill {i+1}", ["— none —"] + ALL_SKILLS,
                                  key=f"is_{i}")
                sc = st.slider(f"Proficiency", 1, 10, 5, key=f"isc_{i}")
                if sk != "— none —":
                    init_skills.append((sk, sc))

        submitted = st.form_submit_button("Add Employee", use_container_width=True)
        if submitted:
            if not a_name.strip():
                st.error("Name is required.")
            else:
                try:
                    new_id = create_employee(a_name, a_dept, float(a_load))
                    for sk_name, sk_score in init_skills:
                        upsert_skill(new_id, sk_name, sk_score)
                    st.success(f"Added **{a_name}** to the team! (ID: {new_id})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — MANAGE SKILLS (per employee)
# ══════════════════════════════════════════════════════════════════════════════

with tab_skills:
    st.markdown('<div class="sec-tag">Skills</div>'
                '<div class="sec-title">Manage Skills per Employee</div>',
                unsafe_allow_html=True)

    employees = get_all_employees()
    if not employees:
        st.info("Add an employee first.")
    else:
        sel_emp = st.selectbox(
            "Select employee",
            options=[e["id"] for e in employees],
            format_func=lambda eid: next(
                e["name"] for e in employees if e["id"] == eid),
        )

        cur_skills = get_skills_for_employee(sel_emp)
        emp_name   = next(e["name"] for e in employees if e["id"] == sel_emp)
        st.markdown(f"#### {emp_name}'s Skills  "
                    f"<span style='color:#64748b;font-size:.85rem'>"
                    f"({len(cur_skills)} skills)</span>", unsafe_allow_html=True)

        # Existing skills — editable inline
        if cur_skills:
            for sk in cur_skills:
                sc1, sc2, sc3 = st.columns([3, 2, 1])
                with sc1:
                    st.markdown(
                        f"<div style='padding:.45rem 0;font-size:.9rem;color:#f1f5f9'>"
                        f"{sk['skill_name']}</div>", unsafe_allow_html=True)
                with sc2:
                    new_score = st.slider(
                        "Score", 1, 10, sk["proficiency_score"],
                        key=f"sk_sc_{sk['id']}",
                        label_visibility="collapsed",
                    )
                with sc3:
                    col_save, col_del = st.columns(2)
                    with col_save:
                        if st.button("Save", key=f"sk_save_{sk['id']}",
                                     use_container_width=True):
                            upsert_skill(sel_emp, sk["skill_name"], new_score)
                            st.rerun()
                    with col_del:
                        st.markdown('<div class="danger-btn">',
                                    unsafe_allow_html=True)
                        if st.button("Del", key=f"sk_del_{sk['id']}",
                                     use_container_width=True):
                            delete_skill(sk["id"])
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("No skills yet.")

        st.divider()

        # Add new skill
        st.markdown("**Add a skill**")
        ns1, ns2, ns3 = st.columns([3, 2, 1])
        with ns1:
            existing_names = {s["skill_name"] for s in cur_skills}
            available = [s for s in ALL_SKILLS if s not in existing_names]
            new_skill_name = st.selectbox("Skill", ["— select —"] + available,
                                          key="new_sk_name")
        with ns2:
            new_skill_score = st.slider("Proficiency", 1, 10, 7, key="new_sk_score")
        with ns3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Add Skill", use_container_width=True, key="add_sk"):
                if new_skill_name != "— select —":
                    upsert_skill(sel_emp, new_skill_name, new_skill_score)
                    st.success(f"Added {new_skill_name}!")
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SKILL MATRIX HEATMAP (live preview)
# ══════════════════════════════════════════════════════════════════════════════

with tab_matrix:
    st.markdown('<div class="sec-tag">Preview</div>'
                '<div class="sec-title">Live Skill Matrix Heatmap</div>',
                unsafe_allow_html=True)

    ews_all = get_all_employees_with_skills()
    rows = [
        {"Employee": ew.employee.name, "Skill": sk.skill_name,
         "Score": sk.proficiency_score}
        for ew in ews_all for sk in ew.skills
    ]

    if rows:
        df_pivot = pd.DataFrame(rows).pivot_table(
            index="Employee", columns="Skill", values="Score", fill_value=0)

        fig = px.imshow(
            df_pivot,
            color_continuous_scale=[[0,"#0d1117"],[0.4,"#1e3a5f"],[1,"#3b82f6"]],
            aspect="auto",
            labels=dict(color="Proficiency (1-10)"),
        )
        fig.update_layout(
            plot_bgcolor="#111827", paper_bgcolor="#111827",
            font=dict(color="#94a3b8", size=11),
            margin=dict(l=10,r=10,t=20,b=10), height=380,
        )
        fig.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        st.plotly_chart(fig, width="stretch")

        st.caption("This matrix is what the Matchmaker node uses for bias-free assignment. "
                   "Higher proficiency score = higher weighting in the algorithm.")
    else:
        st.info("Add employees and skills to see the matrix.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — USER ACCOUNTS (Create · Edit · Delete · Change Password)
# ══════════════════════════════════════════════════════════════════════════════

with tab_users:
    st.markdown('<div class="sec-tag">Users</div>'
                '<div class="sec-title">User Account Management</div>',
                unsafe_allow_html=True)

    ROLES       = [ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE]
    ROLE_COLORS_MAP = {
        ROLE_ADMIN:    ("#ef4444", "#fca5a5"),
        ROLE_MANAGER:  ("#3b82f6", "#93c5fd"),
        ROLE_EMPLOYEE: ("#6366f1", "#a5b4fc"),
    }
    all_users     = get_all_users()
    all_employees = get_all_employees()
    emp_opts      = {e["name"]: e["id"] for e in all_employees}

    # ── Existing users ─────────────────────────────────────────────────────────
    st.markdown("#### Existing Accounts")
    if not all_users:
        st.info("No user accounts yet.")
    else:
        for u in all_users:
            role_bg, role_fg = ROLE_COLORS_MAP.get(u["role"], ("#334155","#94a3b8"))
            badge = (f'<span style="background:{role_bg}22;color:{role_fg};'
                     f'border:1px solid {role_bg}44;border-radius:6px;'
                     f'font-size:.65rem;font-weight:700;letter-spacing:.07em;'
                     f'text-transform:uppercase;padding:2px 8px">{u["role"]}</span>')
            linked = f"→ {u['employee_name']}" if u.get("employee_name") else ""

            with st.expander(
                f"{u['display_name']}  (@{u['username']})  {u['role'].upper()}"
                f"{'  · ' + u['employee_name'] if u.get('employee_name') else ''}"
            ):
                u1, u2 = st.columns([3, 2])
                with u1:
                    new_display = st.text_input("Display Name",
                                                value=u["display_name"],
                                                key=f"u_dn_{u['id']}")
                    new_role = st.selectbox("Role", ROLES,
                                            index=ROLES.index(u["role"]),
                                            key=f"u_role_{u['id']}")
                    emp_choices  = ["— none —"] + list(emp_opts.keys())
                    current_emp  = u.get("employee_name") or "— none —"
                    emp_idx      = emp_choices.index(current_emp) \
                                   if current_emp in emp_choices else 0
                    new_emp_name = st.selectbox(
                        "Linked Employee (for employee role)",
                        emp_choices, index=emp_idx,
                        key=f"u_emp_{u['id']}",
                        help="Link this account to an employee record so "
                             "the My Tasks page shows their tasks automatically."
                    )
                    new_emp_id = emp_opts.get(new_emp_name) \
                                 if new_emp_name != "— none —" else None

                with u2:
                    st.markdown(f"""
<div style="background:#0d1117;border:1px solid #1e293b;border-radius:12px;
  padding:.9rem 1rem;font-size:.78rem;color:#64748b;margin-top:.2rem">
  <div style="margin-bottom:.4rem">{badge}</div>
  <div>Username: <strong style="color:#f1f5f9">@{u['username']}</strong></div>
  <div>Last login: <span style="color:#475569">
    {u['last_login'][:10] if u.get('last_login') else 'never'}</span></div>
  <div>Created: <span style="color:#475569">
    {u['created_at'][:10] if u.get('created_at') else '—'}</span></div>
</div>""", unsafe_allow_html=True)

                sb1, sb2, sb3 = st.columns(3)
                with sb1:
                    if st.button("Save Changes", key=f"u_save_{u['id']}",
                                 use_container_width=True):
                        update_user(u["id"], new_display, new_role, new_emp_id)
                        st.success("Updated!")
                        st.rerun()
                with sb2:
                    # Change password inline
                    with st.popover("Change Password", use_container_width=True):
                        np1 = st.text_input("New password", type="password",
                                            key=f"np1_{u['id']}")
                        np2 = st.text_input("Confirm",     type="password",
                                            key=f"np2_{u['id']}")
                        if st.button("Set Password", key=f"set_pw_{u['id']}",
                                     use_container_width=True):
                            if not np1:
                                st.error("Password cannot be empty.")
                            elif np1 != np2:
                                st.error("Passwords do not match.")
                            elif len(np1) < 6:
                                st.error("Minimum 6 characters.")
                            else:
                                update_user_password(u["id"], hash_password(np1))
                                st.success("Password updated!")
                with sb3:
                    if u["username"] != "admin":  # protect default admin
                        st.markdown('<div class="danger-btn">',
                                    unsafe_allow_html=True)
                        if st.button("Delete", key=f"u_del_{u['id']}",
                                     use_container_width=True):
                            delete_user(u["id"])
                            st.warning(f"Deleted @{u['username']}")
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.caption("Protected account")

    st.divider()

    # ── Add new user ───────────────────────────────────────────────────────────
    st.markdown("#### Add New Account")
    with st.form("add_user_form", clear_on_submit=True):
        nu1, nu2 = st.columns(2)
        with nu1:
            nu_username = st.text_input("Username *",
                                        placeholder="e.g. alice_chen")
            nu_display  = st.text_input("Display Name *",
                                        placeholder="e.g. Alice Chen")
        with nu2:
            nu_role = st.selectbox("Role", ROLES, index=2)
            emp_choices2 = ["— none —"] + list(emp_opts.keys())
            nu_emp_name  = st.selectbox(
                "Linked Employee",
                emp_choices2,
                help="Required for Employee role — gives access to their tasks."
            )
        nu_password = st.text_input("Password *", type="password",
                                    placeholder="Minimum 6 characters")
        nu_confirm  = st.text_input("Confirm Password *", type="password")

        submitted = st.form_submit_button("Create Account",
                                          use_container_width=True)
        if submitted:
            errors = []
            if not nu_username.strip():  errors.append("Username required.")
            if not nu_display.strip():   errors.append("Display name required.")
            if not nu_password:          errors.append("Password required.")
            elif len(nu_password) < 6:   errors.append("Password ≥ 6 characters.")
            elif nu_password != nu_confirm: errors.append("Passwords do not match.")
            if nu_role == ROLE_EMPLOYEE and nu_emp_name == "— none —":
                errors.append("Employee accounts must be linked to an employee record.")
            if errors:
                for e in errors: st.error(e)
            else:
                nu_emp_id = emp_opts.get(nu_emp_name) \
                            if nu_emp_name != "— none —" else None
                try:
                    create_user(
                        username     = nu_username.strip(),
                        password_hash= hash_password(nu_password),
                        display_name = nu_display.strip(),
                        role         = nu_role,
                        employee_id  = nu_emp_id,
                    )
                    st.success(f"Account @{nu_username} created!")
                    st.rerun()
                except Exception as e:
                    if "UNIQUE" in str(e):
                        st.error(f"Username '@{nu_username}' already exists.")
                    else:
                        st.error(f"Error: {e}")

    st.markdown("""
<div style="margin-top:1.5rem;padding:1rem 1.2rem;background:rgba(239,68,68,.06);
  border:1px solid rgba(239,68,68,.2);border-radius:12px;font-size:.78rem;color:#64748b">
  <strong style="color:#f87171;display:block;margin-bottom:.4rem">
    Security reminder</strong>
  Change the default admin/manager passwords immediately after first login.<br>
  Employee accounts require a linked employee record to see their tasks.
</div>""", unsafe_allow_html=True)