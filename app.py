import streamlit as st
import json
import os
import time
from openai import OpenAI
from PIL import Image
import io
import docx
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes, convert_from_path
 # pip install pdf2image

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

# Colonnes : gauche pour document, droite pour chat + rappel
col_doc, col_chat = st.columns([1, 2])  # proportion 1:2

# ======================
# DOCUMENT (gauche)
# ======================
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        content = ""
        images = []

        # ---------- TXT ----------
        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            # convertir texte en image simple pour affichage
            img = Image.new("RGB", (600, 800), color="white")
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), content[:5000], fill="black")  # afficher seulement les 5000 premiers caractères
            images.append(img)

        # ---------- DOCX ----------
        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            # convertir chaque paragraphe en image
            img = Image.new("RGB", (600, max(800, 20*len(doc.paragraphs))), color="white")
            draw = ImageDraw.Draw(img)
            y = 10
            for p in doc.paragraphs:
                draw.text((10, y), p.text, fill="black")
                y += 20
            images.append(img)

        # ---------- PDF ----------
        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in pdf_doc:
                content += page.get_text()
            pdf_images = convert_from_bytes(pdf_bytes, dpi=150)
            images.extend(pdf_images)

        st.session_state.document_content = content
        st.session_state.document_images = images

        # Affichage des images
        st.subheader("📄 Aperçu du document")
        for img in images:
            st.image(img, use_column_width=True)

# ======================
# CHAT + RAPPEL DE COURS (droite)
# ======================
with col_chat:
    # 🔹 Rappel de cours
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

    # 🔹 Chat pédagogique
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

