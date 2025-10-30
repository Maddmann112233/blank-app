import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime, timezone

# ============== CONFIG ==============
WEBHOOK_URL = "https://tofyz.app.n8n.cloud/webhook-test/9373a788-a97b-448b-b9ec-981d1da43ca6"
TIMEOUT_SEC = 8
SAVE_LOCAL_CSV = True
LOCAL_CSV_NAME = "responses.csv"
# ===================================

# --- Page setup ---
st.set_page_config(
    page_title="نموذج طلب مشاركة البيانات - MOH Data Request Form",
    page_icon="📄",
    layout="centered"
)

# --- RTL Arabic Style ---
st.markdown("""
<style>
body { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- Read query parameters ---
def get_query_params():
    try:
        return st.query_params          # Streamlit ≥ 1.30
    except Exception:
        return st.experimental_get_query_params()

qp = get_query_params()
url_id = None
if "id" in qp:                         # read ?id=YOUR_TRACKING_NUMBER
    val = qp["id"]
    url_id = val[0] if isinstance(val, list) else val

# --- Header ---
st.markdown("<h1 style='text-align:center;'>📄 نموذج طلب مشاركة البيانات</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;'>MOH Data Request Form</h3>", unsafe_allow_html=True)
st.write("---")

# --- Show the tracking number if present ---
if url_id:
    st.markdown(f"**رقم التتبع (ID):** `{url_id}`")
else:
    st.info("لا يوجد رقم تتبع في الرابط. يمكنك إدخاله يدوياً في النموذج أدناه.")

st.markdown("### الرجاء اختيار أحد الخيارات التالية:")

# --- Form section ---
with st.form("moh_form"):
    entered_id = st.text_input("رقم التتبع (ID)", value=url_id or "", help="أدخل رقم التتبع إذا لم يكن في الرابط")
    agree = st.checkbox("✅ موافق")
    disagree = st.checkbox("❌ غير موافق")

    submitted = st.form_submit_button("📤 إرسال الطلب")

    if submitted:
        if not entered_id.strip():
            st.warning("⚠️ الرجاء إدخال رقم التتبع (ID).")
        elif agree and disagree:
            st.warning("⚠️ لا يمكن اختيار الخيارين معاً.")
        elif not agree and not disagree:
            st.info("الرجاء اختيار أحد الخيارين قبل الإرسال.")
        else:
            choice = "موافق" if agree else "غير موافق"
            ts = datetime.now(timezone.utc).isoformat()

            payload = {
                "id": entered_id.strip(),    # your tracking number
                "choice": choice,            # user selection
                "timestamp_utc": ts
            }

            # (A) Save locally (optional)
            if SAVE_LOCAL_CSV:
                newrow = pd.DataFrame([payload])
                if os.path.exists(LOCAL_CSV_NAME):
                    old = pd.read_csv(LOCAL_CSV_NAME)
                    df = pd.concat([old, newrow], ignore_index=True)
                else:
                    df = newrow
                df.to_csv(LOCAL_CSV_NAME, index=False, encoding="utf-8-sig")

            # (B) Send to webhook
            send_ok = True
            send_msg = "تم إرسال الطلب بنجاح."
            try:
                r = requests.post(WEBHOOK_URL, json=payload, timeout=TIMEOUT_SEC)
                if r.status_code >= 400:
                    send_ok = False
                    send_msg = f"تعذر الإرسال (HTTP {r.status_code})."
            except Exception as e:
                send_ok = False
                send_msg = f"تعذر الإرسال: {e}"

            if send_ok:
                st.success(f"✅ {send_msg}\n\nرقم التتبع: `{payload['id']}` — الإختيار: **{choice}**")
            else:
                st.error(f"❌ {send_msg}\n\nرقم التتبع: `{payload['id']}` — الإختيار: **{choice}**\n(تم الحفظ محليًا: {SAVE_LOCAL_CSV})")

st.write("---")
st.caption("© 2025 وزارة الصحة - نظام طلب مشاركة البيانات")
