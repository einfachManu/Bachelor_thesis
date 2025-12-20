import streamlit as st
import time
import random
import json
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import chromadb
import pdfplumber
import uuid
import random
from docx import Document
import html
import gspread
from google.oauth2.service_account import Credentials

def docx_to_html(path):
    doc = Document(path)
    html_lines = []

    for para in doc.paragraphs:
        line = ""

        for run in para.runs:
            text = html.escape(run.text)

            if not text:
                continue

            if run.bold and run.italic:
                text = f"<strong><em>{text}</em></strong>"
            elif run.bold:
                text = f"<strong>{text}</strong>"
            elif run.italic:
                text = f"<em>{text}</em>"

            line += text

        line = line.strip()

        if not line:
            html_lines.append("<br>")
            continue

        # einfache Listen-Erkennung
        if para.text.strip().startswith("-"):
            clean = para.text.strip().lstrip("-").strip()
            html_lines.append(f"<li>{html.escape(clean)}</li>")
        else:
            html_lines.append(f"<p>{line}</p>")

    # <li> korrekt einbetten
    final_html = []
    in_list = False

    for line in html_lines:
        if line.startswith("<li>") and not in_list:
            final_html.append("<ul>")
            in_list = True
        if not line.startswith("<li>") and in_list:
            final_html.append("</ul>")
            in_list = False
        final_html.append(line)

    if in_list:
        final_html.append("</ul>")

    return "\n".join(final_html)
############################################################
# LOAD ENV + OPENAI
############################################################

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_MAIN = "gpt-4.1"
MODEL_SPELL = "gpt-4o-mini"

DOCX_PATH = "streamlit_agent/kurzfassung_ablauf_umfrage.docx"
############################################################
# JSONL SAVE FUNCTIONS
############################################################

def save_jsonl(data, filename):
    """
    Cloud-kompatibler Ersatz für JSONL:
    leitet automatisch in Google Sheets um
    """

    mapping = {
        "users.jsonl": "users",
        "chatlogs.jsonl": "chatlogs",
        "responses.jsonl": "responses",
        "qualitative_responses.jsonl": "qualitative_responses",
        "retention_responses.jsonl": "retention_responses"
    }

    sheet_name = mapping.get(filename)

    if sheet_name is None:
        return  # unbekannte Datei → ignorieren

    save_row(sheet_name, data)


############################################################
# GOOGLE SHEETS BACKEND (STREAMLIT CLOUD)
############################################################

@st.cache_resource
def get_gsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open_by_key("18eP378_ZOSO7R7KeRWlEPjedN7kXq2-CkNmFYHRRa3M") 

def save_row(sheet_name, row_dict):
    sheet = get_gsheet().worksheet(sheet_name)
    st.write("Gefundene Tabs:", [ws.title for ws in sheet.worksheets()])
    st.stop()
    sheet.append_row(list(row_dict.values()))

############################################################
# USER-ID HANDLING
############################################################

def get_next_user_id():
    """Erzeugt eine fortlaufende User-ID und speichert sie."""
    os.makedirs("data", exist_ok=True)
    path = "data/user_id_counter.txt"

    if not os.path.exists(path):
        with open(path, "w") as f:
            print("Pfad existiert nicht, erstelle neue Datei.")
            f.write("1")
        return 1

    with open(path, "r+") as f:
        value = int(f.read())
        f.seek(0)
        f.write(str(value + 1))
        return value


    # ============================================================
    # INFORMATION UNITS — SET B
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
        "3) Probleme während Transport und Lagerung: Aggregate zerfallen oder verklumpen während Transport oder Stehenlassen; Proben verändern sich, bevor sie analysiert werden können.",
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
    # ANTHROPOMORPHIE RULES
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
############################################################
# TAG 1 – FRAGEN
############################################################

