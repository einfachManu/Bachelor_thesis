

import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
import pdfplumber
import uuid

# ============================================================
# ENV + OPENAI CLIENT
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_MAIN = "gpt-4.1"         # Hauptmodell für Antworten
MODEL_SPELL = "gpt-4o-mini"    # Rechtschreibung / Cleanup

# ============================================================
# STREAMLIT PAGE SETUP
# ============================================================

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("🌊 Marine Snow Learning Assistant – RAG + IE + Anthropomorphie Chatbot")

# ============================================================
# ANTHRO LEVELS (aus Chatbot 1)
# ============================================================

ANTHRO = {
     0: """
Anthropomorphism Level 0:
- No personal pronouns
- No emotions
- No empathy
- No emojis
- Very mechanical, formal tone
""",

    1: """
Anthropomorphism Level 1:
- Light warmth allowed
- Personal pronouns allowed
- occasional emotional expressions
- light emoji usage
- friendly, semi friendly tone
""",

    2: """
Anthropomorphism Level 2:
- Warm, supportive tone
- strong use of Personal pronouns 
- strong Emotional expressions
- strong emojis usage 
- converstional, engaging tone
"""
}

AVATARS = {
    0: "🟧",
    1: "🧑🏻",
    2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
}

GREETINGS = {
    0: "Hallo. Ich beantworte deine Fragen sachlich und präzise.",
    1: "Hallo! Ich helfe dir gern bei deinen Fragen zu Meeresschnee 🙂",
    2: "Hi! Ich bin Milly 😊🌊 Frag mich alles, was du wissen möchtest!"
}

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)
assistant_avatar = AVATARS[level]

if "greeted" not in st.session_state:
    st.chat_message("assistant", avatar=assistant_avatar).write(GREETINGS[level])
    st.session_state["greeted"] = True

# ============================================================
# MEMORY
# ============================================================

if "memory" not in st.session_state:
    st.session_state.memory = {
        "last_topic": "",
        "last_term": "",
        "last_bot_answer": "",
        "recent_msgs": []
    }

# ============================================================
# INFORMATION UNITS (SET B)
# ============================================================

IEs = {
    "definition": [
        "-kleine Aggregate, welcher größer als 500 Mikrometer sind",
        "-bestehen unter anderem aus Mikroorganismen und Tonmineralien",
        "-umfasst eine allgemeine Kategorie verschiedenster Aggregate",
        "-Strukturen variieren von zerbrechlich bis robust",
        "-Form reicht von Kugeln über Stränge bis zu Platten"
    ],

    "importance": [
        "-Transportmittel für große Mengen organischen Materials in tiefere Schichten",
        "-wichtige Nahrungsquelle für zahlreiche Tiere",
        "-Lebensraum und Struktur für Kleinstlebewesen"
    ],

    "sampling": [
        "-Wasserproben durch Taucher oder Tauchboote",
        "-Aufbewahrung in Flaschen oder Behältern",
        "-Auswertung mit hochauflösenden Kameras oder holografischen Geräten (Größe, Form, Sinkgeschwindigkeit)"
    ],

    "sampling_problems": [
        "1) Zerbrechlichkeit: Aggregate zerfallen leicht",
        "2) Wasserflaschen: große Partikel setzen sich ab und werden übersehen",
        "3) Transportprobleme: Aggregate zerfallen oder verklumpen",
        "4) Verzerrte Messungen: Laborproben zeigen weniger große Partikel",
        "5) Hohe natürliche Variabilität: starke Schwankungen nach Ort/Zeit"
    ],

    "formation": [
        "Zwei grundlegende Entstehungswege:",
        "(A) Biologisch produzierte Aggregate aus Schleim/Hüllen/Kotmaterial",
        "(B) Aggregation kleiner Partikel über Kollisionen",
        "Strömungen bringen Partikel zusammen",
        "Biologische Klebstoffe wie Schleim verbinden Partikel"
    ],

    "degradation": [
        "Fraß durch Tiere → Zerkleinerung und Verlust organischen Materials",
        "Mikrobielle Zersetzung → chemischer Abbau",
        "Sinking: schnelle Absinkprozesse entfernen Aggregate aus Oberfläche",
        "Seitliche Verdriftung: Strömungen transportieren Material seitwärts"
    ]
}

# ============================================================
# LOAD CHROMA RAG DATABASE
# ============================================================

PDF_PATH = "streamlit_agent/relevante_Informationen_Paper.pdf"

def load_chroma():
    chroma_client = chromadb.PersistentClient(path="./chroma_marine_snow")
    if "marine_snow" in [c.name for c in chroma_client.list_collections()]:
        return chroma_client.get_collection("marine_snow")

    col = chroma_client.create_collection("marine_snow")

    with pdfplumber.open(PDF_PATH) as pdf:
        docs, ids, meta = [], [], []
        for p, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            for para in text.split("\n"):
                if len(para.strip()) < 50:
                    continue
                docs.append(para.strip())
                ids.append(str(uuid.uuid4()))
                meta.append({"page": p + 1})
        col.add(documents=docs, ids=ids, metadatas=meta)

    return col

collection = load_chroma()

def rag_section(query):
    result = collection.query(query_texts=[query], n_results=1)
    return result["documents"][0][0]

# ============================================================
# SPELLCHECKER
# ============================================================

def autocorrect(text):
    response = client.chat.completions.create(
        model=MODEL_SPELL,
        temperature=0,
        messages=[{"role": "user", "content": f"Korrigiere Text ohne Erklärungen:\n{text}"}]
    )
    cleaned = response.choices[0].message.content.strip()
    return cleaned

