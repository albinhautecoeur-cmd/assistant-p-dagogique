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

# ======================
# Le reste de ton code reste inchangé
# ======================

# Ajoute ici tout ton code pour documents, chat, rappel, latex, etc.
