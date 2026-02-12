"""AI-Assisted Workflow Authoring — navigation entrypoint."""

import streamlit as st

workflow_page = st.Page("pages/workflow.py", title="Workflow Authoring", icon="🔄")
docs_page = st.Page("pages/documentation.py", title="Documentation", icon="📖")

pg = st.navigation([workflow_page, docs_page])
st.set_page_config(page_title="AI Workflow Authoring", page_icon="🔄", layout="wide")
pg.run()
