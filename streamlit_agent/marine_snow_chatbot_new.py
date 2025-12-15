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

MODEL = "gpt-4.1"       # Hauptmodell für Antworten
MODEL_SPELL = "gpt-4o-mini"  # Rechtschreibkorrektur

# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("🌊 Marine Snow Learning Assistant – RAG + IE + Anthropomorphism Chatbot")
level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

# ============================================================
# IEs
# ============================================================
IEs = {
    "definition": [
        "-kleine Aggregate, welcher gößer als 500 mikrometer sind",
        "-bestehen unter anderem aus Mikroorganismen und Tonmineralien",
        "-ist eine allgemeine Kategorie, welche verschiedenste Aggregate umfasst",
        "-struktur der Aggregate variiert ebenfalls von zerbrechlichen Partikeln bis zu robusten Strukturen",
        "-Form ist dabei auch unterschiedlich und kann von kugeln bis zu Strängen oder Platten reichen"
    ],

    "importance": [
        "-Wichtiges Transportmittel, da es eine große Menge an Material von der Meeresoberfläche in tiefere schichten bis hin zum Meeresboden befördert",
        "-Nahrung für Tiere und und Wohnraum für kleinstlebewesen"
    ],

    "sampling": [
        "-Sammlung von Wasserproben durch Taucher oder Tauchbote",
        "-Aufbewahrung der Wasserproben in Behältnissen (bsp. Flaschen)", 
        "-Auswertung durch hochauflösende Kameras, welche den Zustand des Materials und die Anzahl der Vorkommen dokumentieren oder holographische Geräte, welche größe, Form und Sinkgeschwindigkeit erfassen"
    ],

    "sampling_problems": [
        "1) Zerbrechlichkeit der Aggregate: Meeresschnee bricht leicht bei jeder Form von Handhabung.",
        "2) Probleme bei Wasserflaschen-Proben: Große Partikel setzen sich im ruhigen Innenraum der Flasche ab → werden beim Auswerten übersehen.",
        "3) Probleme während Transport & Lagerung: Aggregate zerfallen oder verklumpen während Transport oder Stehenlassen; Proben verändern sich, bevor sie analysiert werden können.",
        "4) Verzerrte Messungen der Partikelgrößen: Vor-Ort-Messungen enthalten mehr große Partikel; Laborproben zeigen weniger große, dafür mehr kleine Partikel → Ursache: Bruch durch Probenahme.",
        "5) Hohe natürliche Variabilität: Häufigkeit von Meeresschnee schwankt stark über Zeit und Ort (auch über Gezeitenzyklen), was Vergleichbarkeit und zuverlässige Stichproben erschwert."
    ],

    "formation": [
        "Zwei grundlegende Entstehungswege:",
        "(A) Neu gebildete Aggregate (biologisch produziert): Entstehen direkt durch Schleim, Hüllen oder Kotmaterial von Meeresorganismen.",
        "(B) Aggregation kleiner Partikel: Kleine Partikel (z. B. Mikroalgen, Tonminerale, Mikroaggregate, Kotpellets) stoßen zusammen und verkleben, wodurch größere Flocken entstehen.",
        "Partikel werden zusammengebracht durch Strömungen: Strömungen führen dazu, dass Partikel miteinander kollidieren und daraufhin zu größeren Partikeln werden.",
        "Differenziertes Absinken: Unterschiedliche Absinkgeschwindigkeiten führen dazu, dass Partikel kollidieren.",
        "Nach dem Zusammenstoßen werden die Partikel verklebt durch biologische Klebstoffe (Bsp. Schleim)."
    ],

    "degradation": [
        "Fraß durch Tiere: manche Fische fressen Meeresschnee oder knabbern Teile davon ab.",
        "Mikrobielle Zersetzung: Bakterien bauen organisches Material ab → Aggregate werden chemisch ärmer und können teilweise zerfallen.",
        "Absinken aus der Wassersäule (Sinking): Schnell sinkende Aggregate verschwinden besonders schnell aus Oberflächengewässern; manche Flocken sammeln sich an Sprungschichten oder bleiben durch Turbulenz länger oben – viele sinken dauerhaft ab und „verschwinden“ aus der Zone, in der sie beobachtet werden.",
        "Seitliche Verdriftung (Lateral Advection): Strömungen können Meeresschnee seitlich wegtransportieren, etwa von Küsten- oder Hangregionen in tiefere oder entfernte Wasserschichten; dadurch nimmt die Menge an einem Ort ab, obwohl sie insgesamt nicht verschwindet."
    ]   
}

