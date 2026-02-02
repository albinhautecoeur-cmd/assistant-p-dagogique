import time

ACTIVE_USERS_FILE = "active_users.json"

def load_active_users():
    if not os.path.exists(ACTIVE_USERS_FILE):
        return {}
    with open(ACTIVE_USERS_FILE, "r") as f:
        return json.load(f)

def save_active_users(data):
    with open(ACTIVE_USERS_FILE, "w") as f:
        json.dump(data, f)

import streamlit as st
import json
import os
from openai import OpenAI
import docx
import fitz  # PyMuPDF

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Assistant pédagogique", layout="wide")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

PROMPT_PEDAGOGIQUE = """
Tu es un assistant pédagogique bienveillant.
Explique clairement, simplement, avec des exemples si nécessaire. Ne dépasse pas 60 mots.
Mais tu ne donnes jamais la réponse directement, tu guides progressivement l'élève.
Voici le document de l'élève :
"""

# ======================
# UTILISATEURS
# ======================
with open("users.json") as f:
    USERS = json.load(f)

if "connected" not in st.session_state:
    st.session_state.connected = False

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    if st.button("Connexion"):
        if username in USERS and USERS[username] == password:
            st.session_state.connected = True
            st.success("Connexion réussie")
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect")

    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique IA")

col1, col2 = st.columns(2)

document_content = ""

# ======================
# DOCUMENT
# ======================
with col1:
    st.subheader("📄 Document de travail")
    uploaded_file = st.file_uploader("Dépose ton document", type=["txt", "docx", "pdf"])

    if uploaded_file:
        if uploaded_file.name.endswith(".txt"):
            document_content = uploaded_file.read().decode("utf-8")
            st.text_area("Contenu", document_content, height=400)

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            document_content = "\n".join([p.text for p in doc.paragraphs])
            st.text_area("Contenu", document_content, height=400)

        elif uploaded_file.name.endswith(".pdf"):
            pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            for page in pdf:
                document_content += page.get_text()
            st.info("PDF chargé (texte extrait pour l’IA, non visible par l’élève)")

# ======================
# CHAT
# ======================
with col2:
    st.subheader("📝 Rappel de cours")
    mots_cles = st.text_input("Mots-clés")

    if st.button("Obtenir le rappel"):
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
        prompt = PROMPT_PEDAGOGIQUE + "\n\nDOCUMENT:\n" + document_content + "\n\nQUESTION:\n" + question

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        st.markdown("**🤖 Assistant :**")
        st.write(response.choices[0].message.content)

