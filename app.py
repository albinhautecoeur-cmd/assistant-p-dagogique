import streamlit as st
import json
import os
import time
from openai import OpenAI
import docx
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
from PIL import Image

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Assistant pédagogique", layout="wide")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

PROMPT_PEDAGOGIQUE = """
Tu es un assistant pédagogique bienveillant.
Explique clairement, simplement, avec des exemples si nécessaire.
Ne dépasse pas 60 mots.
Tu ne donnes jamais la réponse directement, tu guides progressivement l'élève.
Voici le document de l'élève :
"""

USERS_FILE = "users.json"
ACTIVE_USERS_FILE = "active_users.json"
SESSION_TIMEOUT = 3600  # 1 heure

POPPLER_PATH = r"C:\Users\ghysc\OneDrive\Bureau\assistant pédagogique\poppler-25.12.0\Library\bin"  # <--- ton chemin Poppler

# ======================
# UTILITAIRES
# ======================
def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def load_active_users():
    if not os.path.exists(ACTIVE_USERS_FILE):
        return {}
    with open(ACTIVE_USERS_FILE, "r") as f:
        return json.load(f)

def save_active_users(data):
    with open(ACTIVE_USERS_FILE, "w") as f:
        json.dump(data, f)

def clean_expired_sessions():
    active_users = load_active_users()
    now = time.time()
    updated = {u: t for u, t in active_users.items() if now - t < SESSION_TIMEOUT}
    save_active_users(updated)

# ======================
# SESSION
# ======================
if "connected" not in st.session_state:
    st.session_state.connected = False
if "username" not in st.session_state:
    st.session_state.username = None
if "document_content" not in st.session_state:
    st.session_state.document_content = ""
if "document_images" not in st.session_state:
    st.session_state.document_images = []

clean_expired_sessions()

USERS = load_users()
active_users = load_active_users()

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Connexion"):
        if username in USERS and USERS[username] == password:
            if username in active_users:
                st.error("❌ Ce compte est déjà connecté ailleurs.")
            else:
                active_users[username] = time.time()
                save_active_users(active_users)
                st.session_state.connected = True
                st.session_state.username = username
                st.success("Connexion réussie")
                st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect")
    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique IA")

if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)

    st.session_state.connected = False
    st.session_state.username = None
    st.rerun()

# Colonnes principales
col_doc, col_chat = st.columns([1, 2])  # 1/3 document, 2/3 chat

# ======================
# DOCUMENT
# ======================
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        st.session_state.document_content = ""
        st.session_state.document_images = []

        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            st.session_state.document_content = content
            st.text_area("Contenu du document", content, height=400)

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            st.session_state.document_content = content
            st.text_area("Contenu du document", content, height=400)

        elif uploaded_file.name.endswith(".pdf"):
            # Convertir PDF en images
            try:
                pdf_bytes = uploaded_file.read()
                images = convert_from_bytes(pdf_bytes, dpi=150, poppler_path=POPPLER_PATH)
                st.session_state.document_images = images
                for img in images:
                    st.image(im)