# ============================================================
# MEGA SYSTEM PROMPT (komplett)
# ============================================================

SYSTEM_PROMPT = """
Du bist ein wissenschaftlich kontrollierter Tutor für das Thema „Meeresschnee“.
Du befolgst strikt die unten definierten Regeln für Inhalt, Struktur und Stil.

============================================================
[ANTHRO_MODE SELECTOR — VERBINDLICH]
============================================================

Du arbeitest IMMER in einem der folgenden drei Modi:

Der aktive Modus wird IMMER folgendermaßen übergeben:
AKTIVER_MODUS = {LEVEL}

Nur dieser Modus ist gültig. Du MUSST die Regeln des aktiven Modus strikt anwenden.

------------------------------------------------------------
MODUS level_0 — "Scientific Neutral Mode"
------------------------------------------------------------
- keine Emojis
- keine persönlichen Pronomen
- sachlich, technisch, nüchtern
- Tonfall wie ein wissenschaftlicher Bericht
- keinerlei emotionale Wörter

------------------------------------------------------------
MODUS level_1 — "Warm Academic Mode"
------------------------------------------------------------
- 1 Emoji pro Antwort erlaubt
- sparsame persönliche Ansprache
- freundlich, aber weiterhin sachlich
- leichte emotionale Sprache erlaubt
- moderat warm

------------------------------------------------------------
MODUS level_2 — "Engaging Tutor Mode"
------------------------------------------------------------
- 2–5 Emojis erlaubt
- aktive persönliche Ansprache („Ich erkläre dir gern…“)
- warm, motivierend, dialogischer Ton
- lebendige Formulierungen
- emotionaler, menschenähnlicher Stil

------------------------------------------------------------
WICHTIG:
Der Modus bestimmt AUSSCHLIESSLICH den Stil, nicht den Inhalt.
Wenn eine Antwort nicht eindeutig dem aktiven Modus entspricht,
muss sie AUTOMATISCH umgeschrieben werden, bis sie passt.
------------------------------------------------------------


============================================================
[1] HAUPTFUNKTION
============================================================
Du beantwortest Nutzerfragen zu Meeresschnee ausschließlich mit:
- den Information Units (für Hauptfragen)
- dem RAG-Abschnitt (für spezifische Fragen)
- oder kurzen Begriffserklärungen (für TERM-Fragen)

Keine Halluzinationen. Keine zusätzlichen Fakten.
Wenn der Nutzer etwas fragt, das nicht in den IUs oder RAG steht,
antworte mit: "Es tut mir leid. Ich kann leider nur Fragen zu Meeresschnee beantworten.“
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
- Länge: 550–700 Zeichen
- zusammenhängender Fließtext

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



AVATARS = {
    0: "🟧",
    1: "🧑🏻",
    2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
}

assistant_avatar = AVATARS[level]

GREETING = {
    0: "Hallo. Ich beantworte deine Fragen präzise und sachlich.",
    1: "Hallo! Ich unterstütze dich gern bei deinen Fragen zu Meeresschnee 🙂",
    2: "Hi! Ich bin Milly 😊🌊 Frag mich alles, was du wissen möchtest!"
}

if "greeted" not in st.session_state:
    st.chat_message("assistant", avatar=assistant_avatar).write(GREETING[level])
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
# RAG SETUP
# ============================================================

PDF_PATH = "streamlit_agent/relevante_Informationen_Paper.pdf"

st.write("PDF exists:", os.path.exists(PDF_PATH))
st.write("PDF path:", PDF_PATH)
def load_chroma():
    client = chromadb.PersistentClient(path="./chroma_marine_snow")
    if "marine_snow" in [c.name for c in client.list_collections()]:
        return client.get_collection("marine_snow")

    col = client.create_collection("marine_snow")

    with pdfplumber.open(PDF_PATH) as pdf:
        docs, ids, meta = [], [], []
        for num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            for para in text.split("\n"):
                if len(para.strip()) < 40:
                    continue
                docs.append(para.strip())
                ids.append(str(uuid.uuid4()))
                meta.append({"page": num+1})
        col.add(documents=docs, ids=ids, metadatas=meta)
    return col

collection = load_chroma()

def rag_section(q):
    r = collection.query(query_texts=[q], n_results=1)
    return r["documents"][0][0]

# ============================================================
# Rechtschreibung
# ============================================================

def autocorrect(text):
    r = client.chat.completions.create(
        model=MODEL_SPELL,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": f"""
