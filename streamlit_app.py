import pandas as pd
import streamlit as st
import gspread
import requests
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

@st.cache_data(ttl=30)  # تقليل التخزين المؤقت لتحديث البيانات بسرعة
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
    """
    يعيد الاسم الفعلي لعمود (كما في DataFrame) بمطابقة غير حساسة لحالة الأحرف.
    إذا قدمت قائمة candidates، سيتم قبول أي اسم منها (كلها يجب أن تكون بحروف صغيرة).
    """
    # خريطة من lower -> original
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

# تحديد عمود ID غير حساس لحالة الأحرف
id_col = resolve_column(df, None, fallback_candidates=[c.lower() for c in ID_COLUMN_CANDIDATES])
if not id_col:
    st.error(f"لم يتم العثور على عمود المعرّف. تأكد من وجود أحد هذه الأعمدة: {ID_COLUMN_CANDIDATES}")
    st.stop()

# تحديد عمود الحالة وعمود الويب هوك بشكل غير حساس لحالة الأحرف
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

# عند الضغط على بحث نخزّن القيمة ونحمّل نسخة حديثة من الشيت
if search_btn:
    st.session_state.selected_id = (sid or "").strip()
    st.cache_data.clear()  # نضمن تحديث القراءة في البحث التالي
    df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

selected_id = (st.session_state.get("selected_id") or "").strip()

selected_row = None
if selected_id:
    # مطابقة ID بعد تنظيف المسافات وحساسية لحروف صغيرة
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
    # التحقق من الحالة
    current_state = str(selected_row[state_col]).strip()
    if current_state.lower() not in ALLOWED_STATES:
        st.error(f"لا يمكن المتابعة. الحالة الحالية: {current_state} (المطلوب: Approved أو Declined).")
        st.stop()

    # قراءة الويب هوك من عمود Authorize (غير حساس لحالة الأحرف)
    webhook_url = str(selected_row[webhook_col]).strip()
    if not is_valid_url(webhook_url):
        st.error(f"القيمة في عمود {webhook_col} ليست رابط ويب هوك صالحاً.")
        st.stop()

    # واجهة القرار فقط
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

    submit = st.button("إرسال القرار")

    if submit:
        if st.session_state.decision == "غير موافق" and not st.session_state.reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            payload = {
                "id": selected_id,                       # من عمود ID
                "decision": st.session_state.decision,   # "موافقة" أو "غير موافق"
                "reason": st.session_state.reason.strip(),
                "state_checked": current_state,          # الحالة في الشيت (Approved/Declined)
            }
            try:
                r = requests.post(webhook_url, json=payload, timeout=15)
                r.raise_for_status()
                st.success("تم إرسال القرار بنجاح.")
            except Exception as e:
                st.error(f"تعذر إرسال القرار عبر الويب هوك: {e}")
