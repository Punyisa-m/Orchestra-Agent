"""
auth.py  ·  Orchestra-Agent  ·  Authentication Layer
======================================================
Design decisions:
  - PBKDF2-SHA256 with 310,000 iterations (NIST 2023 recommendation)
    and a per-user random salt. Zero external dependencies — stdlib only.
  - Session stored in st.session_state (in-memory, per-browser tab).
    On page refresh Streamlit re-runs from top, so we check session
    state at the start of every page.
  - Three roles:
      admin    → all pages including Admin CRUD
      manager  → Manager Dashboard + view team
      employee → My Tasks only (sees only own data)
  - require_auth(role) is a one-liner guard at the top of every page.

Production note:
  For a real multi-user deployment swap session_state for a signed
  JWT stored in a secure httpOnly cookie (streamlit-cookies-manager).
  The auth.py interface stays the same — only the storage backend changes.
"""

import hashlib
import hmac
import secrets
import base64
import streamlit as st
from typing import Optional

# ── Role constants ─────────────────────────────────────────────────────────────
ROLE_ADMIN    = "admin"
ROLE_MANAGER  = "manager"
ROLE_EMPLOYEE = "employee"

ROLE_HIERARCHY = {ROLE_ADMIN: 3, ROLE_MANAGER: 2, ROLE_EMPLOYEE: 1}

ROLE_COLORS = {
    ROLE_ADMIN:    ("#ef4444", "#fca5a5"),   # red
    ROLE_MANAGER:  ("#3b82f6", "#93c5fd"),   # blue
    ROLE_EMPLOYEE: ("#6366f1", "#a5b4fc"),   # indigo
}

ROLE_HOME_PAGE = {
    ROLE_ADMIN:    "pages/3_Admin.py",
    ROLE_MANAGER:  "pages/1_Manager.py",
    ROLE_EMPLOYEE: "pages/2_My_Tasks.py",
}


# ── Password hashing ───────────────────────────────────────────────────────────

_ITERATIONS = 310_000
_ALGO       = "sha256"

def hash_password(plain: str) -> str:
    """
    Returns a self-contained string:  salt$hash
    Both parts are base64-encoded so the whole thing is storable as TEXT.
    """
    salt   = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac(_ALGO, plain.encode(), salt, _ITERATIONS)
    return (base64.b64encode(salt).decode() + "$" +
            base64.b64encode(digest).decode())


def verify_password(plain: str, stored: str) -> bool:
    """Constant-time comparison — prevents timing attacks."""
    try:
        salt_b64, hash_b64 = stored.split("$", 1)
        salt   = base64.b64decode(salt_b64)
        stored_hash = base64.b64decode(hash_b64)
        check  = hashlib.pbkdf2_hmac(_ALGO, plain.encode(), salt, _ITERATIONS)
        return hmac.compare_digest(stored_hash, check)
    except Exception:
        return False


# ── Session helpers ────────────────────────────────────────────────────────────

def _s() -> dict:
    """Return the auth sub-dict from session_state, init if missing."""
    if "auth" not in st.session_state:
        st.session_state["auth"] = {
            "logged_in":   False,
            "user_id":     None,
            "username":    None,
            "display_name": None,
            "role":        None,
            "employee_id": None,   # set for employee role
        }
    return st.session_state["auth"]


def is_logged_in() -> bool:
    return _s().get("logged_in", False)


def current_user() -> Optional[dict]:
    s = _s()
    if not s.get("logged_in"):
        return None
    return {k: s[k] for k in
            ("user_id","username","display_name","role","employee_id")}


def login(user_row: dict) -> None:
    """Called after password verification passes — writes session."""
    s = _s()
    s["logged_in"]    = True
    s["user_id"]      = user_row["id"]
    s["username"]     = user_row["username"]
    s["display_name"] = user_row["display_name"]
    s["role"]         = user_row["role"]
    s["employee_id"]  = user_row.get("employee_id")


def logout() -> None:
    st.session_state["auth"] = {
        "logged_in": False, "user_id": None, "username": None,
        "display_name": None, "role": None, "employee_id": None,
    }


# ── Page guard ─────────────────────────────────────────────────────────────────

def require_auth(min_role: str = ROLE_EMPLOYEE) -> dict:
    """
    Call at the top of every page. Redirects to login if not authenticated
    or if user's role is below the required minimum.

    Usage:
        user = require_auth(ROLE_MANAGER)
        # code below only runs if user is manager or admin
    """
    if not is_logged_in():
        st.switch_page("app.py")
        st.stop()

    user = current_user()
    if ROLE_HIERARCHY.get(user["role"], 0) < ROLE_HIERARCHY.get(min_role, 0):
        _show_unauthorized(user["role"], min_role)
        st.stop()

    return user


def _show_unauthorized(actual: str, required: str) -> None:
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:#0a0e1a!important;color:#f1f5f9!important;}
</style>""", unsafe_allow_html=True)
    st.markdown(f"""
<div style="max-width:480px;margin:8rem auto;text-align:center">
  <div style="font-size:3rem;margin-bottom:1rem">&#128683;</div>
  <h2 style="color:#f1f5f9">Access Denied</h2>
  <p style="color:#64748b">
    This page requires <strong style="color:#f87171">{required}</strong> role.<br>
    You are signed in as <strong style="color:#94a3b8">{actual}</strong>.
  </p>
</div>""", unsafe_allow_html=True)
    if st.button("Go Home"):
        st.switch_page("app.py")


# ── Sidebar user widget ────────────────────────────────────────────────────────

def render_user_widget() -> None:
    """
    Drop this into the sidebar of every page.
    Shows avatar, name, role badge, and logout button.
    """
    user = current_user()
    if not user:
        return

    role   = user["role"]
    bg, fg = ROLE_COLORS.get(role, ("#334155", "#94a3b8"))
    name   = user["display_name"] or user["username"]
    inits  = "".join(p[0].upper() for p in name.split()[:2])

    st.sidebar.markdown(f"""
<div style="background:#111827;border:1px solid #1e293b;border-radius:16px;
            padding:1.1rem;margin-bottom:.8rem;text-align:center">
  <div style="width:46px;height:46px;border-radius:50%;margin:0 auto .6rem;
    background:linear-gradient(135deg,{bg},{fg});
    display:flex;align-items:center;justify-content:center;
    font-weight:700;font-size:1rem;color:white">{inits}</div>
  <div style="font-weight:700;color:#f1f5f9;font-size:.95rem">{name}</div>
  <div style="margin-top:.4rem">
    <span style="background:{bg}22;color:{fg};border:1px solid {bg}44;
      border-radius:6px;font-size:.65rem;font-weight:700;
      letter-spacing:.08em;text-transform:uppercase;
      padding:2px 9px">{role}</span>
  </div>
</div>""", unsafe_allow_html=True)

    if st.sidebar.button("Sign Out", use_container_width=True, key="logout_btn"):
        logout()
        st.switch_page("app.py")