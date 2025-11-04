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

# --- Header ---
st.markdown("<h1 style='text-align:center;'>نموذج طلب مشاركة البيانات</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;'>MOH Data Request Form</h3>", unsafe_allow_html=True)
st.write("---")

if resume_url:
    st.caption("سيتم الإرسال تلقائياً إلى رابط الاستئناف (resumeUrl) من n8n إن لم تُدخل رابطاً يدوياً.")
else:
    st.caption("يمكنك إدخال رابط الويب هوك أو رابط الاستئناف يدوياً أدناه.")

st.write("### الرجاء تعبئة الحقول التالية:")

# --- Form ---
with st.form("moh_form"):
    manual_webhook = st.text_input(
        "رابط الويب هوك / الاستئناف (اختياري)",
        value=resume_url or "",
        help="ألصق هنا رابط الاستئناف ($execution.resumeUrl) أو رابط الويب هوك الثابت."
    )

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
        # Validation
        if agree and disagree:
            st.warning("لا يمكن اختيار الخيارين معاً.")
        elif not agree and not disagree:
            st.info("الرجاء اختيار أحد الخيارين قبل الإرسال.")
        elif disagree and not reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            choice = "موافق" if agree else "غير موافق"
            ts = datetime.now(timezone.utc).isoformat()

            payload = {
                "choice": choice,
                "timestamp_utc": ts
            }
            if disagree:
                payload["reason_for_refusal"] = reason.strip()

            # Determine target URL priority: manual field > resume param > default
            target_url = (manual_webhook or "").strip() or resume_url or DEFAULT_WEBHOOK_URL

            if not target_url:
                st.error("لم يتم تحديد أي رابط للإرسال. الرجاء لصق رابط الويب هوك أو الاستئناف.")
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
