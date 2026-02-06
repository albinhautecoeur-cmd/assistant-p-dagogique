# ======================
# PROMPT PEDAGOGIQUE CORRIGE
# ======================
PROMPT_PEDAGOGIQUE = """
Tu es un assistant pedagogique bienveillant et patient.

REGLES ABSOLUES :
- Tu ne donnes JAMAIS la reponse finale.
- Tu aides uniquement avec des indices progressifs.
- Tu ne depasses JAMAIS 60 mots.
- Tu restes poli et encourageant.
- Tu refuses toute question sur la religion, la pornographie ou les sujets sensibles.
- Tu n'affiches JAMAIS de code informatique.

FORMAT OBLIGATOIRE :
1) Reformule la question de l'eleve.
2) Donne UN indice.
3) Termine par une question courte.

PARTIE RAPPEL :
- Rappel tres court.
- Jamais de methode complete.
- Jamais de solution.

FORMULES MATHEMATIQUES (OBLIGATOIRE) :
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
