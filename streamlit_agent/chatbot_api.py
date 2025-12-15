# ============================================================
# chatbot_api.py
# Bietet eine Funktion run_chatbot(), die direkt den Chatbot
# aus Python aufruft – ohne Streamlit UI.
# ============================================================

from streamlit_agent.marine_snow_chatbot_v1 import generate_raw_answer, apply_anthro_style

# ⬆️ WICHTIG:
# Ersetze "streamlit_chatbot" durch den tatsächlichen Dateinamen
# deines Chatbot-Scripts, falls er anders heißt.


def run_chatbot(question: str, level: int):
    """
    Führt den Chatbot aus, aber ohne Streamlit.
    Gibt den finalen Text zurück.
    """

    # Schritt 1: Rohinhalt erzeugen (Intent, IEs, RAG…)
    raw = generate_raw_answer(question)

    # Schritt 2: Stil anwenden (Anthropomorphiestufe)
    styled = apply_anthro_style(raw, level)

    return styled
