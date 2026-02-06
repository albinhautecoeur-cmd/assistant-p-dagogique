import streamlit as st
import json
import os
import time
import re
import tiktoken
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import io
import docx
import fitz  # PyMuPDF

# ======================
# SESSION STATE INITIALISATION
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
# CONFIG
# ======================
st.set_page_config(page_title="Assistant pédagogique", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #eaf3ff; }
h1, h2, h3 { color: #1f3c88; }
.stButton>button {
    background: linear-gradient(135deg, #7aa2ff, #a5c9ff);
    color: white;
    border-radius: 20px;
    padding: 0.5em 1.2em;
    border: none;
    font-weight: bold;
}
.stTextInput>div>div>input,
.stTextArea textarea {
    border-radius: 15px;
    border: 1px solid #aac4ff;
    background-color: #f5f9ff;
}
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

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

USERS_FILE = "users.json"
ACTIVE_USERS_FILE = "active_users.json"
TOKENS_FILE = "tokens.json"
SESSION_TIMEOUT = 60
ADMIN_USER = "ahautecoeur2"

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

def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return {}
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)

def save_tokens(data):
    with open(TOKENS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_tokens(username, prompt_tokens, completion_tokens):
    data = load_tokens()
    if username not in data:
        data[username] = {"prompt": 0, "completion": 0, "total": 0}
    data[username]["prompt"] += prompt_tokens
    data[username]["completion"] += completion_tokens
    data[username]["total"] += prompt_tokens + completion_tokens
    save_tokens(data)

def count_tokens(text, model="gpt-4o-mini"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

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

# ======================
# FIX LATEX
# ======================
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
# CHARGEMENT UTILISATEURS
# ======================
USERS = load_users()
active_users = clean_expired_sessions()

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")
    with st.form("login_form"):
        username_input = st.text_input("Identifiant")
        password_input = st.text_input("Mot de passe", type="password")
        submitted_login = st.form_submit_button("Connexion")
        if submitted_login:
            active_users = clean_expired_sessions()
            if username_input in USERS and USERS[username_input] == password_input:
                if username_input in active_users:
                    st.error("❌ Ce compte est déjà connecté sur un autre appareil.")
                else:
                    st.session_state.connected = True
                    st.session_state.username = username_input
                    active_users[username_input] = time.time()
                    save_active_users(active_users)
                    st.success("Connexion réussie")
            else:
                st.error("Identifiant ou mot de passe incorrect")
    st.stop()

active_users = load_active_users()
active_users[st.session_state.username] = time.time()
save_active_users(active_users)

# ======================
# INTERFACE
# ======================
st.title("🧠 BiNo, mon Assistant Pédagogique")

with st.form("logout_form"):
    submitted_logout = st.form_submit_button("🚪 Déconnexion")
    if submitted_logout:
        active_users = load_active_users()
        if st.session_state.username in active_users:
            del active_users[st.session_state.username]
            save_active_users(active_users)
        st.session_state.connected = False
        st.session_state.username = None
        st.session_state.document_content = ""
        st.session_state.document_images = []
        st.session_state.chat_history = []
        st.stop()

col_doc, col_chat = st.columns([1, 1])

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
# RAPPEL + CHAT
# ======================
with col_chat:
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Ne mets ici que des mots-clés")

    if st.button("Obtenir le rappel"):
        if mots_cles:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": mots_cles}]
            )
            prompt_tokens = count_tokens(mots_cles)
            completion_tokens = count_tokens(response.choices[0].message.content)
            add_tokens(st.session_state.username, prompt_tokens, completion_tokens)

            st.markdown("**📚 Rappel de cours :**")
            st.markdown(fix_latex_for_streamlit(response.choices[0].message.content))

    st.subheader("💬 Chat pédagogique")

    def submit_question():
        q = st.session_state.question_input
        if q:
            prompt = PROMPT_PEDAGOGIQUE + "\n\nDOCUMENT:\n" + st.session_state.document_content + "\n\nQUESTION:\n" + q
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )

            prompt_tokens = count_tokens(prompt)
            completion_tokens = count_tokens(response.choices[0].message.content)
            add_tokens(st.session_state.username, prompt_tokens, completion_tokens)

            st.session_state.chat_history.append(
                {"question": q, "answer": response.choices[0].message.content}
            )
            st.session_state.question_input = ""

    st.text_input("Ta question", key="question_input", on_change=submit_question)

    for msg in reversed(st.session_state.chat_history):
        st.markdown("**❓ Question :**")
        st.markdown(msg["question"])
        st.markdown("**🤖 Assistant :**")
        st.markdown(fix_latex_for_streamlit(msg["answer"]))
        st.markdown("---")

# ======================
# ADMIN VIEW
# ======================
if st.session_state.username == ADMIN_USER:
    st.subheader("📊 Consommation de tokens (ADMIN)")
    data = load_tokens()
    for user, stats in data.items():
        st.write(f"👤 {user} → {stats['total']} tokens")
