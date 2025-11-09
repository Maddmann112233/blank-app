# MOH Admin App

A bilingual Streamlit dashboard for MOH data-sharing workflows.  
It connects to Google Sheets (read-only) and sends approval/decline decisions via n8n webhooks.  
Designed with a teal glassmorphic theme (`ChatGPT Image Nov 9, 2025, 02_38_42 AM.png`) for clarity and focus.

---

## Table of Contents
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Project Structure](#project-structure)
- [Git Workflow](#git-workflow)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Handling Merge Conflicts](#handling-merge-conflicts)
- [Versioning & Releases](#versioning--releases)
- [Testing](#testing)
- [CI/CD](#cicd)
- [License](#license)

---

## Quick Start

```bash
# 1) Clone the repository
git clone <YOUR_REPO_URL>.git
cd <YOUR_REPO_NAME>

# 2) Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Run the Streamlit app
streamlit run app.py
