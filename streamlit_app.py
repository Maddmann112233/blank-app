import time
import urllib.parse
import requests
import streamlit as st
from datetime import datetime, timezone

# ================== CONFIG ==================
DEFAULT_WEBHOOK_URL = "https://tofyz.app.n8n.cloud/webhook-test/moh-form"
REQUEST_TIMEOUT = 10
RETRIES = 3
BACKOFF = 1.6

# NEW: Google Sheets config
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"  # change if needed
WORKSHEET_NAME = "Sheet1"                                        # change if needed
ID_COLUMN = "id"                                                 # change if your ID column differs
STATE_COLUMN = "State"                                           # must exist
REQUIRED_STATE = "Approved"                                      # gate condition
# ============================================

st.set_page_config(
    page_title="نموذج طلب مشاركة البيانات - MOH Data Request Form",
    page_icon="📄",
    layout="centered"
)

# --- RTL style ---
st.markdown("""
<style>
body { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- Helpers for query params ---
def get_query_params():
    try:
        return st.query_params
    except Exception:
        return st.experimental_get_query_params()

qp = get_query_params()
def qp_get_one(name: str):
    if name not in qp:
        return None
    v = qp[name]
    return v[0] if isinstance(v, list) else v

# Read resume URL (optional)
resume_param = qp_get_one("resume") or qp_get_one("resumeUrl")
resume_url = None
if resume_param:
    try:
        resume_url = urllib.parse.unquote(resume_param)
        if "%2F" in resume_url or "%3A" in resume_url:
            resume_url = urllib.parse.unquote(resume_url)
    except Exception:
        resume_url = resume_param

# ---------- Google Sheets helpers ----------
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from urllib.parse import urlparse  # NEW

def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet_df(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    rows = ws.get_all_records()
    return pd.DataFrame(rows)

@st.cache_data(ttl=30)
def find_row_by_id(df: pd.DataFrame, id_value: str) -> pd.Series | None:
    if df.empty or ID_COLUMN not in df.columns:
        return None
    mask = df[ID_COLUMN].astype(str).str.strip().str.lower() == str(id_value).strip().lower()
    match = df[mask]
    return match.iloc[0] if not match.empty else None

def is_valid_url(s: str) -> bool:  # NEW
    s = (s or "").strip()
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False
# -------------------------------------------------

# --- Header ---
st.markdown("<h1 style='text-align:center;'>نموذج طلب مشاركة البيانات</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;'>MOH Data Request Form</h3>", unsafe_allow_html=True)
st.write("---")

if resume_url:
    st.caption("سيتم الإرسال تلقائياً إلى رابط الاستئناف (resumeUrl) من n8n إن لم تُدخل رابطاً يدوياً.")
else:
    st.caption("يمكنك إدخال معرّف الطلب (ID) أدناه وسيتم التحقق من الحالة قبل الإرسال.")

st.write("### الرجاء تعبئة الحقول التالية:")

# --- Form ---
with st.form("moh_form"):
    # ID input (kept)
    input_id = st.text_input("رقم الطلب (ID)")

    agree = st.checkbox("موافق")
    disagree = st.checkbox("غير موافق")

    # Always render the reason box; enable only if (disagree and not agree)
    show_enabled = (disagree and not agree)
    reason = st.text_area(
        "سبب الرفض",
        placeholder="يرجى توضيح سبب الرفض هنا...",
        disabled=not show_enabled
    )

    submitted = st.form_submit_button("إرسال الطلب")

    if submitted:
        # Validation (same as your original logic)
        if not input_id.strip():
            st.warning("يرجى إدخال رقم الطلب (ID).")
        elif agree and disagree:
            st.warning("لا يمكن اختيار الخيارين معاً.")
        elif not agree and not disagree:
            st.info("الرجاء اختيار أحد الخيارين قبل الإرسال.")
        elif disagree and not reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            # ---------- Verify against Google Sheet before sending ----------
            df = load_sheet_df(SPREADSHEET_ID, WORKSHEET_NAME)
            row = find_row_by_id(df, input_id)

            if row is None:
                st.error("لم يتم العثور على صف يطابق رقم الطلب المدخل.")
            elif STATE_COLUMN not in row or str(row[STATE_COLUMN]).strip() != REQUIRED_STATE:
                current_state = str(row.get(STATE_COLUMN, "")).strip() if STATE_COLUMN in row else "غير معروف"
                st.error(f"لا يمكن الإرسال. الحالة الحالية: {current_state} (المطلوب: {REQUIRED_STATE})")
            else:
                # Passed the State gate → proceed to send
                choice = "موافق" if agree else "غير موافق"
                ts = datetime.now(timezone.utc).isoformat()

                # NEW: read "Authorize" column and include in payload
                authorize_value = str(row.get("Authorize", "")).strip()  # NEW

                payload = {
                    "choice": choice,
                    "timestamp_utc": ts,
                    "id": input_id.strip(),
                    "authorize": authorize_value,  # NEW
                }
                if disagree:
                    payload["reason_for_refusal"] = reason.strip()

                # Determine target URL priority:
                # 1) If "Authorize" cell is a valid URL, use it
                # 2) Else use resume_url (if provided)
                # 3) Else use DEFAULT_WEBHOOK_URL
                if is_valid_url(authorize_value):  # NEW
                    target_url = authorize_value
                else:
                    target_url = resume_url or DEFAULT_WEBHOOK_URL

                if not target_url:
                    st.error("لم يتم تحديد أي رابط للإرسال.")
                else:
                    ok, resp_text = False, ""
                    for i in range(RETRIES):
                        try:
                            r = requests.post(target_url, json=payload, timeout=REQUEST_TIMEOUT)
                            ok, resp_text = r.ok, (r.text or "")
                            if ok:
                                break
                        except Exception as e:
                            resp_text = str(e)
                        time.sleep(BACKOFF ** i)

                    if ok:
                        st.success(f"تم إرسال الطلب بنجاح. تم اختيار: {choice}")
                        if disagree:
                            st.caption(f"سبب الرفض: {reason.strip()}")
                        if resp_text:
                            st.caption(f"رد الخادم: {resp_text[:300]}")
                    else:
                        st.error("تعذر الإرسال إلى الخادم بعد عدة محاولات.")
                        if resp_text:
                            st.caption(f"التفاصيل: {resp_text[:300]}")

st.write("---")
st.caption("© 2025 وزارة الصحة - نظام طلب مشاركة البيانات")
