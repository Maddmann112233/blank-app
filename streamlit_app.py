import pandas as pd
import streamlit as st
import gspread
import requests
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials

# ================= الإعدادات =================
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"

ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
STATE_COLUMN = "State"
ALLOWED_STATES = {"Approved", "Declined"}     # الحالة المسموح بها فقط
WEBHOOK_COLUMN = "Authorize"                  # <-- التغيير هنا
# ===========================================

st.set_page_config(page_title="MOH Business Owner", layout="wide")

# ====== تنسيق عربي ======
st.markdown("""
<style>
body, .stApp { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
h1, h2, h3, h4 { text-align: center; }
.stButton>button {
  background-color:#0A66C2; color:#fff; font-weight:600;
  border-radius:10px; height:42px; padding:0 18px; border:none;
}
.stTextInput>div>div>input { direction: rtl; text-align: center; font-size:16px; }
.segmented .stRadio > div { display:flex; gap:8px; justify-content:center; }
.segmented .stRadio label {
  padding:10px 18px; border:1px solid #2a2f3a; border-radius:999px;
  cursor:pointer; font-weight:700; user-select:none;
}
.segmented .stRadio input { display:none; }
.segmented .stRadio label:hover { background:#19202a; }
.segmented .stRadio [aria-checked="true"] + span {
  background:#0A66C2; color:#fff; border-color:#0A66C2;
}
.block-container { padding-top: 24px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h2>MOH Business Owner</h2><h4>نظام مراجعة طلبات مشاركة البيانات</h4>', unsafe_allow_html=True)

# ====== Google Sheets ======
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet(spreadsheet_id, worksheet_name) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def is_valid_url(s: str) -> bool:
    s = (s or "").strip()
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

# ====== تحميل البيانات ======
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("لم يتم العثور على عمود يحتوي على المعرف (ID). عدّل القائمة ID_COLUMN_CANDIDATES أو اسم العمود في الشيت.")
    st.stop()

# ====== البحث برقم الطلب ======
st.markdown("### البحث برقم الطلب")
center = st.columns([1, 3, 1])[1]
with center:
    sid = st.text_input("أدخل رقم الطلب:", key="search_id_input")
    search_btn = st.button("بحث", use_container_width=True)

if search_btn:
    st.session_state.selected_id = (sid or "").strip()

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

# ====== التحقق من الحالة ======
if selected_row is not None:
    if STATE_COLUMN not in selected_row.index:
        st.error(f"لم يتم العثور على عمود الحالة '{STATE_COLUMN}'.")
        st.stop()

    current_state = str(selected_row[STATE_COLUMN]).strip()
    if current_state not in ALLOWED_STATES:
        st.error(f"لا يمكن متابعة المعالجة. الحالة الحالية: {current_state} (المطلوب: Approved أو Declined).")
        st.stop()

    webhook_url = str(selected_row.get(WEBHOOK_COLUMN, "")).strip()
    if not is_valid_url(webhook_url):
        st.warning(f"تعذر العثور على رابط ويب هوك صالح في العمود '{WEBHOOK_COLUMN}'. لن يتم إرسال القرار.")
        # نسمح بالاختيار لكن بدون إرسال فعلي

    # ====== واجهة القرار ======
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
            ["موافقة", "غير موافق"],
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

    submit = st.button("إرسال القرار")

    if submit:
        if st.session_state.decision == "غير موافق" and not st.session_state.reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            payload = {
                "id": selected_id,
                "decision": st.session_state.decision,         # "موافقة" أو "غير موافق"
                "reason": st.session_state.reason.strip(),     # قد تكون فارغة
                "state_checked": current_state,                # الحالة المعتمدة Approved / Declined
            }
            if is_valid_url(webhook_url):
                try:
                    r = requests.post(webhook_url, json=payload, timeout=15)
                    r.raise_for_status()
                    st.success("✅ تم إرسال القرار بنجاح.")
                except Exception as e:
                    st.error(f"❌ تعذر إرسال القرار عبر الويب هوك: {e}")
            else:
                st.info("⚠️ لم يتم إرسال القرار لعدم توفر رابط ويب هوك صالح.")
