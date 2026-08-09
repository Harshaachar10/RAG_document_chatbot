"""
app.py
------
Streamlit UI for the Document Q&A Chatbot, built on rag_pipeline.py
(your notebook's pipeline, completed with retrieval + Gemini generation).
"""

import os

import streamlit as st
from dotenv import load_dotenv

from rag_pipeline import process_uploaded_pdf, answer_question

load_dotenv()

st.set_page_config(page_title="Reading Room", page_icon="🕯️", layout="wide")

# ---------------- Theme ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

:root {
    --ink: #10151c;
    --panel: #171f29;
    --panel-raised: #1e2733;
    --amber: #e2a33e;
    --amber-soft: rgba(226, 163, 62, 0.14);
    --parchment: #efe8da;
    --muted: #8a95a3;
    --border: rgba(226, 163, 62, 0.18);
}

.stApp {
    background: radial-gradient(circle at 15% -10%, #1b2430 0%, var(--ink) 55%);
    color: var(--parchment);
}

section[data-testid="stSidebar"] {
    background: var(--panel);
    border-right: 1px solid var(--border);
}

h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    letter-spacing: 0.2px;
}

body, p, div, span, li {
    font-family: 'Inter', sans-serif;
}

.hero {
    padding: 2.6rem 2.8rem;
    border-radius: 4px;
    background: linear-gradient(135deg, #1c2531 0%, #141b24 100%);
    border: 1px solid var(--border);
    border-left: 3px solid var(--amber);
    margin-bottom: 1.8rem;
}
.hero .eyebrow {
    color: var(--amber);
    font-size: 0.78rem;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 0.6rem;
}
.hero h1 {
    font-size: 2.3rem;
    margin: 0 0 0.6rem 0;
    color: var(--parchment);
}
.hero p {
    color: var(--muted);
    font-size: 1.02rem;
    max-width: 640px;
    margin: 0;
}

.stChatMessage {
    background: var(--panel-raised) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}

[data-testid="stFileUploader"] {
    border: 1px dashed var(--border);
    border-radius: 4px;
    padding: 0.6rem;
    background: var(--amber-soft);
}

.stButton > button {
    background: var(--amber) !important;
    color: #171207 !important;
    border: none !important;
    border-radius: 3px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
}
.stButton > button:hover {
    background: #f0b555 !important;
}

hr, div[data-testid="stDivider"] {
    border-color: var(--border) !important;
}

.doc-badge {
    display: inline-block;
    background: var(--amber-soft);
    border: 1px solid var(--border);
    color: var(--amber);
    padding: 0.3rem 0.7rem;
    border-radius: 3px;
    font-size: 0.85rem;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Session state ----------------
if "rag_retriever" not in st.session_state:
    st.session_state.rag_retriever = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_name" not in st.session_state:
    st.session_state.file_name = None

# ---------------- Hero ----------------
st.markdown("""
<div class="hero">
    <div class="eyebrow">Document Q&A</div>
    <h1>🕯️ The Reading Room</h1>
    <p>Bring a PDF — a report, a paper, a policy — and sit with it. Ask what you need to know,
    and every answer stays grounded in the pages you handed over.</p>
</div>
""", unsafe_allow_html=True)

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Settings")

    api_key_input = st.text_input(
        "Google API Key", type="password", value=os.getenv("GOOGLE_API_KEY", "")
    )
    if api_key_input:
        os.environ["GOOGLE_API_KEY"] = api_key_input

    k_value = st.slider("Chunks to retrieve (k)", 1, 10, 4)

    st.divider()
    st.subheader("📤 Upload a PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    if uploaded_file is not None and st.session_state.file_name != uploaded_file.name:
        with st.spinner("Reading, chunking, and indexing your document..."):
            try:
                st.session_state.rag_retriever = process_uploaded_pdf(
                    uploaded_file.read(), uploaded_file.name
                )
                st.session_state.file_name = uploaded_file.name
                st.session_state.messages = []
                st.success(f"Indexed: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error processing PDF: {e}")

    if st.session_state.rag_retriever is not None:
        st.markdown(f'<span class="doc-badge">📄 {st.session_state.file_name}</span>',
                    unsafe_allow_html=True)
        if st.button("Clear document", use_container_width=True):
            st.session_state.rag_retriever = None
            st.session_state.file_name = None
            st.session_state.messages = []
            st.rerun()

# ---------------- Main chat area ----------------
if st.session_state.rag_retriever is None:
    st.info("👈 Upload a PDF in the sidebar to begin.")
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if question := st.chat_input("Ask a question about the document..."):
        if not api_key_input:
            st.error("Add your Google API key in the sidebar first.")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Searching the document..."):
                    try:
                        answer = answer_question(
                            st.session_state.rag_retriever, question, top_k=k_value
                        )
                    except Exception as e:
                        answer = f"Error generating answer: {e}"
                    st.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})