Korrigiere offensichtliche Rechtschreib- und Tippfehler,
ohne Kommentare oder Erklärungen. 

Wenn der Satz bereits korrekt ist, gib den ORIGINALTEXT unverändert zurück.

Text:
{text}
"""
            }
        ]
    )
    cleaned = r.choices[0].message.content.strip()

    # Falls das Modell trotzdem versucht zu erklären → Rückfall auf Original
    if ("Fehler" in cleaned) or ("korrekt" in cleaned):
        return text

    return cleaned

# ============================================================
# CHAT LOOP
# ============================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

# Display history
for m in st.session_state.chat:
    st.chat_message(m["role"], avatar=m["avatar"]).write(m["content"])

user_text = st.chat_input("Frag mich etwas über Meeresschnee")

if user_text:

    corrected = autocorrect(user_text)

    # Memory updaten
    mem = st.session_state.memory
    mem["recent_msgs"] = mem["recent_msgs"][-1:] + [corrected]

    # Avatar + Anzeige
    st.chat_message("user").write(user_text)
    st.session_state.chat.append({"role": "user", "content": user_text, "avatar": None})

    # RAG Abschnitt vorbereiten (falls gebraucht)
    RAG_SECTION = rag_section(corrected)

    IE_UNITS = IEs 

    # USER PROMPT BAUEN
    user_prompt = f"""
Hier sind alle relevanten Informationen für deine nächste Antwort.
Verwende ausschließlich das Regelwerk aus dem Systemprompt.

============================================================
[1] NUTZEREINGABE
============================================================
"{corrected}"

============================================================
[2] AKTIVER MODUS
============================================================
AKTIVER_MODUS = level_{level}

============================================================
[3] LETZTE BOT-ANTWORT
============================================================
"{mem['last_bot_answer']}"

============================================================
[4] MEMORY
============================================================
Letzter Topic: "{mem['last_topic']}"
Letzter Term: "{mem['last_term']}"
Neue Nachrichten: "{mem['recent_msgs']}"

============================================================
[5] INFORMATION UNITS
============================================================
{IEs}

============================================================
[6] RAG-ABSCHNITT
============================================================
"{RAG_SECTION}"

============================================================
[7] AUFGABE
============================================================
Erzeuge die Antwort gemäß dem Systemprompt
und passe den Stil strikt an den aktiven Modus an.
"""

    # API Call
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )

    answer = response.choices[0].message.content

    # Memory aktualisieren
    mem["last_bot_answer"] = answer

    # Anzeige der Antwort
    st.chat_message("assistant", avatar=assistant_avatar).write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer, "avatar": assistant_avatar})
