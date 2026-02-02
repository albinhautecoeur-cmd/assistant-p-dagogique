import streamlit as st
import json
import time
import os
from openai import OpenAI

# =========================
# CONFIG
# =========================
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

USERS_FILE = "users.json"
ACTIVE_USERS_FILE = "active_users.json"

PROMPT_PEDAGOGIQUE = """
Tu es un assistant pédagogique bienveillant.
Explique clairement et simplement.
Ne donne jamais directement la réponse.
Guide l'élève avec des indices.
"""

# =========================
# SESSION STATE
# =========================
if "connected" not in st.session_state:
    st.session_state.connected = False
if "username" not in st.session_state:
    st.session_state.username = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# =========================
# FICHIERS UTILISATEURS
# =========================
def load_users():
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_active_users():
    if not os.path.exists(ACTIVE_USERS_FILE):
        return {}
    with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_active_users(data):
    with open(ACTIVE_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

USERS = load_users()

# =========================
# PAGE LOGIN
# =========================
def afficher_page_login():
    st.title("🔐 Connexion élève")

    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")

    active_users = load_active_users()

    if st.button("Connexion"):
        if username in USERS and USERS[username] == password:
            if username in active_users:
                st.error("❌ Ce compte est déjà connecté ailleurs.")
            else:
                active_users[username] = time.time()
                save_active_users(active_users)

                st.session_state.connected = True
                st.session_state.username = username
                st.success("✅ Connexion réussie")
                st.rerun()
        else:
            st.error("❌ Identifiant ou mot de passe incorrect")

# =========================
# DECONNEXION
# =========================
def deconnexion():
    active_users = load_active_users()
    username = st.session_state.username

    if username in active_users:
        del active_users[username]
        save_active_users(active_users)

    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.messages = []
    st.rerun()

# =========================
# APPLICATION PRINCIPALE
# =========================
def afficher_application():
    st.title("🧠 Assistant pédagogique IA")

    st.write(f"👤 Connecté en tant que : **{st.session_state.username}**")

    if st.button("🚪 Déconnexion"):
        deconnexion()

    st.divider()

    # Affichage du chat
    for role, msg in st.session_state.messages:
        if role == "user":
            st.markdown(f"**👤 Toi :** {msg}")
        else:
            st.markdown(f"**🤖 Assistant :** {msg}")

    question = st.text_input("Pose ta question")

    if st.button("Envoyer"):
        if question:
            prompt = PROMPT_PEDAGOGIQUE + "\nQUESTION : " + question

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )

            answer = response.choices[0].message.content

            st.session_state.messages.append(("user", question))
            st.session_state.messages.append(("assistant", answer))
            st.rerun()

# =========================
# ROUTEUR PRINCIPAL
# =========================
if not st.session_state.connected:
    afficher_page_login()
else:
    afficher_application()
