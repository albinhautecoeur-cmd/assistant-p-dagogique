import streamlit as st
import json
import os
import time
from openai import OpenAI
from PIL import Image
import io
import docx
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes  # pip install pdf2image

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
if "document_image" not in st.session_state:
    st.session_state.document_image = None

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
                st.experimental_set_query_params()  # simple refresh
                st.success("Connexion réussie")
        else:
            st.error("Identifiant ou mot de passe incorrect")

    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique IA")

# Bouton déconnexion
if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)

    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_image = None
    st.experimental_set_query_params()
    st.stop()

col_doc, col_chat = st.columns([1,1])

# ======================
# DOCUMENT
# ======================
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        # Pour TXT
        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            st.session_state.document_content = content
            st.text_area("Contenu du document", content, height=400)

        # Pour DOCX
        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            st.session_state.document_content = content

            # Convertir en image simple pour afficher
            images = []
            for rel in doc.part._rels:
                rel_obj = doc.part._rels[rel]
                if "image" in rel_obj.target_ref:
                    image_data = rel_obj.target_part.blob
                    image = Image.open(io.BytesIO(image_data))
                    image.thumbnail((600, 800))
                    images.append(image)
            if images:
                st.session_state.document_image = images[0]
                st.image(st.session_state.document_image)

        # Pour PDF
        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            content = ""
            for page in pdf_doc:
                content += page.get_text()
            st.session_state.document_content = content

            # Conversion en images pour affichage
            pages = convert_from_bytes(pdf_bytes, dpi=150)
            if pages:
                page_image = pages[0]
                page_image.thumbnail((600, 800))
                st.session_state.document_image = page_image
                st.image(st.session_state.document_image)

# ======================
# CHAT ET RAPPEL DE COURS
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
