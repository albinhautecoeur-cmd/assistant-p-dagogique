import streamlit as st
import json
import os
import time
import re
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import io
import docx
import fitz
import tiktoken

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Assistant pédagogique", layout="wide")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

ADMIN_ID = "ahautecoeur2"
TOKENS_DIR = "tokens"
PRICE_PER_1K_INPUT = 0.00015
PRICE_PER_1K_OUTPUT = 0.0006

os.makedirs(TOKENS_DIR, exist_ok=True)

# ======================
# SESSION STATE
# ======================
for k, v in {
    "connected": False,
    "username": None,
    "document_content": "",
    "document_images": [],
    "question_input": "",
    "chat_history": []
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ======================
# STYLE
# ======================
st.markdown("""
<style>
.stApp { background-color: #eaf3ff; }
h1, h2, h3 { color: #1f3c88; }
.stButton>button {
    background: linear-gradient(135deg, #7aa2ff, #a5c9ff);
    color: white;
    border-radius: 20px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# UTILS
# ======================
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    return len(enc.encode(text))

def get_etablissement(username):
    return USERS[username]["etablissement"]

def get_token_file(etab):
    path = os.path.join(TOKENS_DIR, etab)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "tokens.json")

def load_tokens(etab):
    file = get_token_file(etab)
    if not os.path.exists(file):
        return {"input": 0, "output": 0}
    with open(file, "r") as f:
        return json.load(f)

def save_tokens(etab, data):
    file = get_token_file(etab)
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def fix_latex_for_streamlit(text):
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.S)
    return text

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

# ======================
# LOAD USERS
# ======================
USERS = load_users()

# ======================
# LOGIN
# ======================
if not st.session_state.connected:
    st.title("Connexion")

    with st.form("login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Connexion")

        if ok:
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.connected = True
                st.session_state.username = u
                st.success("Connecté")
            else:
                st.error("Erreur identifiant ou mot de passe")

    st.stop()

username = st.session_state.username
etab = get_etablissement(username)

# ======================
# ADMIN VIEW
# ======================
if username == ADMIN_ID:
    st.title("📊 Consommation par établissement")

    for folder in os.listdir(TOKENS_DIR):
        data = load_tokens(folder)
        total_in = data["input"]
        total_out = data["output"]

        price = (total_in/1000)*PRICE_PER_1K_INPUT + (total_out/1000)*PRICE_PER_1K_OUTPUT

        st.markdown(f"""
### 🏫 {folder}
- Tokens entrants : {total_in}
- Tokens sortants : {total_out}
- 💰 Coût estimé : **{price:.4f} €**
""")

    st.stop()

# ======================
# INTERFACE
# ======================
st.title("🧠 Assistant pédagogique")

col_doc, col_chat = st.columns([1,1])

# ======================
# DOCUMENT
# ======================
with col_doc:
    uploaded_file = st.file_uploader("Document", type=["txt","docx","pdf"])

    if uploaded_file:
        content = ""
        images = []

        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.read().decode()
            images = [text_to_image(content)]

        elif uploaded_file.name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join(p.text for p in doc.paragraphs)
            images = [text_to_image(content)]

        elif uploaded_file.name.endswith(".pdf"):
            pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            for page in pdf:
                content += page.get_text()
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

        st.session_state.document_content = content
        st.session_state.document_images = images
        st.image(images)

# ======================
# CHAT
# ======================
with col_chat:
    def submit():
        q = st.session_state.question_input
        if not q:
            return

        prompt = "DOCUMENT:\n"+st.session_state.document_content+"\nQUESTION:\n"+q

        in_tokens = count_tokens(prompt)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )

        answer = response.choices[0].message.content
        out_tokens = count_tokens(answer)

        data = load_tokens(etab)
        data["input"] += in_tokens
        data["output"] += out_tokens
        save_tokens(etab, data)

        st.session_state.chat_history.append({"q":q,"a":answer})
        st.session_state.question_input = ""

    st.text_input("Question", key="question_input", on_change=submit)

    for msg in reversed(st.session_state.chat_history):
        st.markdown("**Question :** "+msg["q"])
        st.markdown("**Réponse :** "+fix_latex_for_streamlit(msg["a"]))
        st.markdown("---")
