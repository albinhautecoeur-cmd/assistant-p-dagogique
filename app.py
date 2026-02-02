import streamlit as st
import json
import os
import time
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
Voici le document de l'élève :
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
        active_users = clean_expired_sessions()
        if username in USERS and USERS[username] == password:
            active_users = load_active_users()
            if username in active_users:
                st.error("❌ Ce compte est déjà connecté sur un autre appareil.")
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
st.title("🧠 Mon Assistant pédagogique")

if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)

    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_images = []
    st.session_state.chat_history = []
    st.experimental_set_query_params()
    st.stop()

col_doc, col_chat = st.columns([1, 2])

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

    # 🔁 AFFICHAGE DU PLUS RÉCENT AU PLUS ANCIEN
    for msg in reversed(st.session_state.chat_history):
        st.markdown("**❓ Question :**")
        st.write(msg["question"])
        st.markdown("**🤖 Assistant :**")
        st.write(msg["answer"])
        st.markdown("---")


