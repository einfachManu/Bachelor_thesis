import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
import pdfplumber
import uuid

# ============================================================
# ENV
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_MAIN = "gpt-4.1"
MODEL_SPELL = "gpt-4o-mini"

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("🌊 Marine Snow Learning Assistant – RAG + IE + Anthropomorphismus")

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

# ============================================================
# ANTHROPOMORPHIE RULES
# ============================================================

ANTHRO = {
    0: """
- keine Emojis
- keine persönlichen Pronomen
- rein sachlicher, formeller Stil
""",
    1: """
- leichte Wärme
- persönliche Pronomen erlaubt
- 1 Emoji erlaubt
- freundlicher, sachlicher Ton
""",
    2: """
- warm, persönlich, motivierend
- bis zu 5 Emojis erlaubt
- dialogischer, emotionaler Ton
"""
}

AVATARS = {
    0: "🟧",
    1: "🧑🏻",
    2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
}

GREETINGS = {
    0: "Hallo. Ich beantworte deine Fragen präzise und sachlich.",
    1: "Hallo! Ich unterstütze dich gern bei deinen Fragen 🙂",
    2: "Hey! Ich bin Milly 😊🌊 Frag mich alles, was du wissen möchtest!"
}

assistant_avatar = AVATARS[level]

if "greeted" not in st.session_state:
    st.chat_message("assistant", avatar=assistant_avatar).write(GREETINGS[level])
    st.session_state["greeted"] = True

# ============================================================
# MEMORY
# ============================================================

if "memory" not in st.session_state:
    st.session_state.memory = {
        "last_bot_answer": "",
        "last_topic": "",
        "last_term": "",
        "recent_msgs": []
    }

# ============================================================
# INFORMATION UNITS — SET B
# ============================================================

IEs = {
    "definition": [
        "-kleine Aggregate >500 μm",
        "-bestehen aus Mikroorganismen und Tonmineralien",
        "-umfasst viele Aggregatearten",
        "-Strukturen variieren von zerbrechlich bis robust",
        "-Formen reichen von Kugeln bis Strängen"
    ],
    "importance": [
        "-Transport organischen Materials in tiefere Zonen",
        "-wichtige Nahrungsquelle",
        "-Lebensraum für Kleinstlebewesen"
    ],
    "sampling": [
        "-Proben durch Taucher/Tauchboote",
        "-Aufbewahrung in Flaschen",
        "-Analyse per Kamera oder Holografie"
    ],
    "sampling_problems": [
        "Zerbrechlichkeit",
        "Absetzen großer Partikel in Flaschen",
        "Zerfall beim Transport",
        "Messverzerrungen",
        "Hohe natürliche Variabilität"
    ],
    "formation": [
        "Biologisch produzierte Aggregate",
        "Aggregation kleiner Partikel",
        "Strömungsbedingte Kollisionen",
        "Biologische Klebstoffe verbinden Partikel"
    ],
    "degradation": [
        "Fraß durch Tiere",
        "Mikrobielle Zersetzung",
        "Absinken aus Oberflächenwasser",
        "Seitliche Verdriftung durch Strömungen"
    ]
}

# ============================================================
# RAG SETUP
# ============================================================

PDF_PATH = "streamlit_agent/relevante_Informationen_Paper.pdf"

def load_chroma():
    chroma_client = chromadb.PersistentClient(path="./chroma_marine_snow")
    if "marine_snow" in [c.name for c in chroma_client.list_collections()]:
        return chroma_client.get_collection("marine_snow")

    col = chroma_client.create_collection("marine_snow")

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            for para in text.split("\n"):
                if len(para.strip()) < 50:
                    continue
                col.add(
                    documents=[para.strip()],
                    ids=[str(uuid.uuid4())],
                    metadatas=[{"page": page_num + 1}]
                )
    return col

collection = load_chroma()

def rag_section(query):
    result = collection.query(query_texts=[query], n_results=1)
    return result["documents"][0][0]

# ============================================================
# SPELLCHECK
# ============================================================

def autocorrect(text):
    r = client.chat.completions.create(
        model=MODEL_SPELL,
        temperature=0,
        messages=[{"role": "user", "content": f"Korrigiere ohne Kommentar:\n{text}"}]
    )
    return r.choices[0].message.content.strip()

# ============================================================
# SYSTEMPROMPT (Wissenschaftlich, kein Stil)
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
WICHTIG: Wenn sich die Frage nicht auf Meeresschnee bezieht, antworte klar und in JEDER Anthropomorphiestufe:
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
- Enthält die Antwort KEINE erfundenen Fakten?

Wenn etwas nicht stimmt → automatisch umschreiben.

============================================================
ENDE DES SYSTEMPROMPTS
============================================================
"""

# ============================================================
# ZEICHENLIMIT VALIDIERUNG
# ============================================================

TARGET_MIN = 900
TARGET_MAX = 1100

def enforce_length(text):
    attempt = text

    for _ in range(5):
        length = len(attempt)

        if TARGET_MIN <= length <= TARGET_MAX:
            return attempt

        fix_prompt = f"""
Korrigiere folgenden Text so, dass er zwingend zwischen {TARGET_MIN} und {TARGET_MAX} Zeichen lang ist.
WICHTIG: LEERZEICHEN werden MITGEZÄHLT.
Inhalt NICHT verändern.
Keine Metakommentare, keine Hinweise auf Regeln.

