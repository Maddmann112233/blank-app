import base64
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
REASON_COLUMN_WANTED = "reason"

# الحالتان المسموحتان
ALLOWED_STATES = {"approved", "declined"}
# ===========================================

st.set_page_config(page_title="MOH Admin", layout="wide")

# ====== خلفية مطابقة للثيم (بدون تغيير الاسم) ======
BG_FILE = "ChatGPT Image Nov 9, 2025, 02_38_42 AM.png"

def set_background(image_path: str):
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: 
                  linear-gradient(165deg, rgba(0, 74, 67, 0.70), rgba(10, 130, 117, 0.55)) ,
                  url("data:image/png;base64,{b64}") center/cover no-repeat fixed;
            }}
            /* soften default containers over the background */
            .block-container {{
                background: transparent;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        # إذا تعذر تحميل الصورة لأي سبب، نبقي الخلفية بلون متدرج مناسب
        st.markdown(
            """
            <style>
            .stApp {
                background: linear-gradient(165deg, #004a43, #0a8275);
            }
            .block-container { background: transparent; }
            </style>
            """,
            unsafe_allow_html=True,
        )

set_background(BG_FILE)

# ====== تنسيق عربي + ثيم متوافق مع الخلفية ======
st.markdown("""
<style>
/* Base RTL */
body, .stApp { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
h1, h2, h3, h4 { text-align: center; color:#e9fffa; }
.block-container { padding-top: 24px; }

/* Color tokens derived from the background */
:root {
  --teal-900: #0b3a35;
  --teal-800: #0f4a43;
  --teal-700: #13655e;
  --teal-500: #0FB59C;
  --teal-300: #78e3d3;
  --ink-100: #e6edf3;
  --ink-300: #b9c7d3;
  --glass-bg: rgba(6, 34, 31, 0.45);
  --glass-brd: rgba(90, 210, 195, 0.22);
}

/* Buttons */
.stButton>button {
  background-color: var(--teal-500); color:#042420; font-weight:700;
  border-radius:12px; height:44px; padding:0 20px; border:1px solid rgba(255,255,255,0.05);
  box-shadow: 0 8px 24px rgba(15,181,156,0.25);
}
.stButton>button:hover { filter: brightness(1.06) saturate(1.05); }

/* Inputs */
.stTextInput>div>div>input {
  direction: rtl; text-align: center; font-size:16px;
  background: var(--glass-bg); color: var(--ink-100);
  border:1px solid var(--glass-brd); border-radius:12px;
}

/* Text area styling */
.stTextArea textarea {
  direction: rtl; text-align: right; font-size:15px;
  background: var(--glass-bg) !important; 
  color: var(--ink-100) !important;
  border:1px solid var(--glass-brd) !important; 
  border-radius:12px !important;
}

/* ===== FIXED: Radio buttons to match theme ===== */
/* Hide default radio buttons */
.stRadio > div[role="radiogroup"] > label > div:first-child {
  display: none !important;
}

/* Style the radio container */
.stRadio > div[role="radiogroup"] {
  display: flex !important;
  gap: 12px !important;
  justify-content: center !important;
  flex-wrap: wrap !important;
  padding: 8px 0 !important;
}

/* Style each radio label as a pill button */
.stRadio > div[role="radiogroup"] > label {
  padding: 12px 24px !important;
  border: 1px solid var(--glass-brd) !important;
  border-radius: 999px !important;
  background: var(--glass-bg) !important;
  color: var(--ink-100) !important;
  cursor: pointer !important;
  font-weight: 700 !important;
  user-select: none !important;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3) !important;
  transition: all 0.2s ease !important;
  margin: 0 !important;
  min-width: 120px !important;
  text-align: center !important;
}

/* Hover state */
.stRadio > div[role="radiogroup"] > label:hover {
  background: rgba(16, 94, 86, 0.65) !important;
  border-color: rgba(90, 210, 195, 0.35) !important;
  transform: translateY(-1px) !important;
}

/* Selected state - using aria-checked or data attributes */
.stRadio > div[role="radiogroup"] > label:has(input:checked),
.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
  background: var(--teal-500) !important;
  color: #052826 !important;
  border-color: rgba(15,181,156,0.85) !important;
  box-shadow: 0 6px 20px rgba(15,181,156,0.35) !important;
  font-weight: 900 !important;
}

/* Remove any default streamlit radio styling */
.stRadio > div {
  background: transparent !important;
}

/* ===== Status badge themed to teal network ===== */
.status-wrap { text-align:center; margin: 10px 0 10px 0; }
.badge {
  display:inline-block; padding:10px 18px; border-radius:999px;
  font-weight:900; font-size:14px; letter-spacing:.2px;
  border:1px solid var(--glass-brd);
  background: rgba(8, 60, 55, 0.60);
  color: var(--ink-100);
  box-shadow: 0 6px 24px rgba(0,0,0,0.35);
}
.badge.green {
  background: linear-gradient(180deg, rgba(15,181,156,0.16), rgba(15,181,156,0.08));
  color:#cffff5; border-color: rgba(15,181,156,0.55);
}
.badge.red {
  background: linear-gradient(180deg, rgba(220,66,66,0.16), rgba(220,66,66,0.08));
  color:#ffd6d6; border-color: rgba(220,66,66,0.45);
}

/* ===== Reason card (glassmorphic panel) ===== */
.reason-card {
  backdrop-filter: blur(10px);
  background: var(--glass-bg);
  border:1px solid var(--glass-brd);
  color: var(--ink-100);
  padding:16px 18px; border-radius:16px; margin: 10px 0 22px 0;
  line-height:1.8; font-size:15.5px;
  box-shadow: 0 10px 28px rgba(0,0,0,0.35);
}
.reason-title { font-weight:900; margin-left:8px; color: var(--teal-300); }
.muted { color: var(--ink-300); }
</style>
""", unsafe_allow_html=True)

st.markdown('<h2>MOH Admin</h2><h4>نظام مراجعة طلبات مشاركة البيانات</h4>', unsafe_allow_html=True)

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

# تحديد الأعمدة الأخرى
state_col   = resolve_column(df, STATE_COLUMN_WANTED)
webhook_col = resolve_column(df, WEBHOOK_COLUMN_WANTED)
reason_col  = resolve_column(df, REASON_COLUMN_WANTED)

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
    # الحالة الحالية + عرضها
    current_state = str(selected_row[state_col]).strip()
    state_norm = current_state.lower()

    badge_class = "green" if state_norm == "approved" else "red" if state_norm == "declined" else ""
    st.markdown(
        f"""
        <div class="status-wrap">
            <span class="badge {badge_class}">
                الحالة الحالية: <span dir="ltr">{current_state}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # إظهار السبب من الشيت (إن وجد)
    if reason_col:
        reason_from_sheet = str(selected_row.get(reason_col, "")).strip()
        shown_text = reason_from_sheet if reason_from_sheet else "(لا يوجد سبب مسجل)"
        st.markdown(
            f"""
            <div class="reason-card">
                <span class="reason-title">السبب :</span>
                <span style="direction:auto; unicode-bidi: plaintext;">{shown_text}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div class="reason-card">
                <span class="reason-title">السبب:</span>
                <span class="muted">عمود "reason" غير موجود في ورقة العمل.</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # تحقق السماحية
    if state_norm not in ALLOWED_STATES:
        st.error(f"لا يمكن المتابعة. الحالة الحالية: {current_state} (المطلوب: Approved أو Declined).")
        st.stop()

    # قراءة الويب هوك
    webhook_url = str(selected_row[webhook_col]).strip()
    if not is_valid_url(webhook_url):
        st.error(f"القيمة في عمود {webhook_col} ليست رابط ويب هوك صالحاً.")
        st.stop()

    # واجهة القرار
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### القرار")

    if "decision" not in st.session_state:
        st.session_state.decision = "موافق"
    if "reason" not in st.session_state:
        st.session_state.reason = ""

    # Radio buttons with proper styling
    st.session_state.decision = st.radio(
        "اختر القرار:",
        ["موافق", "غير موافق"],
        horizontal=True,
        key="decision_radio_ar",
        index=0 if st.session_state.decision == "موافق" else 1,
    )

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
                "decision": st.session_state.decision,   # "موافق" أو "غير موافق"
                "reason": st.session_state.reason.strip(),
                "state_checked": current_state,          # الحالة في الشيت (Approved/Declined)
            }
            try:
                r = requests.post(webhook_url, json=payload, timeout=15)
                r.raise_for_status()
                
                # Check if response contains success indicator
                try:
                    response_data = r.json()
                    if response_data.get("success") == False or response_data.get("error"):
                        st.error(f"فشل إرسال القرار: {response_data.get('error', 'خطأ غير معروف')}")
                    else:
                        st.success("تم إرسال القرار بنجاح.")
                except:
                    # If response is not JSON, check status code only
                    if r.status_code == 200:
                        st.success("تم إرسال القرار بنجاح.")
                    else:
                        st.error(f"فشل إرسال القرار. رمز الحالة: {r.status_code}")
                        
            except requests.exceptions.Timeout:
                st.error("انتهت مهلة الاتصال بالويب هوك. يرجى المحاولة مرة أخرى.")
            except requests.exceptions.ConnectionError:
                st.error("تعذر الاتصال بالويب هوك. تحقق من الاتصال بالإنترنت.")
            except requests.exceptions.HTTPError as e:
                st.error(f"خطأ HTTP: {e.response.status_code} - {e.response.text[:200]}")
            except Exception as e:
                st.error(f"تعذر إرسال القرار: {str(e)}")