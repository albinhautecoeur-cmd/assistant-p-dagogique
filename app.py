import streamlit as st
import sqlite3
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
Ne dépasse pas 60 mots que ce soit pour les rappels ou pour la réponse chat.
Tu ne donnes jamais la réponse directement, tu guides progressivement l'élève.
Quand tu écris des formules mathématiques :
- utilise \( ... \) pour les formules en ligne
- utilise \[ ... \] pour les formules en bloc
- n’utilise jamais de blocs de code LaTeX

Voici le document de l'élève :
"""

DB_FILE = "users.db"
SESSION_TIMEOUT = 60  # en secondes

# ======================
# UTILITAIRES SQLITE
# ======================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = 1")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Table des utilisateurs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    # Table des sessions actives
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_sessions (
            username TEXT PRIMARY KEY,
            last_seen REAL,
            FOREIGN KEY(username) REFERENCES users(username)
        )
    """)
    conn.commit()
    conn.close()

def clean_expired_sessions():
    now = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_sessions WHERE ? - last_seen > ?", (now, SESSION_TIMEOUT))
    conn.commit()
    conn.close()

def is_user_active(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_sessions WHERE username = ?", (username,))
    active = cursor.fetchone() is not None
    conn.close()
    return active

def login_user(username):
    now = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO active_sessions (username, last_seen) VALUES (?, ?)", (username, now))
    conn.commit()
    conn.close()

def logout_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_sessions WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def validate_credentials(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    valid = cursor.fetchone() is not None
    conn.close()
    return valid

# Initialisation DB
init_db()
clean_expired_sessions()

# ======================
# SESSION STREAMLIT
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

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Connexion"):
        clean_expired_sessions()
        if validate_credentials(username, password):
            if is_user_active(username):
                st.error("❌ Ce compte est déjà connecté sur un autre appareil.")
            else:
                login_user(username)
                st.session_state.connected = True
                st.session_state.username = username
                st.success("Connexion réussie")
        else:
            st.error("Identifiant ou mot de passe incorrect")
    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Mon Assistant pédagogique")

if st.button("🚪 Déconnexion"):
    logout_user(st.session_state.username)
    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_images = []
    st.session_state.chat_history = []
    st.experimental_set_query_params()
    st.stop()

col_doc, col_chat = st.columns([1, 2])

# ======================
# UTILITAIRES DOCUMENTS
# ======================
def text_to_image(text, width=600):
    font = ImageFont.load_default()
    lines = text.split("\n")
    dummy_img = Image.new("RGB", (width, 1000))
    draw = ImageDraw.Draw(dummy_img)
    line_height = draw.textbbox((0,0), "Hg", font=font)[3] + 4
    height = line_height * len(lines) + 20
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        draw.text((10, y), line, fill="black", font=font)
        y += line_height
    return img

def fix_latex_for_streamlit(text: str) -> str:
    text = re.sub(r"I\s*\n\s*0", r"I_0", text)
    text = re.sub(r"10\s*\n\s*-\s*12", r"10^{-12}", text)
    text = re.sub(r"W\s*/\s*m\s*2", r"\\text{W/m}^2", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.S)
    lines = text.split("\n")
    fixed_lines = []
    for line in lines:
        stripped = line.strip()
        is_math_line = (
            "\\" in stripped
            and any(cmd in stripped for cmd in ["\\sqrt", "\\frac", "\\log"])
            and "=" in stripped
        )
        if is_math_line and not stripped.startswith("$"):
            fixed_lines.append(f"$$\n{stripped}\n$$")
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines)

# ======================
# DOCUMENT
# ======================
with col_doc:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        content = ""
        images = []

        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode("utf-8")
            images = [text_to_image(content)]

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs])
            images = [text_to_image(content)]
            for rel in doc.part._rels:
                rel_obj = doc.part._rels[rel]
                if "image" in rel_obj.target_ref:
                    image_data = rel_obj.target_part.blob
                    img = Image.open(io.BytesIO(image_data))
                    img.thumbnail((600, 800))
                    images.append(img)

        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in pdf_doc:
                content += page.get_text()
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((600, 800))
                images.append(img)

        st.session_state.document_content = content
        st.session_state.document_images = images
        st.image(images, use_column_width=True)

# ======================
# RAPPEL
# ======================
with col_chat:
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Ne mets ici que des Mots-clés, c'est suffisant")

    if st.button("Obtenir le rappel"):
        if mots_cles:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": mots_cles}]
            )
            st.markdown("**📚 Rappel de cours :**")
            st.markdown(fix_latex_for_streamlit(response.choices[0].message.content))

# ======================
# CHAT
# ======================
def submit_question():
    q = st.session_state.question_input
    if q:
        prompt = (
            PROMPT_PEDAGOGIQUE
            + "\n\nDOCUMENT:\n"
            + st.session_state.document_content
            + "\n\nQUESTION:\n"
            + q
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.chat_history.append(
            {"question": q, "answer": response.choices[0].message.content}
        )
        st.session_state.question_input = ""

with col_chat:
    st.subheader("💬 Chat pédagogique")
    with st.form("chat_form"):
        st.text_area("Ta question", key="question_input")
        st.form_submit_button("Envoyer", on_click=submit_question)
    for msg in reversed(st.session_state.chat_history):
        st.markdown("**❓ Question :**")
        st.markdown(msg["question"])
        st.markdown("**🤖 Assistant :**")
        st.markdown(fix_latex_for_streamlit(msg["answer"]))
        st.markdown("---")