Text:
{attempt}
"""

        attempt = client.chat.completions.create(
            model=MODEL_MAIN,
            messages=[{"role": "user", "content": fix_prompt}],
            temperature=0
        ).choices[0].message.content.strip()

    return attempt[:TARGET_MAX]

# ============================================================
# CHAT LOOP
# ============================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

for m in st.session_state.chat:
    st.chat_message(m["role"], avatar=m["avatar"]).write(m["content"])

user_text = st.chat_input("Frag mich etwas über Meeresschnee")

if user_text:

    corrected = autocorrect(user_text)
    mem = st.session_state.memory

    st.chat_message("user").write(user_text)
    st.session_state.chat.append({"role": "user", "content": user_text, "avatar": None})

    RAG = rag_section(corrected)

    # ========================================================
    # MODELLAUFRUF – Rohinhalt
    # ========================================================

    user_prompt = f"""
NUTZEREINGABE:
"{corrected}"

LETZTE ANTWORT:
"{mem['last_bot_answer']}"

IEs:
{IEs}

RAG:
"{RAG}"

WICHTIG:
Gib NUR Rohinhalt zurück.
Zwischen {TARGET_MIN} und {TARGET_MAX} Zeichen (Leerzeichen INKLUDIERT).
Keine Erklärungen, keine Regeln, keine Metakommentare.
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
    raw_answer = enforce_length(raw_answer)

    # ========================================================
    # ANTHROPOMORPHIE REWRITE
    # ========================================================

    style_prompt = f"""
Formuliere den folgenden Text stilistisch um mit diesen Regeln:
{ANTHRO[level]}

SEHR WICHTIG:
- Erwähne NIEMALS die Anthropomorphiestufe.
- Keine Hinweise auf Regeln.
- Keine Metakommentare.
- Gib nur den Text zurück.
Text:
{raw_answer}
"""

    styled = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.25,
        messages=[{"role": "user", "content": style_prompt}]
    ).choices[0].message.content.strip()

    mem["last_bot_answer"] = styled

    st.chat_message("assistant", avatar=assistant_avatar).write(styled)
    st.session_state.chat.append({"role": "assistant", "content": styled, "avatar": assistant_avatar})


# ============================================================
# TESTING FRAMEWORK – Anthropomorphismus + Inhaltsvalidierung
# ============================================================
import re
import random

TEST_QUERIES = {
    "definition": [
        "Was ist Meeresschnee?",
        "Erkläre Meeresschnee.",
        "Definiere Meeresschnee."
    ],
    "sampling": [
        "Wie wird Meeresschnee gesammelt?",
        "Wie sampelt man Meeresschnee?",
        "Wie gewinnt man Proben von Meeresschnee?"
    ],
    "formation": [
        "Wie entsteht Meeresschnee?",
        "Wodurch bildet sich Meeresschnee?",
        "Welche Prozesse führen zu Meeresschnee?"
    ]
}

# Regeln für Tests
ANTHRO_RULES_TEST = {
    0: {
        "max_emojis": 0,
        "forbidden_pronouns": ["ich", "wir", "du", "mich", "mir", "uns", "dich", "euch", "ihr", "ihrer" , "dein", "deine", "mein", "meine", "unser", "unsere", "euer", "eure", "ihre", "seine", "sein"],
    },
    1: {
        "max_emojis": 5,
        "forbidden_pronouns": [],
    },
    2: {
        "max_emojis": 20,
        "forbidden_pronouns": [],
    }
}

def count_emojis(text):
    return sum(bool(re.match(r'[\U0001F300-\U0001FAFF]', c)) for c in text)

def contains_forbidden_pronouns(text, pronouns):
    return any(p in text.lower() for p in pronouns)

def run_single_test():
    topic = random.choice(list(TEST_QUERIES.keys()))
    question = random.choice(TEST_QUERIES[topic])
    level = random.choice([0, 1, 2])

    # Simuliere Anfrage an Chatbot
    test_user_prompt = question
    user_prompt_corrected = autocorrect(test_user_prompt)
    RAG = rag_section(user_prompt_corrected)

    # Modellantwort
    response = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"NUTZEREINGABE: '{user_prompt_corrected}' IEs: {IEs} RAG: '{RAG}'"}
        ]
    ).choices[0].message.content.strip()

    # Stil rewrite
    styled = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.25,
        messages=[{
            "role": "user",
            "content": f"Formuliere mit diesen Regeln: {style_prompt} Text: {response}"
        }]
    ).choices[0].message.content.strip()

    # =====================================
    # Validierung
    # =====================================
    emoji_count = count_emojis(styled)
    pronoun_violation = contains_forbidden_pronouns(
        styled,
        ANTHRO_RULES_TEST[level]["forbidden_pronouns"]
    )

    length_ok = TARGET_MIN <= len(styled) <= TARGET_MAX
    emoji_ok = emoji_count <= ANTHRO_RULES_TEST[level]["max_emojis"]
    pronoun_ok = not pronoun_violation
    print("Länge:", len(styled), "Emojis:", emoji_count, "Pronomen-Verstoß:", pronoun_violation)
    return {
        "topic": topic,
        "question": question,
        "level": level,
        "length_ok": length_ok,
        "emoji_ok": emoji_ok,
        "pronoun_ok": pronoun_ok,
        "final_answer": styled
    }

# Optional: Streamlit Testbutton
if st.button("Automatischen Test ausführen"):
    result = run_single_test()
    st.write(result)