# ============================================================
# SYSTEM PROMPT AUS CHATBOT 2 — OHNE ANTHROPOMORPHIE
# ============================================================

SYSTEM_PROMPT = """
Du bist ein wissenschaftlich kontrollierter Tutor für das Thema „Meeresschnee“.
Du befolgst strikt die unten definierten Regeln für Inhalt, Struktur und Stil.

============================================================
[1] HAUPTFUNKTION
============================================================
Du beantwortest Nutzerfragen zu Meeresschnee ausschließlich mit:
- den Information Units (für Hauptfragen)
- dem RAG-Abschnitt (für spezifische Fragen)
- oder kurzen Begriffserklärungen (für TERM-Fragen)

Keine Halluzinationen. Keine zusätzlichen Fakten. Kein Erwähnen in welcher ANthropomorphiestufe du antwortest.
WICHTIG: Wenn sich die Frage nicht auf Meeresschnee bezieht, antworte:
"Tut mir leid, aber ich kann nur Fragen zu Meeresschnee beantworten."
============================================================
[2] INTENT-KLASSIFIKATION
============================================================

Du wählst genau einen Intent:

INTENT = HAUPTFRAGE
Wenn die Frage inhaltlich einer der fünf folgenden entspricht:

1. Definition + Bedeutung von Meeresschnee  
2. Sammlung & Untersuchung von Meeresschnee  
3. Probleme bei der Probenahme  
4. Entstehung von Meeresschnee  
5. Gründe für eine Abnahme der Menge

INTENT = SPECIFIC  
→ Detailfragen, die NICHT exakt diese Hauptthemen sind  
→ Antwort NUR basierend auf RAG

INTENT = TERM  
→ Nachfrage nach der Bedeutung eines einzelnen Wortes
→ 1–3 Sätze, kein RAG, keine IUs

INTENT = FOLLOW-UP  
→ „Wiederhole“, „in anderen Worten“, „erkläre genauer“  
→ oder Pronomenbezüge

Follow-up Regeln:
- Wiederhole = exakt gleiche letzte Antwort
- In anderen Worten = paraphrasieren
- Erkläre genauer = nur RAG-Details hinzufügen
- Pronomen beziehen sich auf letzte Hauptthema-Antwort

============================================================
[3] REGELN FÜR HAUPTFRAGEN
============================================================

Wenn HAUPTFRAGE:
- alle zugehörigen IUs verwenden (paraphrasiert, nie wörtlich)
- IUs dürfen mit RAG kombiniert werden, aber keine Fakten hinzufügen

WICHTIG:
Gib ausschließlich den fertigen Fließtext zurück.
Gib keine Erklärungen, keine Gedanken und keine Begründungen zurück.
Gib keine Metakommentare zurück.
KEINE Erwähnung der Zeichenlänge, keine Hinweise auf Regeln.
============================================================
[4] REGELN FÜR SPECIFIC-FRAGEN
============================================================
- Keine IUs verwenden
- Antwort basiert ausschließlich auf RAG-Abschnitt
- wissenschaftlich korrekt
- Stil gemäß Modus

============================================================
[5] STILVALIDIERUNG
============================================================
Bevor du die Antwort abschickst, überprüfst du:

- Stimmen Intent & Regeln überein?
- Ist der Stil exakt der des aktiven Modus?
- Bei Hauptfragen: Länge 550–700 Zeichen?
- Enthält die Antwort KEINE erfundenen Fakten?

Wenn etwas nicht stimmt → automatisch umschreiben.

============================================================
ENDE DES SYSTEMPROMPTS
============================================================
"""

# ============================================================
# CHAT LOOP
# ============================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

for msg in st.session_state.chat:
    st.chat_message(msg["role"], avatar=msg["avatar"]).write(msg["content"])

user_text = st.chat_input("Frag mich etwas über Meeresschnee")

if user_text:

    corrected = autocorrect(user_text)
    mem = st.session_state.memory

    st.chat_message("user").write(user_text)
    st.session_state.chat.append({"role": "user", "content": user_text, "avatar": None})

    RAG = rag_section(corrected)

    user_prompt = f"""
NUTZEREINGABE:
"{corrected}"

ANTHRO_LEVEL (wird erst NACH deiner Antwort angewendet):
{level}

LETZTE_ANTWORT:
"{mem['last_bot_answer']}"

IEs:
{IEs}

RAG:
"{RAG}"

AUFGABE:
Erzeuge eine Antwort, basierend ausschließlich auf:
- Intent-Logik aus Systemprompt
- IEs (für Hauptfragen)
- RAG (für Specific-Fragen)
- 1–3 Sätze für TERM-Fragen
- Follow-Up-Regeln

KEINE Stilmerkmale anwenden.
Nur inhaltlicher Rohtext.
"""

    response = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )

    raw_answer = response.choices[0].message.content.strip()

    # ========================================================
    # APPLY ANTHROPOMORPHIE LEVEL (Chatbot 1 Logik)
    # ========================================================

    style_prompt = f"""
Formatiere den folgenden Text in Anthropomorphiestufe {level}:
{ANTHRO[level]}

Text:
{raw_answer}

WICHTIG:
- Inhalt unverändert lassen
- Nur Stil anpassen
"""

    style_response = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.2,
        messages=[{"role": "user", "content": style_prompt}]
    )

    final_answer = style_response.choices[0].message.content.strip()

    mem["last_bot_answer"] = final_answer

    st.chat_message("assistant", avatar=assistant_avatar).write(final_answer)
    st.session_state.chat.append({"role": "assistant", "content": final_answer, "avatar": assistant_avatar})
