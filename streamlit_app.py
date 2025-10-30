# app.py
import os
import json
import time
import requests
import streamlit as st
from datetime import datetime, timezone

# ================== CONFIG ==================
WEBHOOK_URL = "https://tofyz.app.n8n.cloud/webhook-test/moh-form"  # your n8n test webhook
REQUEST_TIMEOUT = 8
RETRIES = 3
BACKOFF = 1.6  # exponential backoff factor
# ============================================

st.set_page_config(
    page_title="نموذج طلب مشاركة البيانات - MOH Data Request Form",
    page_icon="📄",
    layout="centered"
)

# ---- RTL styling ----
st.markdown(
    "<style>body{direction:rtl;text-align:right;font-family:Tahoma,Arial,sans-serif}</style>",
    unsafe_allow_html=True
)

# ---- Query params helper (Streamlit new/old) ----
def get_query_params():
    try:
        return st.query_params        # ≥ 1.30
    except Exception:
        return st.experimental_get_query_params()

qp = get_query_params()
url_id = None
if "id" in qp:
    v = qp["id"]
    url_id = v[0] if isinstance(v, list) else v

# ---- Header ----
st.markdown("<h1 style='text-align:center;'>📄 نموذج طلب مشاركة البيانات</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;'>MOH Data Request Form</h3>", unsafe_allow_html=True)
st.write("---")

if url_id:
    st.markdown(f"**رقم التتبع (ID):** `{url_id}`")
else:
    st.info("لا يوجد رقم تتبع في الرابط. يمكنك إدخاله يدوياً في النموذج أدناه.")

st.markdown("### الرجاء اختيار أحد الخيارات التالية:")

# ---- Form ----
with st.form("moh_form"):
    entered_id = st.text_input("رقم التتبع (ID)", value=url_id or "", help="أدخل رقم التتبع إذا لم يكن في الرابط")
    agree = st.checkbox("✅ موافق")
    disagree = st.checkbox("❌ غير موافق")
    submitted = st.form_submit_button("📤 إرسال الطلب")

    if submitted:
        # Validation
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
                "id": entered_id.strip(),
                "choice": choice,
                "timestamp_utc": ts
            }

            # POST with simple retries
            ok, resp_text = False, ""
            for i in range(RETRIES):
                try:
                    r = requests.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT)
                    ok, resp_text = r.ok, (r.text or "")
                    if ok:
                        break
                except Exception as e:
                    resp_text = str(e)
                time.sleep(BACKOFF ** i)

            if ok:
                st.success(f"✅ تم إرسال الطلب بنجاح.\n\nرقم التتبع: `{payload['id']}` — الإختيار: **{choice}**")
                if resp_text:
                    st.caption(f"رد الخادم: {resp_text[:200]}")
            else:
                st.error(f"❌ تعذر الإرسال إلى الخادم بعد عدة محاولات. الرجاء المحاولة لاحقاً.")
                st.caption(f"التفاصيل: {resp_text[:200]}")

st.write("---")
st.caption("© 2025 وزارة الصحة - نظام طلب مشاركة البيانات")
