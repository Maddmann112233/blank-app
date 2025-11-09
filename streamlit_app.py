import pandas as pd
import streamlit as st
import gspread
import requests
import base64
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials

# ================= الإعدادات =================
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"

# نقبل هذه الأسماء لعمود المعرّف (بحث غير حساس لحالة الأحرف)
ID_COLUMN_CANDIDATES = ["id", "request_id", "ticket_id"]

# أسماء الحقول الأخرى (غير حساسة لحالة الأحرف)
STATE_COLUMN_WANTED = "state"
WEBHOOK_COLUMN_WANTED = "authorize"

# الحالتان المسموحتان
ALLOWED_STATES = {"approved", "declined"}
# ===========================================

st.set_page_config(page_title="MOH Admin", layout="wide")

# ====== خلفية مخصصة ======
def set_background(png_file):
    """Set a custom background image from local file."""
    with open(png_file, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
            color: #E8FFFA;
        }}
        /* subtle dark overlay for readability */
        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            background: radial-gradient(60% 80% at 70% 30%, rgba(5,60,60,.25) 0%, rgba(5,30,32,.55) 100%);
            pointer-events: none;
            z-index: 0;
        }}
        /* color tokens from the background */
        :root {{
            --teal: #0FB39B;        /* primary (picked from image mid-tone) */
            --teal-2: #12D1C1;      /* accent/hover */
            --teal-dark: #0A6E66;   /* darker edge */
            --mint: #A6EEE1;        /* light accents */
            --glass: rgba(6, 33, 36, 0.35);
            --glass-border: rgba(166, 238, 225, 0.25);
            --text: #E8FFFA;
            --muted: #CFF7EF;
        }}
        /* glass card look */
        .block-container {{
            padding-top: 24px;
            position: relative;
            z-index: 1;
        }}
        .block-container > :not(style) {{
            backdrop-filter: blur(6px);
        }}
        /* headers */
        h1, h2, h3, h4 {{
            color: var(--mint) !important;
            text-shadow: 0 1px 12px rgba(0,0,0,.25);
            text-align: center;
        }}

        /* buttons */
        .stButton>button {{
            background: linear-gradient(135deg, var(--teal), var(--teal-2));
            color: #fff;
            font-weight: 700;
            border: 0;
            border-radius: 14px;
            height: 44px;
            padding: 0 22px;
            box-shadow: 0 10px 25px rgba(15, 179, 155, .25), inset 0 0 0 1px rgba(255,255,255,.08);
            transition: transform .06s ease, box-shadow .2s ease, filter .2s ease;
        }}
        .stButton>button:hover {{
            filter: brightness(1.05);
            box-shadow: 0 14px 30px rgba(18, 209, 193, .28);
        }}
        .stButton>button:active {{
            transform: translateY(1px) scale(.99);
        }}

        /* inputs */
        .stTextInput>div>div>input,
        .stTextArea textarea {{
            background: var(--glass);
            color: var(--text);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            text-align: center;
        }}
        .stTextInput>div>div>input:focus,
        .stTextArea textarea:focus {{
            outline: none;
            border-color: var(--mint);
            box-shadow: 0 0 0 3px rgba(18, 209, 193, .25);
        }}

        /* segmented radio (Arabic) */
        .segmented .stRadio > div {{
            display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;
        }}
        .segmented .stRadio label {{
            padding: 10px 18px;
            border: 1px solid var(--glass-border);
            border-radius: 999px;
            cursor: pointer; font-weight: 700; user-select: none;
            background: var(--glass);
            color: var(--text);
        }}
        .segmented .stRadio input {{ display: none; }}
        .segmented .stRadio [aria-checked="true"] + span {{
            background: linear-gradient(135deg, var(--teal), var(--teal-2));
            color: #fff; border-color: transparent;
            box-shadow: 0 6px 16px rgba(18, 209, 193, .25);
        }}
        .segmented .stRadio label:hover {{
            border-color: var(--mint);
        }}

        /* alerts */
        .stAlert>div {{
            background: rgba(6, 33, 36, 0.55);
            color: var(--text);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
        }}

        /* tables (if any appear) */
        .stDataFrame, .stTable {{
            background: rgba(6, 33, 36, 0.45) !important;
            border-radius: 12px !important;
        }}

        /* overall direction & font */
        body, .stApp {{ direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }}
        </style>
        """,
        unsafe_allow_html=True
    )

# نفس اسم الصورة في المستودع
set_background("ChatGPT Image Nov 9, 2025, 02_38_42 AM.png")

st.markdown('<h2>MOH Admin</h2><h4>نظام مراجعة طلبات مشاركة البيانات</h4>', unsafe_allow_html=True)

# ====== Google Sheets ======
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_sheet(spreadsheet_id, worksheet_name) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    return df

def is_valid_url(s: str) -> bool:
    s = (s or "").strip()
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

def resolve_column(df: pd.DataFrame, wanted_lower: str, fallback_candidates=None):
    lower_map = {c.strip().lower(): c for c in df.columns}
    if fallback_candidates:
        for cand in fallback_candidates:
            if cand in lower_map:
                return lower_map[cand]
        return None
    return lower_map.get(wanted_lower)

# ====== تحميل البيانات ======
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

if df.empty:
    st.error("ورقة العمل فارغة أو لم تُحمّل البيانات.")
    st.stop()

# تحديد الأعمدة
id_col = resolve_column(df, None, fallback_candidates=[c.lower() for c in ID_COLUMN_CANDIDATES])
if not id_col:
    st.error(f"لم يتم العثور على عمود المعرّف. تأكد من وجود أحد هذه الأعمدة: {ID_COLUMN_CANDIDATES}")
    st.stop()

state_col = resolve_column(df, STATE_COLUMN_WANTED)
webhook_col = resolve_column(df, WEBHOOK_COLUMN_WANTED)

if not state_col:
    st.error(f"لم يتم العثور على عمود الحالة: {STATE_COLUMN_WANTED}")
    st.stop()
if not webhook_col:
    st.error(f"لم يتم العثور على عمود الويب هوك: {WEBHOOK_COLUMN_WANTED}")
    st.stop()

# ====== البحث برقم الطلب ======
st.markdown("### البحث برقم الطلب")
center = st.columns([1, 3, 1])[1]
with center:
    sid = st.text_input("أدخل رقم الطلب:", key="search_id_input")
    search_btn = st.button("بحث", use_container_width=True)

if search_btn:
    st.session_state.selected_id = (sid or "").strip()
    st.cache_data.clear()
    df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

selected_id = (st.session_state.get("selected_id") or "").strip()
selected_row = None
if selected_id:
    mask = df[id_col].astype(str).str.strip().str.lower() == selected_id.lower()
    match = df[mask]
    if not match.empty:
        selected_row = match.iloc[0]

if search_btn and not selected_id:
    st.warning("يرجى إدخال رقم الطلب أولاً.")

if selected_id and selected_row is None:
    st.warning("لا توجد نتائج مطابقة لهذا الرقم.")
    st.stop()

# ====== التحقق ثم الواجهة ======
if selected_row is not None:
    current_state = str(selected_row[state_col]).strip()
    if current_state.lower() not in ALLOWED_STATES:
        st.error(f"لا يمكن المتابعة. الحالة الحالية: {current_state} (المطلوب: Approved أو Declined).")
        st.stop()

    webhook_url = str(selected_row[webhook_col]).strip()
    if not is_valid_url(webhook_url):
        st.error(f"القيمة في عمود {webhook_col} ليست رابط ويب هوك صالحاً.")
        st.stop()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### القرار")

    if "decision" not in st.session_state:
        st.session_state.decision = "موافقة"
    if "reason" not in st.session_state:
        st.session_state.reason = ""

    with st.container():
        st.markdown('<div class="segmented">', unsafe_allow_html=True)
        st.session_state.decision = st.radio(
            "اختر القرار:",
            ["موافق", "غير موافق"],
            horizontal=True,
            key="decision_radio_ar",
            index=0 if st.session_state.decision == "موافقة" else 1,
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.decision == "غير موافق":
        st.session_state.reason = st.text_area("سبب الرفض (إلزامي):", value=st.session_state.reason, key="reason_ar")
    else:
        st.session_state.reason = ""

    submit = st.button("إرسال القرار", use_container_width=False)

    if submit:
        if st.session_state.decision == "غير موافق" and not st.session_state.reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            payload = {
                "id": selected_id,
                "decision": st.session_state.decision,
                "reason": st.session_state.reason.strip(),
                "state_checked": current_state,
            }
            try:
                r = requests.post(webhook_url, json=payload, timeout=15)
                r.raise_for_status()
                st.success("تم إرسال القرار بنجاح.")
            except Exception as e:
                st.error(f"تعذر إرسال القرار عبر الويب هوك: {e}")
