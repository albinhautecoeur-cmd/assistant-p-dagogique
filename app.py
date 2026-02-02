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

    login_clicked = st.button("Connexion")
    if login_clicked:
        if username in USERS and USERS[username] == password:
            if username in active_users:
                st.error("❌ Ce compte est déjà connecté ailleurs.")
            else:
                active_users[username] = time.time()
                save_active_users(active_users)
                st.session_state.connected = True
                st.session_state.username = username
                st.success("Connexion réussie")
                st.experimental_rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect")
    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique IA")

# Bouton de déconnexion
if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)
    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_images = []
    st.experimental_rerun()

col_doc, col_chat = st.columns([1,1])

# --------------------
# DOCUMENT
# --------------------
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt","docx","pdf"])

    if uploaded_file:
        content = ""
        images = []

        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            st.text_area("Contenu du document", content, height=400)

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            st.text_area("Contenu du document", content, height=400)

        elif uploaded_file.name.endswith(".pdf"):
            pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            for page in pdf:
                content += page.get_text()
            uploaded_file.seek(0)
            pages = convert_from_bytes(uploaded_file.read(), dpi=150)
            for page in pages:
                images.append(page)
            for img in images:
                st.image(img, use_column_width=True)

        st.session_state.document_content = content
        st.session_state.document_images = images

# --------------------
# CHAT + RAPPEL
# --------------------
with col_chat:
    # Rappel de cours
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Mots-clés pour rappel")
    rappel_clicked = st.button("Obtenir le rappel")
    if rappel_clicked and mots_cles:
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
        st.write(response.choices[0].message.content)

    # Chat
    st.subheader("💬 Chat pédagogique")
    question = st.text_area("Ta question")
    send_clicked = st.button("Envoyer")
    if send_clicked and question:
        prompt = (
            PROMPT_PEDAGOGIQUE
            + "\n\nDOCUMENT:\n"
            + st.session_state.document_content
            + "\n\nQUESTION:\n"
            + question
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        st.markdown("**🤖 Assistant :**")
        st.write(response.choices[0].message.content)
