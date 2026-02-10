
import streamlit as st
import json
import os
@@ -57,78 +56,42 @@
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ======================
# PROMPT PEDAGOGIQUE CORRIGE
# PROMPT PEDAGOGIQUE
# ======================
PROMPT_PEDAGOGIQUE = """
Tu es un assistant pedagogique bienveillant et patient.

REGLES ABSOLUES :
- Tu ne donnes JAMAIS la reponse finale.
- Tu aides uniquement avec des indices progressifs.
- Tu ne depasses JAMAIS 60 mots même dans les rappels et au pire tu ne donnes qu'une partie de l'information.
- Tu ne depasses JAMAIS 60 mots.
- Tu restes poli et encourageant.
- Tu refuses toute question sur la religion, la pornographie ou les sujets sensibles.
- Tu n'affiches JAMAIS de code informatique.

FORMAT OBLIGATOIRE :
1) Reformule la question de l'exercice.
2) Donne UN indice.
3) Continue à donner des indices de plus enplus proche de la réponse.
3) Continue à donner des indices de plus en plus proche de la réponse.

PARTIE RAPPEL :
- Rappel tres court pas plus de 60 mots.
- Jamais de methode complete.
- Jamais de solution.

FORMULES MATHEMATIQUES (OBLIGATOIRE) :
FORMULES MATHEMATIQUES :
- Toute expression mathematique DOIT etre entre \( ... \) ou \[ ... \]
- Exemple correct : \( ax^2 + bx + c = 0 \)
- Exemple correct : \( \Delta = b^2 - 4ac \)
- Exemple interdit : ax^2 + bx + c = 0
- Exemple interdit : Δ = b^2 - 4ac

Si tu ecris une formule sans delimiteur, tu dois la reformuler.

INTERDICTIONS :
- jamais de solution
- jamais de code
- jamais plus de 60 mots

Voici le document de l'eleve :
"""

# ======================
# FIX LATEX STRICT POUR STREAMLIT
# ======================
def fix_latex_for_streamlit(text: str) -> str:
    # Encadre probabilités
    text = re.sub(r"(P\([^\)]*\))", r"\\(\1\\)", text)
    
    # Encadre les equations classiques
    text = re.sub(r"(ax\^2 \+ bx \+ c = 0)", r"\\( \1 \\)", text)
    text = re.sub(r"(b\^2 - 4ac)", r"\\( \1 \\)", text)
    text = re.sub(r"(\\Delta\s*=\s*b\^2\s*-\s*4ac)", r"\\( \1 \\)", text)

    # Remplace Delta unicode par LaTeX
    text = text.replace("Δ", "\\Delta")

    # Formule quadratique
    text = re.sub(r"x\s*=\s*\\frac\{-b\s*\\pm\s*\\sqrt\{D\}\}\{2a\}",
                  r"\\( x = \\frac{-b \\pm \\sqrt{D}}{2a} \\)", text)

    # Corrige les anciens formats
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.S)

    return text


USERS_FILE = "users.json"
ACTIVE_USERS_FILE = "active_users.json"
TOKENS_DIR = "tokens"
SESSION_TIMEOUT = 60
ADMIN_USER = "ahautecoeur2"

TOKEN_COST_PER_1K = 0.0015

os.makedirs(TOKENS_DIR, exist_ok=True)
@@ -207,7 +170,20 @@ def text_to_image(text, width=600):
        y += 20
    return img

# ======================
# FIX LATEX STRICT
# ======================
def fix_latex_for_streamlit(text: str) -> str:
    # Remplace caractères Unicode
    text = text.replace("Δ", "\\Delta")
    text = text.replace("∩", "\\cap")
    text = text.replace("̅", "\\overline")  # barre de complément
    # Encadre toutes les expressions mathématiques en $...$
    text = re.sub(r"(?<!\$)(P\([^\)]*\))", r"$\1$", text)
    text = re.sub(r"(?<!\$)(ax\^2 \+ bx \+ c = 0)", r"$\1$", text)
    text = re.sub(r"(?<!\$)(b\^2 - 4ac)", r"$\1$", text)
    text = re.sub(r"(?<!\$)(x\s*=\s*\\frac\{-b\s*\\pm\s*\\sqrt\{D\}\}\{2a\})", r"$\1$", text)
    # Convertit tout \( ... \) ou \[ ... \] en $ ... $ ou $$ ... $$ pour Streamlit
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.S)
    return text
@@ -350,6 +326,3 @@ def submit_question():
        data = load_tokens(folder)
        st.write(f"🏫 {folder} → Prompt: {data['prompt']} | Completion: {data['completion']} | Total: {data['total']} | €: {data['cost']:.4f}")





