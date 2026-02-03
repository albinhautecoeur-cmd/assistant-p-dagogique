import streamlit as st
import json
import os
import time
import re
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
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
Quand tu écris des formules mathématiques :
- utilise \\( ... \\) pour les formules en ligne
- utilise \\[ ... \\] pour les formules en bloc
- n’utilise jamais de blocs de code LaTeX
"""

USERS_FILE = "users.json"
ACTIVE_USERS_FILE = "active_users.json"
SESSION_TIMEOUT = 60

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
    return updated

def text_to_image(text, width=600):
    font = ImageFont.load_default()
    lines = text.split("\n")
    img = Image.new("RGB", (width, 20 + 15 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        draw.text((10, y), line, fill="black", font=font)
        y += 15
    return img

# ======================
# ✅ RENDU LATEX STREAMLIT — VERSION SAINE
# ======================
def render_text_with_math(text: str):
    """
    Affiche le texte normalement
    et toute expression mathématique en blocs $$...$$ séparés
    """
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()

        is_math = (
            stripped.startswith("\\")
            or any(cmd in stripped for cmd in ["\\vec", "\\frac", "\\sqrt"])
            or ("=" in stripped and any(c.isalpha() for c in stripped))
        )

        if is_math:
            st.markdown(f"$$ {stripped} $$")
        else:
            st.markdown(stripped)

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
if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

USERS = load_users()
active_users = clean_expired_sessions()

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Connexion"):
        if username in USERS and USERS[username] == password:
            active = load_active_users()
            if username in active:
                st.error("Compte déjà connecté.")
            else:
                active[username] = time.time()
                save_active_users(active)
                st.session_state.connected = True
                st.session_state.username = username
        else:
            st.error("Identifiants incorrects")
    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Mon Assistant pédagogique")

col_doc, col_chat = st.columns([1, 2])

# ======================
# DOCUMENT
# ======================
with col_doc:
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        content = uploaded_file.read().decode("utf-8", errors="ignore")
        st.session_state.document_content = content
        st.image(text_to_image(content), use_column_width=True)

# ======================
# CHAT
# ======================
def submit_question():
    q = st.session_state.question_input
    if q:
        prompt = PROMPT_PEDAGOGIQUE + "\n\n" + q
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.chat_history.append(response.choices[0].message.content)
        st.session_state.question_input = ""

with col_chat:
    st.subheader("💬 Chat pédagogique")

    with st.form("chat"):
        st.text_area("Ta question", key="question_input")
        st.form_submit_button("Envoyer", on_click=submit_question)

    for answer in reversed(st.session_state.chat_history):
        render_text_with_math(answer)
        st.markdown("---")
