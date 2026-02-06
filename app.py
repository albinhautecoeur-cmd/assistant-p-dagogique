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
TOKENS_DIR = "tokens"
SESSION_TIMEOUT = 60
ADMIN_USER = "ahautecoeur2"

TOKEN_COST_PER_1K = 0.0015

os.makedirs(TOKENS_DIR, exist_ok=True)

# ======================
# UTILITAIRES
# ======================
def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def get_password(user):
    if isinstance(USERS[user], dict):
        return USERS[user]["password"]
    return USERS[user]

def get_etablissement(user):
    if isinstance(USERS[user], dict):
        return USERS[user].get("etablissement", "etablissement_defaut")
    return "etablissement_defaut"

def get_token_file(etab):
    path = os.path.join(TOKENS_DIR, etab)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "tokens.json")

def load_tokens(etab):
    file = get_token_file(etab)
    if not os.path.exists(file):
        return {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0}
    with open(file, "r") as f:
        return json.load(f)

def save_tokens(etab, data):
    file = get_token_file(etab)
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def add_tokens(etab, prompt_tokens, completion_tokens):
    data = load_tokens(etab)
    data["prompt"] += prompt_tokens
    data["completion"] += completion_tokens
    data["total"] += prompt_tokens + completion_tokens
    data["cost"] = (data["total"] / 1000) * TOKEN_COST_PER_1K
    save_tokens(etab, data)

def count_tokens(text, model="gpt-4o-mini"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

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
    img = Image.new("RGB", (width, 20 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    y = 5
    for line in lines:
        draw.text((10, y), line, fill="black", font=font)
        y += 20
    return img

def fix_latex_for_streamlit(text: str) -> str:
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.S)
    return text

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
            if username_input in USERS and get_password(username_input) == password_input:
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

etab = get_etablissement(st.session_state.username)

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

        elif uploaded_file.name.endswith(".pdf"):
            pdf_bytes = uploaded_file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in pdf_doc:
                content += page.get_text()
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
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
            add_tokens(etab, count_tokens(mots_cles), count_tokens(response.choices[0].message.content))
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
            add_tokens(etab, count_tokens(prompt), count_tokens(response.choices[0].message.content))
            st.session_state.chat_history.append({"question": q, "answer": response.choices[0].message.content})
            st.session_state.question_input = ""

    st.text_input("Ta question", key="question_input", on_change=submit_question)

    for msg in reversed(st.session_state.chat_history):
        st.markdown("**❓ Question :**")
        st.markdown(msg["question"])
        st.markdown("**🤖 BiNo :**")
        st.markdown(fix_latex_for_streamlit(msg["answer"]))
        st.markdown("---")

# ======================
# ADMIN VIEW (PAR ÉTABLISSEMENT)
# ======================
if st.session_state.username == ADMIN_USER:
    st.subheader("📊 Tokens cumulés par établissement")
    for folder in os.listdir(TOKENS_DIR):
        data = load_tokens(folder)
        st.write(f"🏫 {folder} → Prompt: {data['prompt']} | Completion: {data['completion']} | Total: {data['total']} | €: {data['cost']:.4f}")

