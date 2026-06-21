import streamlit as st
import json
import os
import time
import hashlib
import hmac
import re
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="ঢাকার মিল্কী আইস বার",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
#  SECURITY CONSTANTS
# ─────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS   = 5
LOCKOUT_SECONDS      = 300
MAX_NAME_LEN         = 100
MAX_AMOUNT           = 10_000_000
SECRET_KEY           = os.environ.get("APP_SECRET", "milky-icebar-secret-2026")

LOGO_FILE = "logo.png"

# ─────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────
USERS = {
    "admin": {"password": "newaz56", "role": "admin"},
    "milky": {"password": "milky123", "role": "viewer"},
}

# ─────────────────────────────────────────────
#  DATA / PASSWORD FILES
# ─────────────────────────────────────────────
DATA_FILE = "data.json"
PASS_FILE = "passwords.json"


def _hash_pw(password: str) -> str:
    return hmac.new(SECRET_KEY.encode(), password.encode(), hashlib.sha256).hexdigest()


def _verify_pw(password: str, stored: str) -> bool:
    return hmac.compare_digest(_hash_pw(password), stored)


def load_passwords():
    if os.path.exists(PASS_FILE):
        with open(PASS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for uname, hashed in saved.items():
            if uname in USERS:
                USERS[uname]["password"] = hashed
    else:
        for u in USERS:
            USERS[u]["password"] = _hash_pw(USERS[u]["password"])
        save_passwords()


def save_passwords():
    with open(PASS_FILE, "w", encoding="utf-8") as f:
        json.dump({u: USERS[u]["password"] for u in USERS}, f, ensure_ascii=False)


def set_password(username: str, new_plain: str):
    USERS[username]["password"] = _hash_pw(new_plain)
    save_passwords()


# ─────────────────────────────────────────────
#  BRUTE-FORCE PROTECTION
# ─────────────────────────────────────────────
def _bf_key(username: str) -> str:
    return f"bf_{username}"


def check_login_allowed(username: str) -> tuple[bool, int]:
    key = _bf_key(username)
    info = st.session_state.get(key, {"attempts": 0, "locked_until": 0})
    now = time.time()
    if info["locked_until"] > now:
        remaining = int(info["locked_until"] - now)
        return False, remaining
    return True, 0


def record_failed_login(username: str):
    key = _bf_key(username)
    info = st.session_state.get(key, {"attempts": 0, "locked_until": 0})
    info["attempts"] += 1
    if info["attempts"] >= MAX_LOGIN_ATTEMPTS:
        info["locked_until"] = time.time() + LOCKOUT_SECONDS
        info["attempts"] = 0
    st.session_state[key] = info


def record_success_login(username: str):
    st.session_state.pop(_bf_key(username), None)


# ─────────────────────────────────────────────
#  INPUT SANITISATION
# ─────────────────────────────────────────────
_ALLOWED_TEXT_RE = re.compile(r"[^\w\s\u0980-\u09FF,.\-/()+]")

def sanitize_text(text: str) -> str:
    text = re.sub(r"<[^>]*>", "", text)
    text = _ALLOWED_TEXT_RE.sub("", text)
    return text[:MAX_NAME_LEN].strip()


def validate_amount(value: float) -> bool:
    return 0 < value <= MAX_AMOUNT


# ─────────────────────────────────────────────
#  DATA FILE
# ─────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if "sales" in raw or "expenses" in raw:
            yesterday = date_to_key(datetime.today() - timedelta(days=1))
            migrated = {
                "dates": {
                    yesterday: {
                        "sales": raw.get("sales", []),
                        "expenses": raw.get("expenses", []),
                    }
                }
            }
            save_data_raw(migrated)
            return migrated
        return raw
    return {"dates": {}}


def save_data_raw(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_data(data):
    save_data_raw(data)


def get_day_data(data, date_key):
    if date_key not in data["dates"]:
        data["dates"][date_key] = {"sales": [], "expenses": []}
    return data["dates"][date_key]


# ─────────────────────────────────────────────
#  DATE HELPERS
# ─────────────────────────────────────────────
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def date_to_key(d: datetime) -> str:
    return f"{d.day}/{MONTHS[d.month-1]}/{d.year}"


def get_today_key() -> str:
    return date_to_key(datetime.today())


def key_to_date(key: str) -> datetime:
    parts = key.split("/")
    day   = int(parts[0])
    month = MONTHS.index(parts[1]) + 1
    year  = int(parts[2])
    return datetime(year, month, day)


def prev_date_key(key: str) -> str:
    return date_to_key(key_to_date(key) - timedelta(days=1))


def next_date_key(key: str) -> str:
    return date_to_key(key_to_date(key) + timedelta(days=1))


def get_sorted_date_keys(data) -> list:
    keys = list(data["dates"].keys())
    return sorted(keys, key=lambda k: key_to_date(k))


def get_carry_forward(data, date_key: str) -> float:
    total = 0.0
    for k in get_sorted_date_keys(data):
        if key_to_date(k) >= key_to_date(date_key):
            break
        day = data["dates"][k]
        s = sum(x["amount"] for x in day.get("sales", []))
        e = sum(x["amount"] for x in day.get("expenses", []))
        total += (s - e)
    return total


def parse_manual_date(text: str) -> Optional[str]:
    text = bn_to_en(text.strip())
    today = datetime.today()

    patterns = [
        (r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$",   "dmy"),
        (r"^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$",    "ymd"),
        (r"^(\d{1,2})[/\-]([A-Za-z]{3})[/\-](\d{4})$","dMonY"),
        (r"^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})$",  "dMonY"),
    ]

    dt = None
    for pat, fmt in patterns:
        m = re.match(pat, text, re.IGNORECASE)
        if not m:
            continue
        try:
            if fmt == "dmy":
                dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            elif fmt == "ymd":
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif fmt == "dMonY":
                mon_str = m.group(2)[:3].capitalize()
                if mon_str not in MONTHS:
                    continue
                dt = datetime(int(m.group(3)), MONTHS.index(mon_str) + 1, int(m.group(1)))
        except ValueError:
            continue
        break

    if dt is None:
        return None
    if dt > today:
        return None
    return date_to_key(dt)


# ─────────────────────────────────────────────
#  LOGO HELPERS
# ─────────────────────────────────────────────
def load_logo_b64() -> Optional[str]:
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def save_logo(uploaded_file):
    data = uploaded_file.read()
    if data[:4] == b'\x89PNG' or data[:3] == b'\xff\xd8\xff':
        with open(LOGO_FILE, "wb") as f:
            f.write(data)
        return True
    return False


def delete_logo():
    if os.path.exists(LOGO_FILE):
        os.remove(LOGO_FILE)


# ─────────────────────────────────────────────
#  GLOBAL CSS
# ─────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@300;400;500;600;700&family=Tiro+Bangla&display=swap');

    html, body, [class*="css"] {
        font-family: 'Hind Siliguri', sans-serif !important;
        background-color: #0d1117;
        color: #e6edf3;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 0.5rem !important; }

    /* ── HEADER ── */
    .app-header {
        background: #0d1117;
        border-bottom: 1px solid rgba(0,198,255,0.12);
        margin-bottom: 20px;
        padding-bottom: 20px;
    }
    .header-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 11px 24px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        margin-bottom: 22px;
    }
    .topbar-live {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        color: rgba(255,255,255,0.28);
        letter-spacing: 2px;
        text-transform: uppercase;
        font-weight: 600;
    }
    .live-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: #3dffa0;
        animation: livepulse 2s infinite;
        flex-shrink: 0;
    }
    @keyframes livepulse {
        0%,100%{ opacity:1; box-shadow:0 0 0 0 rgba(61,255,160,0.4); }
        50%{ opacity:0.4; box-shadow:0 0 0 4px rgba(61,255,160,0); }
    }
    .topbar-badges { display:flex; align-items:center; gap:10px; }

    .header-center {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 11px;
    }
    .header-eyebrow {
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        color: rgba(255,255,255,0.2);
        font-weight: 600;
    }
    .logo-ring {
        width: 88px; height: 88px;
        border-radius: 50%;
        border: 2px solid rgba(0,198,255,0.28);
        background: rgba(0,198,255,0.05);
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    }
    .logo-ring::before {
        content: '';
        position: absolute;
        inset: -8px;
        border-radius: 50%;
        border: 1px solid rgba(0,198,255,0.08);
    }
    .logo-ring img {
        width: 72px; height: 72px;
        object-fit: contain;
        border-radius: 50%;
    }
    .logo-emoji { font-size: 38px; }
    .header-divider {
        width: 56px; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,198,255,0.45), transparent);
    }
    .brand {
        font-family: 'Tiro Bangla', serif;
        font-size: 30px;
        color: #d0f0ff;
        text-align: center;
        line-height: 1.3;
    }
    .brand span { color: #00c6ff; }
    .header-tagline {
        font-size: 12px;
        color: rgba(255,255,255,0.25);
        letter-spacing: 1.5px;
        text-align: center;
    }

    /* ── BADGES ── */
    .date-badge {
        display: inline-block;
        background: rgba(247,201,72,0.08);
        border: 1px solid rgba(247,201,72,0.22);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 12px;
        color: #f7c948;
        letter-spacing: 1px;
        font-weight: 600;
    }
    .role-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .role-admin  { background: rgba(0,198,255,0.12); color: #00c6ff; border: 1px solid rgba(0,198,255,0.28); }
    .role-viewer { background: rgba(247,201,72,0.12); color: #f7c948; border: 1px solid rgba(247,201,72,0.28); }

    /* ── SECTION TITLES ── */
    .sec-title-sales   { color: #3dffa0; font-size: 17px; font-weight: 700; letter-spacing:1px; }
    .sec-title-expense { color: #ff5e7a; font-size: 17px; font-weight: 700; letter-spacing:1px; }

    /* ── SUMMARY CARDS ── */
    .sum-row { display:flex; gap:12px; margin-bottom:18px; flex-wrap:wrap; }
    .sum-card {
        flex:1; min-width:120px;
        background:#1c2230; border:1px solid #2a3548; border-radius:14px;
        padding:14px 18px; text-align:center;
    }
    .sum-card .lbl { font-size:11px; letter-spacing:1.5px; text-transform:uppercase; color:#8b949e; }
    .sum-card .val { font-size:22px; font-weight:700; margin-top:4px; }
    .cf-card {
        flex:1; min-width:120px;
        background:linear-gradient(135deg,rgba(180,120,255,0.12),rgba(100,80,200,0.08));
        border:1px solid rgba(180,120,255,0.3); border-radius:14px;
        padding:14px 18px; text-align:center;
    }
    .cf-card .lbl { font-size:11px; letter-spacing:1.5px; text-transform:uppercase; color:#a78bfa; }
    .cf-card .val { font-size:22px; font-weight:700; margin-top:4px; }

    .c-green  { color: #3dffa0; }
    .c-red    { color: #ff5e7a; }
    .c-gold   { color: #f7c948; }
    .c-purple { color: #c084fc; }
    .c-muted  { color: #8b949e; }
    .c-blue   { color: #00c6ff; }

    /* ── CATEGORY BREAKDOWN ── */
    .cat-row {
        display:flex; align-items:center; gap:10px;
        background:#1c2230; border:1px solid #2a3548; border-radius:10px;
        padding:10px 14px; margin-bottom:8px;
    }
    .cat-row .cat-name { flex:1; font-weight:600; font-size:14px; }
    .cat-row .cat-amt   { font-weight:700; color:#ff5e7a; font-size:14px; }
    .cat-row .cat-bar-wrap { flex:2; background:#0d1117; border-radius:6px; height:8px; overflow:hidden; }
    .cat-row .cat-bar { height:100%; background:linear-gradient(90deg,#ff5e7a,#ff8fa3); border-radius:6px; }
    .cat-pill {
        display:inline-block; background:rgba(0,198,255,0.1); border:1px solid rgba(0,198,255,0.25);
        color:#00c6ff; font-size:11px; padding:2px 10px; border-radius:12px; font-weight:600; margin-left:6px;
    }

    /* ── DATE NAV ── */
    .date-nav {
        display:flex; align-items:center; justify-content:center;
        gap:10px; margin-bottom:18px;
        background:#1c2230; border:1px solid #2a3548;
        border-radius:14px; padding:10px 18px;
    }
    .date-nav .cur-date { font-size:16px; font-weight:700; color:#f7c948; min-width:140px; text-align:center; }
    .date-nav .today-tag {
        background:rgba(61,255,160,0.12); border:1px solid rgba(61,255,160,0.3);
        color:#3dffa0; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600;
    }

    /* ── TABLES ── */
    .row-header {
        display:flex; align-items:center; background:#161b22;
        border-bottom:1px solid #2a3548; padding:7px 4px;
        font-size:11px; letter-spacing:1.5px; text-transform:uppercase;
        color:#8b949e; font-weight:600; border-radius:8px 8px 0 0;
    }
    .row-item {
        display:flex; align-items:center;
        padding:8px 4px; border-bottom:1px solid rgba(42,53,72,0.4); font-size:14px;
    }
    .row-item:hover { background:rgba(255,255,255,0.02); border-radius:4px; }
    .col-num  { width:32px; color:#8b949e; font-size:12px; flex-shrink:0; }
    .col-name { flex:1; font-weight:500; }
    .col-amt-s { width:110px; text-align:right; color:#3dffa0; font-weight:700; flex-shrink:0; padding-right:8px; }
    .col-amt-e { width:110px; text-align:right; color:#ff5e7a; font-weight:700; flex-shrink:0; padding-right:8px; }

    /* ── LOGIN ── */
    .login-wrap {
        max-width:400px; margin:80px auto 0;
        background:#1c2230; border:1px solid #2a3548;
        border-radius:20px; padding:38px 32px 30px; text-align:center;
    }
    .login-wrap .login-title { font-family:'Tiro Bangla',serif; font-size:22px; color:#d0f0ff; margin-bottom:6px; }
    .login-wrap .login-sub   { font-size:13px; color:#8b949e; margin-bottom:24px; }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        background:#0d1117 !important; color:#e6edf3 !important;
        border:1px solid #2a3548 !important; border-radius:8px !important;
    }
    div[data-testid="stButton"] button {
        border-radius:10px !important;
        font-family:'Hind Siliguri',sans-serif !important;
        font-size:15px !important; font-weight:600 !important;
    }
    div[data-testid="stAlert"] { border-radius:10px !important; }
    .empty-msg { text-align:center; color:#8b949e; font-style:italic; padding:24px; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  LOGIN PAGE
# ─────────────────────────────────────────────
def login_page():
    logo_b64 = load_logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="width:72px;height:72px;object-fit:contain;border-radius:50%;'
        f'border:2px solid rgba(0,198,255,0.4);margin-bottom:6px;" alt="logo">'
        if logo_b64
        else '<div style="font-size:44px;margin-bottom:6px">🍦</div>'
    )
    st.markdown(f"""
    <div class="login-wrap">
        {logo_html}
        <div class="login-title">ঢাকার মিল্কী আইস বার</div>
        <div class="login-sub">আপনার অ্যাকাউন্টে লগইন করুন</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        username = st.text_input("👤 ইউজারনেম", placeholder="username লিখুন", max_chars=30)
        password = st.text_input("🔒 পাসওয়ার্ড", type="password", placeholder="password লিখুন", max_chars=100)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔑  লগইন করুন", use_container_width=True):
            username = username.strip().lower()
            allowed, remaining = check_login_allowed(username)
            if not allowed:
                st.error(f"🔒 অনেকবার ভুল চেষ্টা! {remaining} সেকেন্ড পর আবার চেষ্টা করুন।")
                return

            if username in USERS and _verify_pw(password, USERS[username]["password"]):
                record_success_login(username)
                st.session_state.logged_in  = True
                st.session_state.username   = username
                st.session_state.role       = USERS[username]["role"]
                st.rerun()
            else:
                record_failed_login(username)
                _, remaining2 = check_login_allowed(username)
                if remaining2 > 0:
                    st.error(f"❌ অনেকবার ভুল চেষ্টা! {remaining2} সেকেন্ড পর আবার চেষ্টা করুন।")
                else:
                    st.error("❌ ইউজারনেম বা পাসওয়ার্ড ভুল!")


# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
def render_header(viewing_date_key: str):
    role       = st.session_state.get("role", "viewer")
    role_label = "অ্যাডমিন" if role == "admin" else "ভিউয়ার"
    role_class = "role-admin" if role == "admin" else "role-viewer"
    logo_b64   = load_logo_b64()

    if logo_b64:
        logo_inner = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="width:72px;height:72px;object-fit:contain;border-radius:50%;" alt="logo">'
        )
    else:
        logo_inner = '<span class="logo-emoji">🍦</span>'

    st.markdown(f"""
    <div class="app-header">

      <div class="header-topbar">
        <div class="topbar-live">
          <span class="live-dot"></span>
          লাইভ ট্র্যাকিং চালু
        </div>
        <div class="topbar-badges">
          <span class="date-badge">📅 {viewing_date_key}</span>
          <span class="role-badge {role_class}">{'🔑' if role == 'admin' else '👁️'} {role_label}</span>
        </div>
      </div>

      <div class="header-center">
        <div class="header-eyebrow">ঢাকা · বাংলাদেশ</div>
        <div class="logo-ring">{logo_inner}</div>
        <div class="header-divider"></div>
        <div class="brand">ঢাকার <span>মিল্কী</span> আইস বার</div>
        <div class="header-tagline">প্রতিদিনের হিসাব — এক নজরে</div>
      </div>

    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  DATE NAVIGATION
# ─────────────────────────────────────────────
def render_date_nav(data):
    today_key = get_today_key()
    if "viewing_date" not in st.session_state:
        st.session_state["viewing_date"] = today_key

    cur      = st.session_state["viewing_date"]
    is_today = (cur == today_key)

    col_prev, col_mid, col_next, col_today = st.columns([1, 3, 1, 1])

    with col_prev:
        if st.button("◀ আগের দিন", use_container_width=True, key="nav_prev"):
            st.session_state["viewing_date"] = prev_date_key(cur)
            st.rerun()

    with col_mid:
        today_badge = '<span class="today-tag">আজকের দিন</span>' if is_today else ""
        st.markdown(f"""
        <div class="date-nav">
            <span class="cur-date">📅 {cur}</span>
            {today_badge}
        </div>""", unsafe_allow_html=True)

    with col_next:
        if not is_today:
            if st.button("পরের দিন ▶", use_container_width=True, key="nav_next"):
                nxt = next_date_key(cur)
                if key_to_date(nxt) <= datetime.today():
                    st.session_state["viewing_date"] = nxt
                st.rerun()

    with col_today:
        if not is_today:
            if st.button("🏠 আজকে", use_container_width=True, key="nav_today"):
                st.session_state["viewing_date"] = today_key
                st.rerun()

    with st.expander("📆 নির্দিষ্ট তারিখে যান", expanded=False):
        st.markdown(
            "<p style='font-size:12px;color:#8b949e;margin:0 0 6px'>ফরম্যাট: DD/MM/YYYY বা DD-MM-YYYY বা DD/Jan/2025</p>",
            unsafe_allow_html=True,
        )
        mc1, mc2 = st.columns([3, 1])
        with mc1:
            manual_input = st.text_input(
                "তারিখ লিখুন",
                placeholder="যেমন: 05/06/2025 বা 5-Jun-2025",
                label_visibility="collapsed",
                max_chars=20,
                key="manual_date_input",
            )
        with mc2:
            if st.button("✅ যান", use_container_width=True, key="manual_date_go"):
                if manual_input.strip():
                    parsed = parse_manual_date(manual_input)
                    if parsed:
                        st.session_state["viewing_date"] = parsed
                        st.rerun()
                    else:
                        st.error("❌ ভুল ফরম্যাট বা ভবিষ্যতের তারিখ!")

    return st.session_state["viewing_date"]


# ─────────────────────────────────────────────
#  SUMMARY BAR
# ─────────────────────────────────────────────
def render_summary(data, date_key: str):
    day           = get_day_data(data, date_key)
    total_sales   = sum(s["amount"] for s in day["sales"])
    total_expense = sum(e["amount"] for e in day["expenses"])
    today_net     = total_sales - total_expense
    carry_fwd     = get_carry_forward(data, date_key)
    grand_total   = carry_fwd + today_net

    profit_class = "c-gold" if today_net >= 0 else "c-red"
    profit_label = "আজকের লাভ" if today_net >= 0 else "আজকের ক্ষতি"
    profit_sign  = "" if today_net >= 0 else "-"

    grand_class  = "c-green" if grand_total >= 0 else "c-red"
    grand_label  = "সর্বমোট লাভ" if grand_total >= 0 else "সর্বমোট ক্ষতি"
    grand_sign   = "" if grand_total >= 0 else "-"
    cf_sign      = "" if carry_fwd >= 0 else "-"
    cf_color     = "c-purple" if carry_fwd >= 0 else "c-red"

    sorted_keys = get_sorted_date_keys(data)
    has_history = any(key_to_date(k) < key_to_date(date_key) for k in sorted_keys)

    if has_history:
        st.markdown(f"""
        <div class="sum-row">
            <div class="sum-card">
                <div class="lbl">মোট বিক্রি</div>
                <div class="val c-green">৳ {total_sales:,.0f}</div>
            </div>
            <div class="sum-card">
                <div class="lbl">মোট খরচ</div>
                <div class="val c-red">৳ {total_expense:,.0f}</div>
            </div>
            <div class="sum-card">
                <div class="lbl">{profit_label}</div>
                <div class="val {profit_class}">{profit_sign}৳ {abs(today_net):,.0f}</div>
            </div>
            <div class="cf-card">
                <div class="lbl">🔄 ক্যারি ফরওয়ার্ড</div>
                <div class="val {cf_color}">{cf_sign}৳ {abs(carry_fwd):,.0f}</div>
            </div>
            <div class="sum-card">
                <div class="lbl">🏆 {grand_label}</div>
                <div class="val {grand_class}">{grand_sign}৳ {abs(grand_total):,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        lbl2 = "লাভ" if today_net >= 0 else "ক্ষতি"
        sgn2 = "" if today_net >= 0 else "-"
        pc2  = "c-gold" if today_net >= 0 else "c-red"
        st.markdown(f"""
        <div class="sum-row">
            <div class="sum-card">
                <div class="lbl">মোট বিক্রি</div>
                <div class="val c-green">৳ {total_sales:,.0f}</div>
            </div>
            <div class="sum-card">
                <div class="lbl">মোট খরচ</div>
                <div class="val c-red">৳ {total_expense:,.0f}</div>
            </div>
            <div class="sum-card">
                <div class="lbl">{lbl2}</div>
                <div class="val {pc2}">{sgn2}৳ {abs(today_net):,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  EXPENSE CATEGORY BREAKDOWN
# ─────────────────────────────────────────────
def render_category_breakdown(data, date_key: str):
    day = get_day_data(data, date_key)
    rows = day["expenses"]
    if not rows:
        return

    totals = {}
    for e in rows:
        cat = e.get("category", "অন্যান্য")
        totals[cat] = totals.get(cat, 0) + e["amount"]

    if not totals:
        return

    max_amt = max(totals.values()) if totals else 1
    sorted_cats = sorted(totals.items(), key=lambda x: -x[1])

    with st.expander("📊 ক্যাটাগরি অনুযায়ী খরচ", expanded=False):
        for cat, amt in sorted_cats:
            pct = (amt / max_amt) * 100 if max_amt else 0
            st.markdown(f"""
            <div class="cat-row">
                <span class="cat-name">{cat}</span>
                <div class="cat-bar-wrap"><div class="cat-bar" style="width:{pct:.0f}%"></div></div>
                <span class="cat-amt">৳ {amt:,.0f}</span>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  TABLE CSS + CONTEXT MENU (right-click / long-press)
# ─────────────────────────────────────────────
ROW_HEADER_CSS = """<style>
.row-header{display:flex;align-items:center;background:#161b22;border-bottom:1px solid #2a3548;padding:7px 4px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#8b949e;font-weight:600;border-radius:8px 8px 0 0}
.row-item{display:flex;align-items:center;padding:8px 4px;border-bottom:1px solid rgba(42,53,72,0.4);font-size:14px;position:relative;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
.row-item:hover{background:rgba(0,198,255,0.05);border-radius:4px}
.col-num{width:32px;color:#8b949e;font-size:12px;flex-shrink:0}
.col-name{flex:1;font-weight:500}
.col-amt-s{width:110px;text-align:right;color:#3dffa0;font-weight:700;flex-shrink:0;padding-right:8px}
.col-amt-e{width:110px;text-align:right;color:#ff5e7a;font-weight:700;flex-shrink:0;padding-right:8px}
.row-edit-hint{font-size:10px;color:#4a5568;text-align:right;margin:-4px 4px 6px 0;letter-spacing:0.3px}

/* ── context menu popup ── */
.ctx-menu{
    position:fixed; z-index:9999; display:none;
    background:#1c2230; border:1px solid rgba(0,198,255,0.35); border-radius:12px;
    box-shadow:0 10px 30px rgba(0,0,0,0.5); padding:6px; min-width:150px;
}
.ctx-menu.open{ display:flex; flex-direction:column; gap:2px; }
.ctx-menu a{
    display:flex; align-items:center; gap:8px; padding:9px 12px; border-radius:8px;
    color:#e6edf3; text-decoration:none; font-size:13px; font-weight:600;
}
.ctx-menu a:hover{ background:rgba(0,198,255,0.12); }
.ctx-menu a.danger{ color:#ff5e7a; }
.ctx-menu a.danger:hover{ background:rgba(255,94,122,0.12); }
.ctx-menu-overlay{
    position:fixed; inset:0; z-index:9998; display:none;
}
.ctx-menu-overlay.open{ display:block; }
</style>

<div id="milky-ctx-overlay" class="ctx-menu-overlay" onclick="milkyCloseCtxMenu()"></div>
<div id="milky-ctx-menu" class="ctx-menu"></div>

<script>
(function(){
    if (window.milkyCtxInit) { return; }
    window.milkyCtxInit = true;

    window.milkyCloseCtxMenu = function(){
        var m = document.getElementById('milky-ctx-menu');
        var o = document.getElementById('milky-ctx-overlay');
        if(m){ m.classList.remove('open'); }
        if(o){ o.classList.remove('open'); }
    };

    window.milkyOpenCtxMenu = function(x, y, editHref, delHref){
        var m = document.getElementById('milky-ctx-menu');
        var o = document.getElementById('milky-ctx-overlay');
        if(!m || !o){ return; }
        m.innerHTML =
            '<a href="' + editHref + '" target="_self">✏️ এডিট করুন</a>' +
            '<a href="' + delHref + '" target="_self" class="danger">🗑️ ডিলিট করুন</a>';
        var vw = window.innerWidth, vh = window.innerHeight;
        var mw = 160, mh = 90;
        if(x + mw > vw){ x = vw - mw - 10; }
        if(y + mh > vh){ y = vh - mh - 10; }
        m.style.left = x + 'px';
        m.style.top  = y + 'px';
        m.classList.add('open');
        o.classList.add('open');
    };

    document.addEventListener('contextmenu', function(e){
        var row = e.target.closest('.row-item[data-edit][data-del]');
        if(!row){ return; }
        e.preventDefault();
        window.milkyOpenCtxMenu(e.clientX, e.clientY, row.getAttribute('data-edit'), row.getAttribute('data-del'));
    });

    var pressTimer = null;
    var startX = 0, startY = 0;
    document.addEventListener('touchstart', function(e){
        var row = e.target.closest('.row-item[data-edit][data-del]');
        if(!row){ return; }
        var touch = e.touches[0];
        startX = touch.clientX; startY = touch.clientY;
        pressTimer = setTimeout(function(){
            window.milkyOpenCtxMenu(startX, startY, row.getAttribute('data-edit'), row.getAttribute('data-del'));
            if(navigator.vibrate){ navigator.vibrate(30); }
        }, 500);
    }, {passive:true});
    document.addEventListener('touchmove', function(){
        if(pressTimer){ clearTimeout(pressTimer); pressTimer = null; }
    }, {passive:true});
    document.addEventListener('touchend', function(){
        if(pressTimer){ clearTimeout(pressTimer); pressTimer = null; }
    }, {passive:true});
})();
</script>
"""


# ─────────────────────────────────────────────
#  SALES TABLE
# ─────────────────────────────────────────────
def _qp_url(**params) -> str:
    encoded = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())
    return f"?{encoded}"


def render_sales_table(data, date_key, is_admin):
    day = get_day_data(data, date_key)
    st.markdown('<p class="sec-title-sales">🟢 বিক্রি</p>', unsafe_allow_html=True)
    st.markdown(ROW_HEADER_CSS, unsafe_allow_html=True)
    rows = day["sales"]
    if rows:
        if is_admin:
            st.markdown(
                '<p class="row-edit-hint">💡 ডান-ক্লিক করুন (মোবাইলে চেপে ধরুন) এডিট/ডিলিটের জন্য</p>',
                unsafe_allow_html=True,
            )
        st.markdown("""<div class="row-header">
            <span class="col-num">#</span>
            <span class="col-name">নাম</span>
            <span class="col-amt-s">টাকা</span>
        </div>""", unsafe_allow_html=True)
        for i, s in enumerate(rows):
            if is_admin:
                edit_href = _qp_url(action="edit", type="sale", date=date_key, idx=i)
                del_href  = _qp_url(action="delete", type="sale", date=date_key, idx=i)
                st.markdown(f"""<div class="row-item" data-edit="{edit_href}" data-del="{del_href}">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{s['name']}</span>
                    <span class="col-amt-s">৳ {s['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)
                if st.session_state.get("edit_target") == ("sale", date_key, i):
                    render_sale_edit_form(data, date_key, i)
            else:
                st.markdown(f"""<div class="row-item">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{s['name']}</span>
                    <span class="col-amt-s">৳ {s['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<p class="empty-msg">কোনো বিক্রি যোগ হয়নি</p>', unsafe_allow_html=True)


def render_sale_edit_form(data, date_key, idx):
    day = get_day_data(data, date_key)
    if idx >= len(day["sales"]):
        return
    item = day["sales"][idx]
    with st.container(border=True):
        st.markdown(f"<p style='color:#00c6ff;font-weight:700;font-size:13px;margin-bottom:8px'>✏️ এডিট করুন — বিক্রি #{idx+1}</p>", unsafe_allow_html=True)
        new_name = st.text_input("নাম", value=item["name"], key=f"edit_sale_name_{date_key}_{idx}", max_chars=MAX_NAME_LEN)
        new_amount_raw = st.text_input("টাকা", value=f"{item['amount']:.0f}", key=f"edit_sale_amt_{date_key}_{idx}", max_chars=20)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ সেভ করুন", use_container_width=True, key=f"edit_sale_save_{date_key}_{idx}"):
                clean_name = sanitize_text(new_name)
                parsed_amt = parse_amount(new_amount_raw)
                if clean_name and parsed_amt:
                    day["sales"][idx] = {"name": clean_name, "amount": parsed_amt}
                    save_data(data)
                    st.session_state.pop("edit_target", None)
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.warning("সঠিক নাম ও টাকার পরিমাণ দিন!")
        with c2:
            if st.button("✕ বাতিল", use_container_width=True, key=f"edit_sale_cancel_{date_key}_{idx}"):
                st.session_state.pop("edit_target", None)
                st.query_params.clear()
                st.rerun()


# ─────────────────────────────────────────────
#  EXPENSE TABLE (with category tag)
# ─────────────────────────────────────────────
def render_expense_table(data, date_key, is_admin):
    day = get_day_data(data, date_key)
    st.markdown('<p class="sec-title-expense">🔴 খরচ</p>', unsafe_allow_html=True)
    st.markdown(ROW_HEADER_CSS, unsafe_allow_html=True)
    rows = day["expenses"]
    if rows:
        if is_admin:
            st.markdown(
                '<p class="row-edit-hint">💡 ডান-ক্লিক করুন (মোবাইলে চেপে ধরুন) এডিট/ডিলিটের জন্য</p>',
                unsafe_allow_html=True,
            )
        st.markdown("""<div class="row-header">
            <span class="col-num">#</span>
            <span class="col-name">বিবরণ</span>
            <span class="col-amt-e">টাকা</span>
        </div>""", unsafe_allow_html=True)
        for i, e in enumerate(rows):
            cat = e.get("category", "অন্যান্য")
            desc_text = e.get("desc", "").strip()
            name_html = f"{desc_text}<span class=\"cat-pill\">{cat}</span>" if desc_text else f"<span class=\"cat-pill\">{cat}</span>"
            if is_admin:
                edit_href = _qp_url(action="edit", type="exp", date=date_key, idx=i)
                del_href  = _qp_url(action="delete", type="exp", date=date_key, idx=i)
                st.markdown(f"""<div class="row-item" data-edit="{edit_href}" data-del="{del_href}">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{name_html}</span>
                    <span class="col-amt-e">৳ {e['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)
                if st.session_state.get("edit_target") == ("exp", date_key, i):
                    render_expense_edit_form(data, date_key, i)
            else:
                st.markdown(f"""<div class="row-item">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{name_html}</span>
                    <span class="col-amt-e">৳ {e['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<p class="empty-msg">কোনো খরচ যোগ হয়নি</p>', unsafe_allow_html=True)


def render_expense_edit_form(data, date_key, idx):
    day = get_day_data(data, date_key)
    if idx >= len(day["expenses"]):
        return
    item = day["expenses"][idx]
    with st.container(border=True):
        st.markdown(f"<p style='color:#ff5e7a;font-weight:700;font-size:13px;margin-bottom:8px'>✏️ এডিট করুন — খরচ #{idx+1}</p>", unsafe_allow_html=True)

        categories = load_categories()
        current_cat = item.get("category", "অন্যান্য")
        cat_options = categories + [ADD_NEW_LABEL]
        default_idx = cat_options.index(current_cat) if current_cat in cat_options else 0
        selected_cat = st.selectbox("ক্যাটাগরি", cat_options, index=default_idx, key=f"edit_exp_cat_{date_key}_{idx}")

        new_cat_name = ""
        if selected_cat == ADD_NEW_LABEL:
            new_cat_name = st.text_input("নতুন ক্যাটাগরির নাম", placeholder="যেমন: প্যাকেজিং", key=f"edit_exp_new_cat_{date_key}_{idx}", max_chars=40)

        new_desc = st.text_input("বিবরণ (ঐচ্ছিক)", value=item.get("desc", ""), key=f"edit_exp_desc_{date_key}_{idx}", max_chars=MAX_NAME_LEN)
        new_amount_raw = st.text_input("টাকা", value=f"{item['amount']:.0f}", key=f"edit_exp_amt_{date_key}_{idx}", max_chars=20)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ সেভ করুন", use_container_width=True, key=f"edit_exp_save_{date_key}_{idx}"):
                if selected_cat == ADD_NEW_LABEL:
                    final_cat = sanitize_text(new_cat_name)
                else:
                    final_cat = selected_cat
                parsed_amt = parse_amount(new_amount_raw)
                clean_desc = sanitize_text(new_desc) if new_desc.strip() else ""

                if parsed_amt and final_cat:
                    if selected_cat == ADD_NEW_LABEL:
                        add_category_if_new(final_cat)
                    day["expenses"][idx] = {"desc": clean_desc, "amount": parsed_amt, "category": final_cat}
                    save_data(data)
                    st.session_state.pop("edit_target", None)
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.warning("সঠিক ক্যাটাগরি ও টাকার পরিমাণ দিন!")
        with c2:
            if st.button("✕ বাতিল", use_container_width=True, key=f"edit_exp_cancel_{date_key}_{idx}"):
                st.session_state.pop("edit_target", None)
                st.query_params.clear()
                st.rerun()


# ─────────────────────────────────────────────
#  BANGLA ↔ ENGLISH NUMBER
# ─────────────────────────────────────────────
def bn_to_en(text: str) -> str:
    return text.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))


def parse_amount(raw: str) -> Optional[float]:
    cleaned = bn_to_en(raw.strip().replace(",", "").replace("৳", "").replace(" ", ""))
    try:
        val = float(cleaned)
        if val > 0 and validate_amount(val):
            return val
        return None
    except ValueError:
        return None


# ─────────────────────────────────────────────
#  EXPENSE CATEGORIES (preset + custom)
# ─────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    "নাস্তা",
    "জেনারেটর ও অন্যান্য",
    "ক্যামিকেল",
    "প্যাকেট ও বক্স",
    "মার্কেটিং",
    "গাড়ি মেরামত",
    "মাছ ও মাংস",
    "গ্যাস, তেল ও চাল",
    "মালাই এর মশলা",
    "বিদ্যুৎ বিল",
    "সরঞ্জাম",
    "ঘর ভাড়া",
    "বেতন",
    "অন্যান্য",
]
CATEGORY_FILE = "categories.json"
ADD_NEW_LABEL = "➕ নতুন ক্যাটাগরি যোগ করুন..."


def load_categories() -> list:
    if os.path.exists(CATEGORY_FILE):
        try:
            with open(CATEGORY_FILE, "r", encoding="utf-8") as f:
                cats = json.load(f)
            if isinstance(cats, list) and cats:
                # ensure defaults always present, no duplicates, preserve order
                merged = list(dict.fromkeys(DEFAULT_CATEGORIES + cats))
                return merged
        except (json.JSONDecodeError, OSError):
            pass
    save_categories(DEFAULT_CATEGORIES)
    return list(DEFAULT_CATEGORIES)


def save_categories(cats: list):
    with open(CATEGORY_FILE, "w", encoding="utf-8") as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)


def add_category_if_new(cat_name: str) -> list:
    cats = load_categories()
    if cat_name not in cats:
        # keep "অন্যান্য" at the end
        if "অন্যান্য" in cats:
            cats.remove("অন্যান্য")
            cats.append(cat_name)
            cats.append("অন্যান্য")
        else:
            cats.append(cat_name)
        save_categories(cats)
    return cats


# ─────────────────────────────────────────────
#  ADMIN INPUT FORMS
# ─────────────────────────────────────────────
def render_admin_inputs(data, date_key):
    today_key = get_today_key()
    if date_key != today_key:
        st.markdown("""
        <div style="background:rgba(247,201,72,0.08);border:1px solid rgba(247,201,72,0.25);
        border-radius:10px;padding:12px 18px;color:#f7c948;font-size:13px;text-align:center;margin-top:12px;">
        ⚠️ পুরনো তারিখে নতুন এন্ট্রি যোগ করা যাবে না। আজকের তারিখে ফিরে যান।
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("---")
    st.markdown(
        "<p style='font-size:12px;color:#8b949e;margin-bottom:4px'>"
        "💡 টাকার ঘরে বাংলা (যেমন: ৫০০) বা ইংরেজি (500) দুটোই লেখা যাবে।"
        "</p>", unsafe_allow_html=True,
    )

    if "sale_counter" not in st.session_state: st.session_state["sale_counter"] = 0
    if "exp_counter"  not in st.session_state: st.session_state["exp_counter"]  = 0
    if "exp_new_cat_mode" not in st.session_state: st.session_state["exp_new_cat_mode"] = False

    sc = st.session_state["sale_counter"]
    ec = st.session_state["exp_counter"]

    col_s, col_e = st.columns(2)

    with col_s:
        st.markdown("#### ➕ নতুন বিক্রি যোগ করুন")
        sale_name       = st.text_input("নাম", placeholder="যেমন: আইস বার, কুলফি...", key=f"sale_name_{sc}", max_chars=MAX_NAME_LEN)
        sale_amount_raw = st.text_input("টাকা", placeholder="যেমন: ৫০০ বা 500", key=f"sale_amt_{sc}", max_chars=20)

        parsed_sale = parse_amount(sale_amount_raw) if sale_amount_raw.strip() else None
        if sale_amount_raw.strip() and parsed_sale is None:
            st.caption("⚠️ সঠিক সংখ্যা লিখুন (সর্বোচ্চ ১ কোটি)")
        elif parsed_sale:
            st.caption(f"✅ পরিমাণ: ৳ {parsed_sale:,.0f}")

        if st.button("✅  বিক্রি যোগ করুন", use_container_width=True, key="add_sale_btn"):
            clean_name = sanitize_text(sale_name)
            if clean_name and parsed_sale:
                day = get_day_data(data, date_key)
                day["sales"].append({"name": clean_name, "amount": parsed_sale})
                save_data(data)
                st.session_state["sale_counter"] += 1
                st.rerun()
            else:
                st.warning("নাম ও সঠিক টাকার পরিমাণ দিন!")

    with col_e:
        st.markdown("#### ➕ নতুন খরচ যোগ করুন")

        categories = load_categories()
        cat_options = categories + [ADD_NEW_LABEL]
        selected_cat = st.selectbox("ক্যাটাগরি", cat_options, key=f"exp_cat_{ec}")

        new_cat_name = ""
        if selected_cat == ADD_NEW_LABEL:
            new_cat_name = st.text_input(
                "নতুন ক্যাটাগরির নাম",
                placeholder="যেমন: প্যাকেজিং",
                key=f"exp_new_cat_{ec}",
                max_chars=40,
            )

        exp_desc = st.text_input(
            "বিবরণ (ঐচ্ছিক)",
            placeholder="যেমন: ৫ কেজি চাল কেনা... (নাও লিখতে পারেন)",
            key=f"exp_desc_{ec}",
            max_chars=MAX_NAME_LEN,
        )

        exp_amount_raw  = st.text_input("টাকা", placeholder="যেমন: ২৫০ বা 250", key=f"exp_amt_{ec}", max_chars=20)

        parsed_exp = parse_amount(exp_amount_raw) if exp_amount_raw.strip() else None
        if exp_amount_raw.strip() and parsed_exp is None:
            st.caption("⚠️ সঠিক সংখ্যা লিখুন (সর্বোচ্চ ১ কোটি)")
        elif parsed_exp:
            st.caption(f"✅ পরিমাণ: ৳ {parsed_exp:,.0f}")

        if st.button("✅  খরচ যোগ করুন", use_container_width=True, key="add_exp_btn"):
            clean_desc = sanitize_text(exp_desc) if exp_desc.strip() else ""

            if selected_cat == ADD_NEW_LABEL:
                final_cat = sanitize_text(new_cat_name)
            else:
                final_cat = selected_cat

            if parsed_exp and final_cat:
                if selected_cat == ADD_NEW_LABEL:
                    add_category_if_new(final_cat)
                day = get_day_data(data, date_key)
                day["expenses"].append({"desc": clean_desc, "amount": parsed_exp, "category": final_cat})
                save_data(data)
                st.session_state["exp_counter"] += 1
                st.rerun()
            elif selected_cat == ADD_NEW_LABEL and not final_cat:
                st.warning("নতুন ক্যাটাগরির নাম দিন!")
            else:
                st.warning("ক্যাটাগরি ও সঠিক টাকার পরিমাণ দিন!")


# ─────────────────────────────────────────────
#  CATEGORY MANAGEMENT (admin)
# ─────────────────────────────────────────────
def render_category_manager():
    st.markdown("---")
    st.markdown("#### 🏷️ খরচের ক্যাটাগরি ম্যানেজমেন্ট")

    categories = load_categories()

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(
            "<p style='font-size:13px;color:#8b949e;margin-bottom:8px'>বর্তমান ক্যাটাগরি সমূহ</p>",
            unsafe_allow_html=True,
        )
        for cat in categories:
            is_default = cat in DEFAULT_CATEGORIES
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"<div class='cat-pill' style='margin:3px 0'>{cat}</div>", unsafe_allow_html=True)
            with c2:
                if not is_default:
                    if st.button("✕", key=f"del_cat_{cat}"):
                        categories.remove(cat)
                        save_categories(categories)
                        st.rerun()

    with col_r:
        st.markdown(
            "<p style='font-size:13px;color:#8b949e;margin-bottom:8px'>নতুন ক্যাটাগরি যোগ করুন</p>",
            unsafe_allow_html=True,
        )
        if "cat_mgr_counter" not in st.session_state:
            st.session_state["cat_mgr_counter"] = 0
        cmc = st.session_state["cat_mgr_counter"]
        new_cat = st.text_input("ক্যাটাগরির নাম", placeholder="যেমন: প্যাকেজিং", key=f"cat_mgr_input_{cmc}", max_chars=40)
        if st.button("➕ যোগ করুন", key="cat_mgr_add_btn"):
            clean = sanitize_text(new_cat)
            if clean:
                if clean in categories:
                    st.warning("এই ক্যাটাগরি আগে থেকেই আছে!")
                else:
                    add_category_if_new(clean)
                    st.session_state["cat_mgr_counter"] += 1
                    st.success(f"✅ '{clean}' ক্যাটাগরি যোগ হয়েছে!")
                    st.rerun()
            else:
                st.warning("ক্যাটাগরির নাম দিন!")


# ─────────────────────────────────────────────
#  LOGO MANAGEMENT
# ─────────────────────────────────────────────
def render_logo_manager():
    st.markdown("---")
    st.markdown("#### 🖼️ লোগো ম্যানেজমেন্ট")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(
            "<p style='font-size:13px;color:#8b949e;margin-bottom:8px'>"
            "PNG বা JPEG ফাইল আপলোড করুন (সর্বোচ্চ 2 MB)</p>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "লোগো আপলোড করুন",
            type=["png", "jpg", "jpeg"],
            key="logo_upload",
            label_visibility="collapsed",
        )
        if uploaded:
            if uploaded.size > 2 * 1024 * 1024:
                st.error("❌ ফাইল সাইজ ২ MB এর বেশি হতে পারবে না!")
            else:
                if save_logo(uploaded):
                    st.success("✅ লোগো সফলভাবে আপলোড হয়েছে!")
                    st.rerun()
                else:
                    st.error("❌ শুধু PNG বা JPEG ফাইল গ্রহণযোগ্য!")

    with col_r:
        if os.path.exists(LOGO_FILE):
            b64 = load_logo_b64()
            st.markdown(
                f'<img src="data:image/png;base64,{b64}" style="width:100px;border-radius:12px;border:1px solid #2a3548">',
                unsafe_allow_html=True,
            )
            if st.button("🗑️ লোগো মুছুন", key="del_logo_btn"):
                delete_logo()
                st.success("✅ লোগো মুছে ফেলা হয়েছে!")
                st.rerun()
        else:
            st.markdown('<p class="empty-msg">কোনো লোগো নেই</p>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  PASSWORD RESET
# ─────────────────────────────────────────────
def render_password_reset():
    st.markdown("---")
    st.markdown("#### 🔐 পাসওয়ার্ড পরিবর্তন করুন")

    if "pw_counter" not in st.session_state:
        st.session_state["pw_counter"] = 0
    pc = st.session_state["pw_counter"]

    col_a, col_v = st.columns(2)

    def _pw_section(col, label, color, uname, btn_key, title_key):
        with col:
            st.markdown(
                f'<div style="background:#1c2230;border:1px solid #2a3548;border-radius:12px;padding:16px 18px;">'
                f'<p style="color:{color};font-weight:700;margin-bottom:12px;font-size:14px">{label}</p>',
                unsafe_allow_html=True,
            )
            new_pw  = st.text_input("নতুন পাসওয়ার্ড", type="password", key=f"new_{title_key}_{pc}", placeholder="নতুন পাসওয়ার্ড লিখুন", max_chars=100)
            conf_pw = st.text_input("নিশ্চিত করুন",   type="password", key=f"conf_{title_key}_{pc}", placeholder="আবার লিখুন",           max_chars=100)
            if st.button(f"✅ {label} সেট করুন", use_container_width=True, key=btn_key):
                if not new_pw:
                    st.warning("পাসওয়ার্ড খালি রাখা যাবে না!")
                elif len(new_pw) < 6:
                    st.warning("পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে!")
                elif new_pw != conf_pw:
                    st.error("পাসওয়ার্ড দুটো মিলছে না!")
                else:
                    set_password(uname, new_pw)
                    st.session_state["pw_counter"] += 1
                    st.success(f"✅ {label} পরিবর্তন হয়েছে!")
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    _pw_section(col_a, "🔑 অ্যাডমিন পাসওয়ার্ড", "#00c6ff", "admin", "save_admin_pw", "admin_pw")
    _pw_section(col_v, "👁️ ভিউয়ার পাসওয়ার্ড",  "#f7c948", "milky", "save_view_pw",  "view_pw")


# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
def handle_row_actions(data, is_admin):
    if not is_admin:
        return
    qp = st.query_params
    action = qp.get("action")
    if not action:
        return

    item_type = qp.get("type")
    date_param = qp.get("date")
    idx_param  = qp.get("idx")

    if item_type not in ("sale", "exp") or date_param is None or idx_param is None:
        st.query_params.clear()
        return

    try:
        idx = int(idx_param)
    except ValueError:
        st.query_params.clear()
        return

    if date_param not in data["dates"]:
        st.query_params.clear()
        return

    day = data["dates"][date_param]
    list_key = "sales" if item_type == "sale" else "expenses"
    rows = day.get(list_key, [])

    if idx < 0 or idx >= len(rows):
        st.query_params.clear()
        return

    if action == "delete":
        rows.pop(idx)
        save_data(data)
        st.query_params.clear()
        st.rerun()
    elif action == "edit":
        st.session_state["edit_target"] = (item_type, date_param, idx)
        st.session_state["viewing_date"] = date_param
        st.query_params.clear()


def main():
    inject_css()
    load_passwords()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
        return

    data     = load_data()
    is_admin = st.session_state.role == "admin"

    handle_row_actions(data, is_admin)

    if not is_admin:
        st.markdown("""<style>
        [data-testid="stToolbar"],[data-testid="manage-app-button"],
        div[class*="StatusWidget"],div[class*="viewerBadge"],
        .stDeployButton,#stDecoration,header[data-testid="stHeader"]
        { display:none !important; visibility:hidden !important; }
        </style>""", unsafe_allow_html=True)

    # ── session এ date আগে সেট করি যাতে header ঠিকঠাক দেখায় ──
    today_key = get_today_key()
    if "viewing_date" not in st.session_state:
        st.session_state["viewing_date"] = today_key

    # ── HEADER সবার আগে ──
    render_header(st.session_state["viewing_date"])

    # ── Logout button ──
    if is_admin:
        _, _, logout_col = st.columns([6, 1, 1])
        with logout_col:
            if st.button("🚪 লগআউট"):
                for k in ["logged_in", "username", "role", "viewing_date"]:
                    st.session_state.pop(k, None)
                st.rerun()
    else:
        _, _, logout_col = st.columns([8, 1, 1])
        with logout_col:
            if st.button("🚪 বের হন", key="viewer_logout"):
                for k in ["logged_in", "username", "role", "viewing_date"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ── Date navigation (header এর পরে) ──
    date_key = render_date_nav(data)

    # ── Summary ──
    render_summary(data, date_key)

    # ── Category breakdown ──
    render_category_breakdown(data, date_key)

    # ── Tables ──
    col_left, col_right = st.columns(2)
    with col_left:
        render_sales_table(data, date_key, is_admin)
    with col_right:
        render_expense_table(data, date_key, is_admin)

    # ── Admin only ──
    if is_admin:
        render_admin_inputs(data, date_key)
        render_category_manager()
        render_logo_manager()
        render_password_reset()


if __name__ == "__main__":
    main()
