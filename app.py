import streamlit as st
import json
import os
import time
from openai import OpenAI
from PIL import Image
import io
import docx
import fitz  # PyMuPDF

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
SESSION_TIMEOUT = 60  # 1 minute

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
    """Supprime les sessions expirées depuis plus de SESSION_TIMEOUT secondes"""
    active_users = load_active_users()
    now = time.time()
    updated = {u: t for u, t in active_users.items() if now - t < SESSION_TIMEOUT}
    save_active_users(updated)
    return updated

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

# Nettoyage des sessions expirées
active_users = clean_expired_sessions()
USERS = load_users()

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Connexion"):
        active_users = clean_expired_sessions()
        if username in USERS and USERS[username] == password:
            if username in active_users:
                st.error("❌ Ce compte est déjà connecté ailleurs.")
            else:
                active_users[username] = time.time()
                save_active_users(active_users)
                st.session_state.connected = True
                st.session_state.username = username
                st.success("Connexion réussie")
        else:
            st.error("Identifiant ou mot de passe incorrect")
    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique IA")

# Déconnexion
if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)
    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_images = []
    st.experimental_set_query_params()  # simple refresh
    st.stop()

col_doc, col_chat = st.columns([1, 2])  # document plus étroit que le chat

# ======================
# DOCUMENT
# ======================
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        st.session_state.document_images = []
        content = ""

        # TXT
        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            st.session_state.document_content = content
            st.text_area("Contenu du document", content, height=400)

        # DOCX
        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            st.session_state.document_content = content

            images = []
            for rel in doc.part._rels:
                rel_obj = doc.part._rels[rel]
                if "image" in rel_obj.target_ref:
                    image_data = rel_obj.target_part.blob
                    img = Image.open(io.BytesIO(image_data))
                    img.thumbnail((600, 800))
                    images.append(img)
            if images:
                st.session_state.document_images = images
                st.image(images, use_column_width=True)

        # PDF
        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            content = ""
            images = []
            for page in pdf_doc:
                content += page.get_text()
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((600, 800))
                images.append(img)
            st.session_state.document_content = content
            st.session_state.document_images = images
            if images:
                st.image(images, use_column_width=True)

# ======================
# RAPPEL DE COURS
# ======================
with col_chat:
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Mots-clés")

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
            st.write(response.choices[0].message.content)

# ======================
# CHAT
# ======================
with col_chat:
    st.subheader("💬 Chat pédagogique")
    question = st.text_area("Ta question")

    if st.button("Envoyer"):
        if question:
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