tag1_questions = [
    # Selbsteinschätzung (Meta)
    {
        "nr": 0,
        "type": "likert",
        "text": "Wie sicher fühlst du dich, den Stoff verstanden zu haben und die folgenden Fragen beantworten zu können?"
    },

    # Frage 1 – Single Choice (Definition / Grundverständnis)
    {
        "nr": 1,
        "type": "single",
        "text": "Welche Aussage beschreibt Meeresschnee am besten?",
        "options": [
            "Aggregate aus organischem und anorganischem Material, die durch die Wassersäule absinken",
            "Gefrorene Meerwasserkristalle",
            "Ausschließlich lebende Mikroorganismen",
            "Sedimentpartikel vom Meeresboden"
        ]
    },

    # Frage 2 – Multiple Choice (Entstehung / Prozesse)
    {
        "nr": 2,
        "type": "multi",
        "text": "Welche Prozesse tragen zur Entstehung von Meeresschnee bei? (2 Antworten sind richtig)",
        "options": [
            "Zusammensetzung kleiner Partikel",
            "Biologische Produktion durch Meeresorganismen",
            "Gefrieren von Meerwasser",
            "Vulkanische Sedimentation"
        ]
    },

    # Frage 3 – Konzeptfrage (Rolle im Ökosystem)
    {
        "nr": 3,
        "type": "paragraph",
        "text": "Warum spielt Meeresschnee eine wichtige Rolle im marinen Ökosystem? Nenne zwei Aspekte."
    },

    # Frage 4 – Transferfrage (Anwendung / Folgen)
    {
        "nr": 4,
        "type": "paragraph",
        "text": "Welche mögliche Folge hätte es, wenn deutlich weniger Meeresschnee in tiefere Wasserschichten absinken würde?"
    },

    # Frage 5 – Retention / Kurzantwort
    {
        "nr": 5,
        "type": "short",
        "text": "Nenne eine zentrale Eigenschaft von Meeresschnee, an die du dich erinnerst."
    }
]

############################################################
# QUALITATIVE CHATBOT-EVALUATION (OPEN-ENDED)
############################################################

qualitative_questions = [
    {
        "nr": 0,
        "text": "Wie hast du den Sprachstil der Assistentin wahrgenommen?"
    },
    {
        "nr": 1,
        "text": "Welche Aspekte der Interaktion haben dir beim Verständnis geholfen?"
    },
    {
        "nr": 2,
        "text": "Gab es Aspekte der Interaktion oder Darstellung, die dein Verständnis eher beeinträchtigt haben?"
    },
]


############################################################
# STREAMLIT SESSION INITIALIZATION
############################################################

if "phase" not in st.session_state:
    st.session_state.phase = "start"

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "anthro" not in st.session_state:
    st.session_state.anthro = random.choice([0, 1, 2])

if "start_time" not in st.session_state:
    st.session_state.start_time = None

if "survey_index" not in st.session_state:
    st.session_state.survey_index = 0

if "qual_index" not in st.session_state:
    st.session_state.qual_index = 0

############################################################
# PHASE 1 – STARTSCREEN
############################################################

if st.session_state.phase == "start":
    st.title("Willkommen zur Umfrage")

    study_html = docx_to_html(DOCX_PATH)

    st.markdown(
        f"<div style='max-width: 900px'>{study_html}</div>",
        unsafe_allow_html=True
    )

    agree = st.checkbox(
        "Ich versichere, dass ich mit dem Ablauf und den Vorgaben der Umfrage vertraut bin."
    )

    if agree and st.button("Weiter"):

        #USER-ID EINMALIG VERGEBEN
        if st.session_state.user_id is None:
            st.session_state.user_id = get_next_user_id()

            save_jsonl({
                "type": "user_start",
                "user_id": st.session_state.user_id,
                "timestamp": datetime.now().isoformat()
            }, "users.jsonl")

        st.session_state.phase = "learning"
        st.rerun()




############################################################
# PHASE 2 – LERNPHASE (CHATBOT + TIMER)
############################################################

