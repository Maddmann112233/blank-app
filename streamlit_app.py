# app.py
import os
import time
import json
import urllib.parse
import requests
import streamlit as st
from datetime import datetime, timezone

# ============== OPTIONAL FALLBACK ==============
# If no resume URL is provided in the query string, we can fall back to a fixed webhook.
WEBHOOK_URL_FALLBACK = ""  # e.g. "https://your-n8n/webhook/moh-form" or leave empty
REQUEST_TIMEOUT = 10
RETRIES = 3
BACKOFF = 1.6
# ==============================================

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

def qp_get_one(name: str):
    if name not in qp:
        return None
    v = qp[name]
    return v[0] if isinstance(v, list) else v

# Read params
url_id = qp_get_one("id")
resume_param = qp_get_one("resume") or qp_get_one("resumeUrl")

# Decode resume URL if provided (it should be URL-encoded from n8n)
resume_url = None
if resume_param:
    # handle double-encoding gracefully
    try:
        resume_url = urllib.parse.unquote(resume_param)
        # if still encoded (rare), unquote again
        if "%2F" in resume_url or "%3A" in resume_url:
            resume_url = urllib.parse.unquote(resume_url)
    except Exception:
        resume_url = resume_param  # fallback to raw

# ---- Header ----
st.markdown("<h1 style='text-align:center;'>📄 نموذج طلب مشاركة البيانات</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;'>MOH Data Request Form</h3>", unsafe_allow_html=True)
st.write("---")

# Show context
if url_id:
    st.markdown(f"**رقم التتبع (ID):** `{url_id}`")
else:
    st.info("لا يوجد رقم تتبع (ID) في الرابط. يمكنك إدخاله يدوياً في النموذج أدناه.")

if resume_url:
    st.caption("سيتم إرسال الرد مباشرةً إلى تدفق n8n (Wait node) عبر رابط الاستئناف المزوّد.")
else:
    if WEBHOOK_URL_FALLBACK:
        st.caption("لم يتم تمرير resumeUrl — سيتم الإرسال إلى عنوان webhook البديل (fallback).")
    else:
        st.caption("لم يتم تمرير resumeUrl ولا يوجد بديل محدد — لن يتم الإرسال إلى أي خادم.")

st.write("### الرجاء اختيار أحد الخيارات التالية:")

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

            # decide target URL: resumeUrl > fallback
            target_url = resume_url or WEBHOOK_URL_FALLBACK
            if not target_url:
                st.error("❌ لا يوجد resumeUrl ولا عنوان webhook بديل. أعد فتح الرابط من n8n أو عيّن WEBHOOK_URL_FALLBACK.")
            else:
                ok, resp_text = False, ""
                for i in range(RETRIES):
                    try:
                        # Wait node default is fine with POST + JSON
                        r = requests.post(target_url, json=payload, timeout=REQUEST_TIMEOUT)
                        ok, resp_text = r.ok, (r.text or "")
                        if ok:
                            break
                    except Exception as e:
                        resp_text = str(e)
                    time.sleep(BACKOFF ** i)

                if ok:
                    st.success(f"✅ تم إرسال الطلب بنجاح.\n\nرقم التتبع: `{payload['id']}` — الإختيار: **{choice}**")
                    if resp_text:
                        st.caption(f"رد الخادم: {resp_text[:300]}")
                else:
                    st.error("❌ تعذر الإرسال إلى رابط الاستئناف/الويب هوك بعد عدة محاولات.")
                    if resp_text:
                        st.caption(f"التفاصيل: {resp_text[:300]}")

st.write("---")
st.caption("© 2025 وزارة الصحة - نظام طلب مشاركة البيانات")
