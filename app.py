import streamlit as st
import json
import os
from datetime import datetime

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
#  USERS  (user: admin → full access, viewer → read-only)
# ─────────────────────────────────────────────
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "viewer": {"password": "view123",  "role": "viewer"},
}

# ─────────────────────────────────────────────
#  DATA FILE  (persists between reloads)
# ─────────────────────────────────────────────
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sales": [], "expenses": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
#  DATE HELPER
# ─────────────────────────────────────────────
def formatted_date():
    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    d = datetime.today()
    return f"{d.day}/{months[d.month-1]}/{d.year}"

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

    /* Hide Streamlit default header/footer */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; }

    /* ── App Header ── */
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

    /* ── Section titles ── */
    .sec-title-sales   { color: #3dffa0; font-size: 17px; font-weight: 700; letter-spacing:1px; }
    .sec-title-expense { color: #ff5e7a; font-size: 17px; font-weight: 700; letter-spacing:1px; }

    /* ── Summary cards ── */
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
    .c-green { color: #3dffa0; }
    .c-red   { color: #ff5e7a; }
    .c-gold  { color: #f7c948; }
    .c-muted { color: #8b949e; }

    /* ── Data table ── */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        margin-bottom: 4px;
    }
    .data-table thead th {
        background: #161b22;
        color: #8b949e;
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 9px 12px;
        border-bottom: 1px solid #2a3548;
        text-align: left;
    }
    .data-table thead th:last-child { text-align: right; }
    .data-table tbody tr { border-bottom: 1px solid rgba(42,53,72,0.5); }
    .data-table tbody tr:hover { background: rgba(255,255,255,0.025); }
    .data-table tbody td { padding: 9px 12px; vertical-align: middle; }
    .data-table tbody td:last-child { text-align: right; }
    .row-num { color: #8b949e; font-size: 12px; }
    .amt-s { color: #3dffa0; font-weight: 700; }
    .amt-e { color: #ff5e7a; font-weight: 700; }
    .empty-msg { text-align: center; color: #8b949e; font-style: italic; padding: 24px; }

    /* ── Login box ── */
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

    /* Streamlit input overrides */
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

    /* Viewer info banner */
    .viewer-banner {
        background: rgba(247,201,72,0.08);
        border: 1px solid rgba(247,201,72,0.25);
        border-radius: 10px;
        padding: 10px 16px;
        color: #f7c948;
        font-size: 13px;
        margin-bottom: 18px;
        text-align: center;
    }
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
        username = st.text_input("👤 ইউজারনেম", placeholder="username লিখুন", label_visibility="visible")
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

        st.markdown("""
        <div style="margin-top:20px;background:#0d1117;border:1px solid #2a3548;
             border-radius:10px;padding:12px 16px;font-size:12px;color:#8b949e;text-align:left;">
            <b style="color:#e6edf3;">ডিফল্ট লগইন তথ্য:</b><br>
            🔴 <b>Admin:</b> admin / admin123<br>
            🟡 <b>Viewer:</b> viewer / view123
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
def render_header():
    role = st.session_state.get("role", "viewer")
    role_label = "অ্যাডমিন" if role == "admin" else "ভিউয়ার"
    role_class = "role-admin" if role == "admin" else "role-viewer"

    st.markdown(f"""
    <div class="app-header">
        <div class="brand">ঢাকার <span>মিল্কী</span> আইস বার</div>
        <div>
            <span class="date-badge">📅 {formatted_date()}</span>
            <span class="role-badge {role_class}">{'🔑' if role=='admin' else '👁️'} {role_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SUMMARY BAR
# ─────────────────────────────────────────────
def render_summary(data):
    total_sales   = sum(s["amount"] for s in data["sales"])
    total_expense = sum(e["amount"] for e in data["expenses"])
    profit        = total_sales - total_expense

    profit_class = "c-gold" if profit > 0 else ("c-red" if profit < 0 else "c-muted")
    profit_sign  = "" if profit >= 0 else "- "
    profit_label = "লাভ" if profit >= 0 else "ক্ষতি"

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
            <div class="val {profit_class}">{profit_sign}৳ {abs(profit):,.0f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  SALES TABLE
# ─────────────────────────────────────────────
def render_sales_table(data, is_admin):
    st.markdown('<p class="sec-title-sales">🟢 বিক্রি</p>', unsafe_allow_html=True)

    rows = data["sales"]
    if rows:
        html = '<table class="data-table"><thead><tr>'
        html += '<th>#</th><th>নাম</th><th>টাকা</th>'
        if is_admin:
            html += '<th></th>'
        html += '</tr></thead><tbody>'

        for i, s in enumerate(rows):
            html += f"""<tr>
                <td class="row-num">{i+1}</td>
                <td>{s['name']}</td>
                <td class="amt-s">৳ {s['amount']:,.0f}</td>
            """
            if is_admin:
                html += f'<td></td>'
            html += '</tr>'

        html += '</tbody></table>'
        st.markdown(html, unsafe_allow_html=True)

        # Delete buttons — outside raw HTML (Streamlit limitation)
        if is_admin:
            for i, s in enumerate(rows):
                col_a, col_b, col_c = st.columns([2, 3, 1])
                with col_c:
                    if st.button(f"✕", key=f"del_sale_{i}", help=f"'{s['name']}' মুছুন"):
                        data["sales"].pop(i)
                        save_data(data)
                        st.rerun()
    else:
        st.markdown('<p class="empty-msg">কোনো বিক্রি যোগ হয়নি</p>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  EXPENSE TABLE
# ─────────────────────────────────────────────
def render_expense_table(data, is_admin):
    st.markdown('<p class="sec-title-expense">🔴 খরচ</p>', unsafe_allow_html=True)

    rows = data["expenses"]
    if rows:
        html = '<table class="data-table"><thead><tr>'
        html += '<th>#</th><th>বিবরণ</th><th>টাকা</th>'
        if is_admin:
            html += '<th></th>'
        html += '</tr></thead><tbody>'

        for i, e in enumerate(rows):
            html += f"""<tr>
                <td class="row-num">{i+1}</td>
                <td>{e['desc']}</td>
                <td class="amt-e">৳ {e['amount']:,.0f}</td>
            """
            if is_admin:
                html += '<td></td>'
            html += '</tr>'

        html += '</tbody></table>'
        st.markdown(html, unsafe_allow_html=True)

        if is_admin:
            for i, e in enumerate(rows):
                col_a, col_b, col_c = st.columns([2, 3, 1])
                with col_c:
                    if st.button(f"✕", key=f"del_exp_{i}", help=f"'{e['desc']}' মুছুন"):
                        data["expenses"].pop(i)
                        save_data(data)
                        st.rerun()
    else:
        st.markdown('<p class="empty-msg">কোনো খরচ যোগ হয়নি</p>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  ADMIN INPUT FORMS
# ─────────────────────────────────────────────
def render_admin_inputs(data):
    st.markdown("---")
    col_s, col_e = st.columns(2)

    with col_s:
        st.markdown("#### ➕ নতুন বিক্রি যোগ করুন")
        sale_name   = st.text_input("নাম", placeholder="যেমন: আইস বার, কুলফি...", key="sale_name")
        sale_amount = st.number_input("টাকা", min_value=0.0, step=1.0, format="%.0f", key="sale_amount")
        if st.button("✅  বিক্রি যোগ করুন", use_container_width=True, key="add_sale_btn"):
            if sale_name.strip() and sale_amount > 0:
                data["sales"].append({"name": sale_name.strip(), "amount": float(sale_amount)})
                save_data(data)
                st.success("বিক্রি যোগ হয়েছে!")
                st.rerun()
            else:
                st.warning("নাম ও টাকার পরিমাণ দিন!")

    with col_e:
        st.markdown("#### ➕ নতুন খরচ যোগ করুন")
        exp_desc   = st.text_input("বিবরণ", placeholder="যেমন: কাঁচামাল, ভাড়া...", key="exp_desc")
        exp_amount = st.number_input("টাকা", min_value=0.0, step=1.0, format="%.0f", key="exp_amount")
        if st.button("✅  খরচ যোগ করুন", use_container_width=True, key="add_exp_btn"):
            if exp_desc.strip() and exp_amount > 0:
                data["expenses"].append({"desc": exp_desc.strip(), "amount": float(exp_amount)})
                save_data(data)
                st.success("খরচ যোগ হয়েছে!")
                st.rerun()
            else:
                st.warning("বিবরণ ও টাকার পরিমাণ দিন!")

# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
def main():
    inject_css()

    # ── Session defaults ──
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # ── Not logged in → show login ──
    if not st.session_state.logged_in:
        login_page()
        return

    # ── Logged in ──
    data     = load_data()
    is_admin = st.session_state.role == "admin"

    # Header
    render_header()

    # Logout button (top right)
    _, _, logout_col = st.columns([6, 1, 1])
    with logout_col:
        if st.button("🚪 লগআউট"):
            for k in ["logged_in", "username", "role"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Viewer notice
    if not is_admin:
        st.markdown("""
        <div class="viewer-banner">
            👁️ আপনি <b>ভিউয়ার মোড</b>-এ আছেন — শুধু ডেটা দেখতে পারবেন, পরিবর্তন করা যাবে না।
        </div>
        """, unsafe_allow_html=True)

    # Summary
    render_summary(data)

    # Two-column layout
    col_left, col_right = st.columns(2)

    with col_left:
        render_sales_table(data, is_admin)

    with col_right:
        render_expense_table(data, is_admin)

    # Admin input forms
    if is_admin:
        render_admin_inputs(data)

if __name__ == "__main__":
    main()