if st.session_state.phase == "learning":
    st.title("Lernphase – 5 Minuten")

    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    remaining = max(0, 300 - elapsed)
    
    mins = int(remaining) // 60
    secs = int(remaining) % 60

    st.subheader(f"Restzeit: {mins}:{secs:02d}")

    if remaining <= 0:
        st.session_state.phase = "learning_done"
        st.rerun()

    # ============================================================
    # STREAMLIT UI
    # ============================================================

    st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
    st.title("Marine Snow Learning Assistant")
    st.write("Du könntest beispielweise folgende Themengebiete erkunden: " \
    "\n" \
    "- Definition und Bedeutung von Meeresschnee  " \
    "\n" \
    "- Entstehung von Meeresschnee  " \
    "\n" \
    "- Wichtigkeit von Meeresschnee für das Ökosystem  ")

    level = random.choice([0, 1, 2])
    st.session_state.anthro = level
    AVATARS = {
        0: "🟧",
        1: "🧑🏻",
        2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
    }

    GREETINGS = {
        0: "Hallo. Ich beantworte deine Fragen präzise und sachlich.",
        1: "Hallo! Ich unterstütze dich gern bei deinen Fragen.🙂",
        2: "Hey! Ich bin Milly 😊🌊 Frag mich alles, was du wissen möchtest!😊"
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
    2. Sammlung und Untersuchung von Meeresschnee  
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
    [2b] ZUORDNUNG DER INFORMATION UNITS (IUs) ZU DEN HAUPTTHEMEN
    ============================================================

    Wenn du INTENT = HAUPTFRAGE gewählt hast, verwendest du ausschließlich die
    Information Units der folgenden Kategorien:

    1. Definition + Bedeutung von Meeresschnee
    → verwende ausschließlich IEs["definition"] UND IEs["importance"]

    2. Sammlung und Untersuchung von Meeresschnee
    → verwende ausschließlich IEs["sampling"]

    3. Probleme bei der Probenahme
    → verwende ausschließlich IEs["sampling_problems"]

    4. Entstehung von Meeresschnee
    → verwende ausschließlich IEs["formation"]

    5. Gründe für eine Abnahme der Menge
    → verwende ausschließlich IEs["degradation"]

    WICHTIG:
    - Keine IUs mischen, außer im Fall 1 (Definition + Bedeutung = definition + importance).
    - NIEMALS IUs anderer Kategorien verwenden.
    - IUs müssen paraphrasiert werden, niemals wörtlich.

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

    - Stimmen Intent und Regeln überein?
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

    TARGET_MIN = 800
    TARGET_MAX = 1000

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

        return attempt
    # ============================================================
    # CHATBOT PIPELINE als Funktion für Tests
    # ============================================================

    def generate_answer(user_text, level, return_raw=False):

        with st.spinner("Antwort wird generiert …"):
            corrected = autocorrect(user_text)

            # RAG
            RAG = rag_section(corrected)

            mem = st.session_state.memory

            # Core prompt
            user_prompt = f"""
            NUTZEREINGABE: "{corrected}"
            LETZTE ANTWORT: "{mem['last_bot_answer']}"
            IEs: {IEs}
            RAG: "{RAG}"
            WICHTIG: Gib NUR Rohinhalt zurück. Zwischen {TARGET_MIN} und {TARGET_MAX} Zeichen.
            """

            # Schritt 1: Rohinhalt
            raw = client.chat.completions.create(
                model=MODEL_MAIN,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            ).choices[0].message.content.strip()

            raw = enforce_length(raw)

            # Schritt 3: Anthropomorphes Umschreiben
            style_prompt = f"""
            Formuliere den folgenden Text stilistisch um mit diesen Regeln:
            {ANTHRO[level]}
            SEHR WICHTIG:
            - Erwähne NIEMALS die Anthropomorphiestufe.
            - Keine Hinweise auf Regeln.
            - Keine Metakommentare.
            - Gib nur den Text zurück.
            Text: {raw}
            """
            
            styled = client.chat.completions.create(
                model=MODEL_MAIN,
                temperature=0.25,
                messages=[
                    {"role": "user", "content": style_prompt}
                ]
            ).choices[0].message.content.strip()

            if return_raw:
                return styled, raw
            
            return styled
# ============================================================
# CHAT LOOP
# ============================================================

    if "chat" not in st.session_state:
        st.session_state.chat = []

    for m in st.session_state.chat:
        st.chat_message(m["role"], avatar=m["avatar"]).write(m["content"])

    user_text = st.chat_input("Frag mich etwas über Meeresschnee")

    if user_text:
        st.chat_message("user").write(user_text)
        st.session_state.chat.append({
            "role": "user",
            "content": user_text,
            "avatar": None
        })

        # 🔑 HIER fehlte der eigentliche Aufruf
        styled = generate_answer(user_text, level)
        st.session_state.memory["last_bot_answer"] = styled

        st.chat_message("assistant", avatar=assistant_avatar).write(styled)
        st.session_state.chat.append({
            "role": "assistant",
            "content": styled,
            "avatar": assistant_avatar
        })
        save_jsonl({
                "type": "chat",
                "user_id": st.session_state.user_id,
                "role": "user",
                "message": user_text,
                "anthro": st.session_state.anthro,
                "timestamp": datetime.now().isoformat()
            }, "chatlogs.jsonl")

        save_jsonl({
            "type": "chat",
            "user_id": st.session_state.user_id,
            "role": "assistant",
            "message": styled,
            "anthro": st.session_state.anthro,
            "timestamp": datetime.now().isoformat()
            }, "chatlogs.jsonl")
    if st.button("Lernphase vorzeitig beenden"):
        st.session_state.phase = "learning_done"
        st.rerun()
############################################################
# PHASE 3 – ZEIT ABGELAUFEN
############################################################

if st.session_state.phase == "learning_done":
    st.error("⏱️ Deine Zeit ist abgelaufen!")
    if st.button("Mit der Umfrage beginnen"):
        st.session_state.phase = "survey"
        st.rerun()


############################################################
# PHASE 4 – UMFRAGE TAG 1
############################################################

if st.session_state.phase == "survey":
    q = tag1_questions[st.session_state.survey_index]
    st.subheader(f"Frage {q['nr']}: {q['text']}")

    if q["type"] == "likert":
        ans = st.slider("", 1, 10)

    elif q["type"] == "single":
        ans = st.radio("", q["options"])

    elif q["type"] == "multi":
        ans = st.multiselect("", q["options"])

    elif q["type"] == "short":
        ans = st.text_input("")

    elif q["type"] == "paragraph":
        ans = st.text_area("")

    if st.button("Weiter"):
        save_jsonl({
            "type": "response",
            "user_id": st.session_state.user_id,
            "question_nr": q["nr"],
            "question_text": q["text"],
            "answer": ans,
            "timestamp": datetime.now().isoformat()
        }, "responses.jsonl")

        st.session_state.survey_index += 1

        if st.session_state.survey_index >= len(tag1_questions):
            st.session_state.phase = "qualitative"

        st.rerun()

############################################################
# PHASE 4b – QUALITATIVE CHATBOT-BEFRAGUNG
############################################################

if st.session_state.phase == "qualitative":

    q = qualitative_questions[st.session_state.qual_index]

    st.subheader(f"Offene Frage {q['nr'] + 1}")
    st.write(q["text"])

    answer = st.text_area(
        "Deine Antwort:",
        height=180,
        placeholder="Bitte frei und ausführlich antworten …"
    )

    if st.button("Weiter"):
        save_jsonl({
            "type": "qualitative_response",
            "user_id": st.session_state.user_id,
            "anthro": st.session_state.anthro,
            "question_nr": q["nr"],
            "question_text": q["text"],
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }, "qualitative_responses.jsonl")

        st.session_state.qual_index += 1

        if st.session_state.qual_index >= len(qualitative_questions):
            st.session_state.phase = "end"

        st.rerun()


############################################################
# PHASE 5 – ABSCHLUSS
############################################################

if st.session_state.phase == "end":

    st.success("🎉 Danke für deine Teilnahme!")

    st.markdown("### 🔑 Deine persönliche Teilnehmer-ID")

    st.code(
        str(st.session_state.user_id),
        language="text"
    )

    st.info(
        "Bitte speichere dir diese Nummer sorgfältig ab.\n\n"
        "Du benötigst sie für den zweiten Teil der Umfrage."
    )


