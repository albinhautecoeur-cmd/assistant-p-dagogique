import streamlit as st
import json
import os
import time
from openai import OpenAI
import docx
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from pdf2image import convert_from_bytes

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

# ======================
# FONCTIONS UTILITAIRES
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

# ======================
# COLONNES DOCUMENT / CHAT
# ======================
col_doc, col_chat = st.columns([1, 1.5])  # document plus petit que chat

# ======================
# DOCUMENT
# ======================
with col_doc:
    st.subheader("📄 Document")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        st.session_state.document_images = []  # réinitialiser
        content_text = ""

        if uploaded_file.name.endswith(".txt"):
            content_text = uploaded_file.read().decode("utf-8")
            st.text_area("Contenu du document (pour IA)", content_text, height=400)
            st.session_state.document_images = []  # pas d'image pour txt

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content_text = "\n".join([p.text for p in doc.paragraphs])
            st.text_area("Contenu du document (pour IA)", content_text, height=400)
            # Affichage image non dispo pour DOCX simple, peut être amélioré

        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            # Texte pour IA
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in pdf_doc:
                content_text += page.get_text()
            st.session_state.document_content = content_text
            # Conversion PDF -> images pour affichage
            images = convert_from_bytes(pdf_bytes, dpi=150)
            for img in images:
                st.image(img, use_column_width=True)
                st.session_state.document_images.append(img)

        st.session_state.document_content = content_text

# ======================
# CHAT ET RAPPEL
# ======================
with col_chat:
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Mots-clés pour rappel")

    if st.button("Obtenir le rappel"):
        if mots_cles:
            prompt_rappel = f"""
Tu es un assistant pédagogique bienveillant.
Fais un rappel de cours clair basé sur ces mots-clés : {mots_cles}
Maximum 100 mots.
"""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_rappel}]
            )
            st.markdown("**📚 Rappel de cours :**")
            st.write(response.cho
