import streamlit as st
import json
import os
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
#  USERS
# ─────────────────────────────────────────────
USERS = {
    "admin": {"password": "newaz56", "role": "admin"},
    "milky": {"password": "milky123", "role": "viewer"},
}

# ─────────────────────────────────────────────
#  DATA FILE
# ─────────────────────────────────────────────
DATA_FILE = "data.json"
PASS_FILE = "passwords.json"


def load_passwords():
    if os.path.exists(PASS_FILE):
        with open(PASS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for uname, pwd in saved.items():
            if uname in USERS:
                USERS[uname]["password"] = pwd


def save_passwords():
    with open(PASS_FILE, "w", encoding="utf-8") as f:
        json.dump({u: USERS[u]["password"] for u in USERS}, f, ensure_ascii=False)


def load_data():
    """
    New structure:
    {
      "dates": {
        "9/Jun/2026": {"sales": [...], "expenses": [...]},
        ...
      }
    }
    Also supports legacy flat format for backward compatibility.
    On migration, data is placed under yesterday (previous day) automatically.
    """
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # ── Migrate old flat format → place under yesterday ──
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
        # ── Fix: if today's key has data that belongs to yesterday ──
        # (one-time correction stored as flag)
        return raw
    return {"dates": {}}


def save_data_raw(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_data(data):
    save_data_raw(data)


def get_day_data(data, date_key):
    """Return sales/expenses for a specific date, creating if needed."""
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
    day = int(parts[0])
    month = MONTHS.index(parts[1]) + 1
    year = int(parts[2])
    return datetime(year, month, day)


def prev_date_key(key: str) -> str:
    d = key_to_date(key)
    return date_to_key(d - timedelta(days=1))


def next_date_key(key: str) -> str:
    d = key_to_date(key)
    return date_to_key(d + timedelta(days=1))


def get_sorted_date_keys(data) -> list:
    """All date keys sorted oldest → newest."""
    keys = list(data["dates"].keys())
    return sorted(keys, key=lambda k: key_to_date(k))


def get_carry_forward(data, date_key: str) -> float:
    """
    Sum all net profit/loss from every date BEFORE date_key.
    Only dates that actually have data count.
    """
    total = 0.0
    for k in get_sorted_date_keys(data):
        if key_to_date(k) >= key_to_date(date_key):
            break
        day = data["dates"][k]
        s = sum(x["amount"] for x in day.get("sales", []))
        e = sum(x["amount"] for x in day.get("expenses", []))
        total += (s - e)
    return total


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
    .block-container { padding-top: 1rem !important; }

    .app-header {
        text-align: center;
        padding: 22px 10px 14px;
        background: linear-gradient(180deg, rgba(0,198,255,0.07) 0%, transparent 100%);
        border-bottom: 1px solid #2a3548;
        margin-bottom: 20px;
    }
    .app-header .brand {
        font-family: 'Tiro Bangla', serif;
        font-size: 30px;
        color: #d0f0ff;
        text-shadow: 0 0 28px rgba(0,198,255,0.45);
        line-height: 1.3;
    }
    .app-header .brand span { color: #00c6ff; }
    .app-header .date-badge {
        display: inline-block;
        margin-top: 8px;
        background: #1c2230;
        border: 1px solid #2a3548;
        border-radius: 20px;
        padding: 4px 16px;
        font-size: 13px;
        color: #f7c948;
        letter-spacing: 1px;
    }
    .app-header .role-badge {
        display: inline-block;
        margin-left: 10px;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .role-admin  { background: rgba(0,198,255,0.15); color: #00c6ff; border: 1px solid rgba(0,198,255,0.3); }
    .role-viewer { background: rgba(247,201,72,0.15); color: #f7c948; border: 1px solid rgba(247,201,72,0.3); }

    .sec-title-sales   { color: #3dffa0; font-size: 17px; font-weight: 700; letter-spacing:1px; }
    .sec-title-expense { color: #ff5e7a; font-size: 17px; font-weight: 700; letter-spacing:1px; }

    .sum-row {
        display: flex;
        gap: 12px;
        margin-bottom: 18px;
        flex-wrap: wrap;
    }
    .sum-card {
        flex: 1;
        min-width: 120px;
        background: #1c2230;
        border: 1px solid #2a3548;
        border-radius: 14px;
        padding: 14px 18px;
        text-align: center;
    }
    .sum-card .lbl { font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #8b949e; }
    .sum-card .val { font-size: 22px; font-weight: 700; margin-top: 4px; }

    /* Carry forward card — distinct styling */
    .cf-card {
        flex: 1;
        min-width: 120px;
        background: linear-gradient(135deg, rgba(180,120,255,0.12), rgba(100,80,200,0.08));
        border: 1px solid rgba(180,120,255,0.35);
        border-radius: 14px;
        padding: 14px 18px;
        text-align: center;
    }
    .cf-card .lbl { font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #a78bfa; }
    .cf-card .val { font-size: 22px; font-weight: 700; margin-top: 4px; }

    .c-green  { color: #3dffa0; }
    .c-red    { color: #ff5e7a; }
    .c-gold   { color: #f7c948; }
    .c-purple { color: #c084fc; }
    .c-muted  { color: #8b949e; }

    /* Date nav */
    .date-nav {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-bottom: 18px;
        background: #1c2230;
        border: 1px solid #2a3548;
        border-radius: 14px;
        padding: 10px 18px;
    }
    .date-nav .cur-date {
        font-size: 16px;
        font-weight: 700;
        color: #f7c948;
        min-width: 140px;
        text-align: center;
    }
    .date-nav .today-tag {
        background: rgba(61,255,160,0.12);
        border: 1px solid rgba(61,255,160,0.3);
        color: #3dffa0;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 600;
    }

    /* Row styles */
    .row-header {
        display: flex; align-items: center;
        background: #161b22;
        border-bottom: 1px solid #2a3548;
        padding: 7px 4px;
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #8b949e;
        font-weight: 600;
        border-radius: 8px 8px 0 0;
    }
    .row-item {
        display: flex; align-items: center;
        padding: 8px 4px;
        border-bottom: 1px solid rgba(42,53,72,0.4);
        font-size: 14px;
    }
    .row-item:hover { background: rgba(255,255,255,0.02); border-radius: 4px; }
    .col-num  { width: 32px; color: #8b949e; font-size: 12px; flex-shrink:0; }
    .col-name { flex: 1; font-weight: 500; }
    .col-amt-s { width: 110px; text-align:right; color: #3dffa0; font-weight:700; flex-shrink:0; padding-right:8px; }
    .col-amt-e { width: 110px; text-align:right; color: #ff5e7a; font-weight:700; flex-shrink:0; padding-right:8px; }

    .login-wrap {
        max-width: 400px;
        margin: 80px auto 0;
        background: #1c2230;
        border: 1px solid #2a3548;
        border-radius: 20px;
        padding: 38px 32px 30px;
        text-align: center;
    }
    .login-wrap .login-title {
        font-family: 'Tiro Bangla', serif;
        font-size: 22px;
        color: #d0f0ff;
        margin-bottom: 6px;
    }
    .login-wrap .login-sub { font-size: 13px; color: #8b949e; margin-bottom: 24px; }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        background: #0d1117 !important;
        color: #e6edf3 !important;
        border: 1px solid #2a3548 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stButton"] button {
        border-radius: 10px !important;
        font-family: 'Hind Siliguri', sans-serif !important;
        font-size: 15px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stAlert"] { border-radius: 10px !important; }

    .empty-msg { text-align: center; color: #8b949e; font-style: italic; padding: 24px; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  LOGIN PAGE
# ─────────────────────────────────────────────
def login_page():
    st.markdown("""
    <div class="login-wrap">
        <div style="font-size:44px;margin-bottom:6px">🍦</div>
        <div class="login-title">ঢাকার মিল্কী আইস বার</div>
        <div class="login-sub">আপনার অ্যাকাউন্টে লগইন করুন</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        username = st.text_input("👤 ইউজারনেম", placeholder="username লিখুন")
        password = st.text_input("🔒 পাসওয়ার্ড", type="password", placeholder="password লিখুন")
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔑  লগইন করুন", use_container_width=True):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = USERS[username]["role"]
                st.rerun()
            else:
                st.error("❌ ইউজারনেম বা পাসওয়ার্ড ভুল!")


# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
def render_header(viewing_date_key: str):
    role = st.session_state.get("role", "viewer")
    role_label = "অ্যাডমিন" if role == "admin" else "ভিউয়ার"
    role_class = "role-admin" if role == "admin" else "role-viewer"

    st.markdown(f"""
    <div class="app-header">
        <div class="brand">ঢাকার <span>মিল্কী</span> আইস বার</div>
        <div>
            <span class="date-badge">📅 {viewing_date_key}</span>
            <span class="role-badge {role_class}">{'🔑' if role=='admin' else '👁️'} {role_label}</span>
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

    cur = st.session_state["viewing_date"]
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
        </div>
        """, unsafe_allow_html=True)

    with col_next:
        # Disable going beyond today
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

    return st.session_state["viewing_date"]


# ─────────────────────────────────────────────
#  SUMMARY BAR  (with carry forward)
# ─────────────────────────────────────────────
def render_summary(data, date_key: str):
    day = get_day_data(data, date_key)
    total_sales   = sum(s["amount"] for s in day["sales"])
    total_expense = sum(e["amount"] for e in day["expenses"])
    today_net     = total_sales - total_expense
    carry_fwd     = get_carry_forward(data, date_key)
    grand_total   = carry_fwd + today_net

    profit_class = "c-gold" if today_net >= 0 else "c-red"
    profit_label = "আজকের লাভ" if today_net >= 0 else "আজকের ক্ষতি"
    profit_sign  = "" if today_net >= 0 else "-"

    grand_class = "c-green" if grand_total >= 0 else "c-red"
    grand_label = "সর্বমোট লাভ" if grand_total >= 0 else "সর্বমোট ক্ষতি"
    grand_sign  = "" if grand_total >= 0 else "-"

    cf_sign  = "" if carry_fwd >= 0 else "-"
    cf_color = "c-purple" if carry_fwd >= 0 else "c-red"

    # Only show carry forward card if there's history before this date
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
        # No history → simpler 3-card view (same as before)
        profit_class2 = "c-gold" if today_net >= 0 else "c-red"
        lbl2 = "লাভ" if today_net >= 0 else "ক্ষতি"
        sgn2 = "" if today_net >= 0 else "-"
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
                <div class="val {profit_class2}">{sgn2}৳ {abs(today_net):,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  SALES TABLE
# ─────────────────────────────────────────────
ROW_HEADER_CSS = """<style>
.row-header { display:flex;align-items:center;background:#161b22;border-bottom:1px solid #2a3548;padding:7px 4px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#8b949e;font-weight:600;border-radius:8px 8px 0 0; }
.row-item { display:flex;align-items:center;padding:8px 4px;border-bottom:1px solid rgba(42,53,72,0.4);font-size:14px; }
.row-item:hover { background:rgba(255,255,255,0.02);border-radius:4px; }
.col-num{width:32px;color:#8b949e;font-size:12px;flex-shrink:0}
.col-name{flex:1;font-weight:500}
.col-amt-s{width:110px;text-align:right;color:#3dffa0;font-weight:700;flex-shrink:0;padding-right:8px}
.col-amt-e{width:110px;text-align:right;color:#ff5e7a;font-weight:700;flex-shrink:0;padding-right:8px}
</style>"""


def render_sales_table(data, date_key, is_admin):
    day = get_day_data(data, date_key)
    st.markdown('<p class="sec-title-sales">🟢 বিক্রি</p>', unsafe_allow_html=True)
    st.markdown(ROW_HEADER_CSS, unsafe_allow_html=True)

    rows = day["sales"]
    if rows:
        st.markdown("""<div class="row-header">
            <span class="col-num">#</span>
            <span class="col-name">নাম</span>
            <span class="col-amt-s">টাকা</span>
        </div>""", unsafe_allow_html=True)

        for i, s in enumerate(rows):
            if is_admin:
                col_main, col_btn = st.columns([11, 1])
            else:
                col_main = st.container()
                col_btn = None

            with col_main:
                st.markdown(f"""<div class="row-item">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{s['name']}</span>
                    <span class="col-amt-s">৳ {s['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)

            if is_admin and col_btn:
                with col_btn:
                    if st.button("✕", key=f"del_sale_{date_key}_{i}"):
                        day["sales"].pop(i)
                        save_data(data)
                        st.rerun()
    else:
        st.markdown('<p class="empty-msg">কোনো বিক্রি যোগ হয়নি</p>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  EXPENSE TABLE
# ─────────────────────────────────────────────
def render_expense_table(data, date_key, is_admin):
    day = get_day_data(data, date_key)
    st.markdown('<p class="sec-title-expense">🔴 খরচ</p>', unsafe_allow_html=True)
    st.markdown(ROW_HEADER_CSS, unsafe_allow_html=True)

    rows = day["expenses"]
    if rows:
        st.markdown("""<div class="row-header">
            <span class="col-num">#</span>
            <span class="col-name">বিবরণ</span>
            <span class="col-amt-e">টাকা</span>
        </div>""", unsafe_allow_html=True)

        for i, e in enumerate(rows):
            if is_admin:
                col_main, col_btn = st.columns([11, 1])
            else:
                col_main = st.container()
                col_btn = None

            with col_main:
                st.markdown(f"""<div class="row-item">
                    <span class="col-num">{i+1}</span>
                    <span class="col-name">{e['desc']}</span>
                    <span class="col-amt-e">৳ {e['amount']:,.0f}</span>
                </div>""", unsafe_allow_html=True)

            if is_admin and col_btn:
                with col_btn:
                    if st.button("✕", key=f"del_exp_{date_key}_{i}"):
                        day["expenses"].pop(i)
                        save_data(data)
                        st.rerun()
    else:
        st.markdown('<p class="empty-msg">কোনো খরচ যোগ হয়নি</p>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  BANGLA ↔ ENGLISH NUMBER
# ─────────────────────────────────────────────
def bn_to_en(text: str) -> str:
    return text.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))


def parse_amount(raw: str) -> Optional[float]:
    cleaned = bn_to_en(raw.strip().replace(",", "").replace("৳", "").replace(" ", ""))
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


# ─────────────────────────────────────────────
#  ADMIN INPUT FORMS
# ─────────────────────────────────────────────
def render_admin_inputs(data, date_key):
    today_key = get_today_key()
    # Only allow adding entries for today
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
        "</p>",
        unsafe_allow_html=True,
    )

    if "sale_counter" not in st.session_state:
        st.session_state["sale_counter"] = 0
    if "exp_counter" not in st.session_state:
        st.session_state["exp_counter"] = 0

    sc = st.session_state["sale_counter"]
    ec = st.session_state["exp_counter"]

    col_s, col_e = st.columns(2)

    # ── SALES ──
    with col_s:
        st.markdown("#### ➕ নতুন বিক্রি যোগ করুন")
        sale_name = st.text_input("নাম", placeholder="যেমন: আইস বার, কুলফি...", key=f"sale_name_{sc}")
        sale_amount_raw = st.text_input("টাকা", placeholder="যেমন: ৫০০ বা 500", key=f"sale_amt_{sc}")

        parsed_sale = parse_amount(sale_amount_raw) if sale_amount_raw.strip() else None
        if sale_amount_raw.strip() and parsed_sale is None:
            st.caption("⚠️ সঠিক সংখ্যা লিখুন")
        elif parsed_sale:
            st.caption(f"✅ পরিমাণ: ৳ {parsed_sale:,.0f}")

        if st.button("✅  বিক্রি যোগ করুন", use_container_width=True, key="add_sale_btn"):
            if sale_name.strip() and parsed_sale:
                day = get_day_data(data, date_key)
                day["sales"].append({"name": sale_name.strip(), "amount": parsed_sale})
                save_data(data)
                st.session_state["sale_counter"] += 1
                st.rerun()
            else:
                st.warning("নাম ও সঠিক টাকার পরিমাণ দিন!")

    # ── EXPENSES ──
    with col_e:
        st.markdown("#### ➕ নতুন খরচ যোগ করুন")
        exp_desc = st.text_input("বিবরণ", placeholder="যেমন: কাঁচামাল, ভাড়া...", key=f"exp_desc_{ec}")
        exp_amount_raw = st.text_input("টাকা", placeholder="যেমন: ২৫০ বা 250", key=f"exp_amt_{ec}")

        parsed_exp = parse_amount(exp_amount_raw) if exp_amount_raw.strip() else None
        if exp_amount_raw.strip() and parsed_exp is None:
            st.caption("⚠️ সঠিক সংখ্যা লিখুন")
        elif parsed_exp:
            st.caption(f"✅ পরিমাণ: ৳ {parsed_exp:,.0f}")

        if st.button("✅  খরচ যোগ করুন", use_container_width=True, key="add_exp_btn"):
            if exp_desc.strip() and parsed_exp:
                day = get_day_data(data, date_key)
                day["expenses"].append({"desc": exp_desc.strip(), "amount": parsed_exp})
                save_data(data)
                st.session_state["exp_counter"] += 1
                st.rerun()
            else:
                st.warning("বিবরণ ও সঠিক টাকার পরিমাণ দিন!")


# ─────────────────────────────────────────────
#  ONE-TIME DATE FIX  (admin only)
# ─────────────────────────────────────────────
def render_date_fix(data):
    today_key = get_today_key()
    yesterday_key = date_to_key(datetime.today() - timedelta(days=1))

    today_data = data["dates"].get(today_key, {"sales": [], "expenses": []})
    yesterday_data = data["dates"].get(yesterday_key, {"sales": [], "expenses": []})

    today_has_data = bool(today_data.get("sales") or today_data.get("expenses"))
    yesterday_has_data = bool(yesterday_data.get("sales") or yesterday_data.get("expenses"))

    # Only show if today has data but yesterday doesn't (wrong migration)
    if not (today_has_data and not yesterday_has_data):
        return

    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(255,94,122,0.08);border:1px solid rgba(255,94,122,0.3);
    border-radius:12px;padding:16px 20px;margin-bottom:8px;">
    <p style="color:#ff5e7a;font-weight:700;font-size:15px;margin-bottom:6px">⚠️ তারিখ সংশোধন দরকার</p>
    <p style="color:#e6edf3;font-size:13px;margin-bottom:0">
    আজকের ({today_key}) তারিখে ডেটা আছে কিন্তু এটা আসলে গতকালের ({yesterday_key}) ডেটা।
    নিচের বাটন ক্লিক করলে সব ডেটা <b>{yesterday_key}</b> তারিখে সরিয়ে দেওয়া হবে।
    </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"🔄 ডেটা {yesterday_key} তারিখে সরাও", key="fix_date_btn"):
        data["dates"][yesterday_key] = data["dates"].pop(today_key)
        save_data(data)
        st.session_state["viewing_date"] = yesterday_key
        st.success(f"✅ সব ডেটা {yesterday_key} তারিখে সরানো হয়েছে!")
        st.rerun()


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

    with col_a:
        st.markdown("""<div style="background:#1c2230;border:1px solid #2a3548;border-radius:12px;padding:16px 18px;">
        <p style="color:#00c6ff;font-weight:700;margin-bottom:12px;font-size:14px">🔑 অ্যাডমিন পাসওয়ার্ড</p>""",
                    unsafe_allow_html=True)
        new_admin_pw = st.text_input("নতুন পাসওয়ার্ড", type="password", key=f"new_admin_pw_{pc}", placeholder="নতুন পাসওয়ার্ড লিখুন")
        conf_admin_pw = st.text_input("নিশ্চিত করুন", type="password", key=f"conf_admin_pw_{pc}", placeholder="আবার লিখুন")
        if st.button("✅ অ্যাডমিন পাসওয়ার্ড সেট করুন", use_container_width=True, key="save_admin_pw"):
            if not new_admin_pw:
                st.warning("পাসওয়ার্ড খালি রাখা যাবে না!")
            elif new_admin_pw != conf_admin_pw:
                st.error("পাসওয়ার্ড দুটো মিলছে না!")
            else:
                USERS["admin"]["password"] = new_admin_pw
                save_passwords()
                st.session_state["pw_counter"] += 1
                st.success("✅ অ্যাডমিন পাসওয়ার্ড পরিবর্তন হয়েছে!")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_v:
        st.markdown("""<div style="background:#1c2230;border:1px solid #2a3548;border-radius:12px;padding:16px 18px;">
        <p style="color:#f7c948;font-weight:700;margin-bottom:12px;font-size:14px">👁️ ভিউয়ার পাসওয়ার্ড</p>""",
                    unsafe_allow_html=True)
        new_view_pw = st.text_input("নতুন পাসওয়ার্ড", type="password", key=f"new_view_pw_{pc}", placeholder="নতুন পাসওয়ার্ড লিখুন")
        conf_view_pw = st.text_input("নিশ্চিত করুন", type="password", key=f"conf_view_pw_{pc}", placeholder="আবার লিখুন")
        if st.button("✅ ভিউয়ার পাসওয়ার্ড সেট করুন", use_container_width=True, key="save_view_pw"):
            if not new_view_pw:
                st.warning("পাসওয়ার্ড খালি রাখা যাবে না!")
            elif new_view_pw != conf_view_pw:
                st.error("পাসওয়ার্ড দুটো মিলছে না!")
            else:
                USERS["milky"]["password"] = new_view_pw
                save_passwords()
                st.session_state["pw_counter"] += 1
                st.success("✅ ভিউয়ার পাসওয়ার্ড পরিবর্তন হয়েছে!")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
def main():
    inject_css()
    load_passwords()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
        return

    data = load_data()
    is_admin = st.session_state.role == "admin"

    if not is_admin:
        st.markdown("""<style>
        [data-testid="stToolbar"],[data-testid="manage-app-button"],
        div[class*="StatusWidget"],div[class*="viewerBadge"],
        .stDeployButton,#stDecoration,header[data-testid="stHeader"]
        { display:none !important; visibility:hidden !important; }
        </style>""", unsafe_allow_html=True)

    # ── Date navigation (renders before header so we know which date) ──
    date_key = render_date_nav(data)

    # ── Header ──
    render_header(date_key)

    # ── Logout ──
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

    # ── Summary (with carry forward) ──
    render_summary(data, date_key)

    # ── Tables ──
    col_left, col_right = st.columns(2)
    with col_left:
        render_sales_table(data, date_key, is_admin)
    with col_right:
        render_expense_table(data, date_key, is_admin)

    # ── Admin forms ──
    if is_admin:
        render_date_fix(data)
        render_admin_inputs(data, date_key)
        render_password_reset()


if __name__ == "__main__":
    main()
