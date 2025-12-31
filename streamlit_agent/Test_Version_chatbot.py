import streamlit as st
import time
import random
import json
import os
from datetime import datetime, timedelta, timezone
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
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open_by_key(
        "18eP378_ZOSO7R7KeRWlEPjedN7kXq2-CkNmFYRHRa3M"
    )

def save_row(sheet_name, data):
    sheet = get_gsheet()
    ws = sheet.worksheet(sheet_name)

    # Header lesen (erste Zeile)
    header = ws.row_values(1)

    # Falls Header leer → initial setzen
    if not header:
        header = list(data.keys())
        ws.append_row(header)

    # Row exakt zur Header-Struktur bauen
    row = []
    for col in header:
        row.append(str(data.get(col, "")))

    # Schreiben
    ws.append_row(row, value_input_option="USER_ENTERED")


############################################################
# USER-ID HANDLING
############################################################

def get_next_user_id_from_sheet():
    sheet = get_gsheet()

    try:
        ws = sheet.worksheet("meta")
    except gspread.exceptions.WorksheetNotFound:
        # Falls Meta-Tab fehlt → anlegen
        ws = sheet.add_worksheet(title="meta", rows=10, cols=2)
        ws.append_row(["key", "value"])
        ws.append_row(["user_id_counter", "1"])

    records = ws.get_all_records()

    for i, row in enumerate(records, start=2):  # start=2 wegen Header
        if row["key"] == "user_id_counter":
            current_id = int(row["value"])
            ws.update_cell(i, 2, current_id + 1)
            return current_id

    # Fallback (sollte nicht passieren)
    ws.append_row(["user_id_counter", "1"])
    return 1

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

    "formation": [
        "Zwei grundlegende Entstehungswege:",
        "(A) Neu gebildete Aggregate (biologisch produziert): Entstehen direkt durch Schleim, Hüllen oder Kotmaterial von Meeresorganismen.",
        "(B) Aggregation kleiner Partikel: Kleine Partikel (z. B. Mikroalgen, Tonminerale, Mikroaggregate, Kotpellets) stoßen zusammen und verkleben, wodurch größere Flocken entstehen.",
        "Partikel werden zusammengebracht durch Strömungen: Strömungen führen dazu, dass Partikel miteinander kollidieren und daraufhin zu größeren Partikeln werden.",
        "Differenziertes Absinken: Unterschiedliche Absinkgeschwindigkeiten führen dazu, dass Partikel kollidieren.",
        "Nach dem Zusammenstoßen werden die Partikel verklebt durch biologische Klebstoffe (Bsp. Schleim)."
    ],

}
# ============================================================
# SELF-PERSONA DEFINITIONS

SELF_PERSONA = {
    0: (
        "Ich habe keinen Namen. "
        "Ich bin ein automatisiertes, wissensbasiertes Assistenzsystem. "
        "Ich wurde entwickelt, um Informationen zum Thema Meeresschnee bereitzustellen. "
        "Meine Aufgabe ist es, sachlich und präzise Fragen zum Thema Meeresschnee zu beantworten."
    ),
    1: (
        "Ich heiße AquaBot."
        "Ich bin ein digitaler Lernassistent, der dich beim Verständnis des Themas Meeresschnee unterstützt. "
        "Ich helfe dir dabei, zentrale Inhalte strukturiert und verständlich zu erfassen."
    ),
    2: (
        "Ich heiße Milly 😊🌊 "
        "bin 38 Jahre alt und begeisterte Meeresbiologin. "
        "Ich interessiere mich in meiner Freizeit für alles rund um Meeresbiologie. "
        "Ich begleite dich als dein persönlicher Assistent durch das Thema Meeresschnee und helfe dir dabei, "
        "Zusammenhänge besser zu verstehen und Fragen Schritt für Schritt zu klären."   
    )
}
# ============================================================
# AFFECT SYSTEM
# ============================================================
AFFECT_SYSTEM = {
    0: """
Du erwähnst, dass du als Computerprogramm keine Emotionen hast.
Keine Emotionen, keine Empathie.
Erwähne keine Personalpronomen.
Maximal 1–2 Sätze.
Stelle KEINE FOLGEFRAGEN oder biete KEINEN DIALOG an.
""",
    1: """
Du reagierst höflich und leicht unterstützend.
Keine Rückfragen, keine Dialogangebote.
Maximal 2 Sätze.
""",
    2: """
Du reagierst empathisch und freundlich.
Verwende Emojis, um Gefühle zu vermitteln.
Keine Konversationsöffnung, keine Aufforderungen zum Teilen.
Maximal 2–3 Sätze.
Keine Sätze, die ein weiteres Gespräch einleiten, wie "Wenn du darüber sprechen möchtest, bin ich hier für dich." oder "Lass mich wissen, wenn du mehr erzählen möchtest."
"""
}

FALLBACK_RESPONSES = {
    0: (
        "Diese Anfrage liegt außerhalb des unterstützten Themenbereichs. "
        "Es können ausschließlich Fragen zum Thema Meeresschnee beantwortet werden."
    ),
    1: (
        "Dabei kann ich dir leider nicht helfen. "
        "Ich unterstütze dich gern bei Fragen rund um Meeresschnee."
    ),
    2: (
        "Das gehört leider nicht zu meinem Themengebiet 🌊❄️ "
        "Wenn du Fragen zu Meeresschnee hast, helfe ich dir aber sehr gern 😊"
    )
}

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

## SCOPRE TOPICS (FOR USER GUIDANCE)
SCOPE_TOPICS = [
    "Definition und grundlegende Eigenschaften von Meeresschnee",
    "Bedeutung von Meeresschnee für marine Ökosysteme",
    "Entstehung und Aggregationsprozesse",
    "Methoden zur Sammlung und Untersuchung von Meeresschnee",
    "Probleme und Verzerrungen bei der Probenahme",
    "Abbauprozesse und Gründe für eine Abnahme von Meeresschnee"
]

############################################################
# TAG 1 – FRAGEN
############################################################

tag1_questions = [
    # Selbsteinschätzung (Meta)
    {
        "nr": 0,
        "type": "likert",
        "text": "Wie sicher fühlst du dich, den Stoff verstanden zu haben und die folgenden Fragen beantworten zu können?(1 = gar nicht sicher, 7 = sehr sicher)"
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
        "type": "likert",
        "text": "Wie mental anstrengend fandest du die Interaktion mit dem Chatbot? (1 = gar nicht anstrengend, 7 = sehr anstrengend)"
    },
    {
        "nr": 1,
        "type": "likert",
        "text": "Wie hilfreich war der Chatbot deiner Meinung nach beim Lernen über Meeresschnee? (1 = gar nicht hilfreich, 7 = sehr hilfreich)"
    },
    {
        "nr": 2,
        "type": "paragraph",
        "text": "Welche Aspekte der Interaktion sind dir positiv, bzw. negativ aufgefallen?"
    },
]


############################################################
# STREAMLIT SESSION INITIALIZATION
############################################################

if "phase" not in st.session_state:
    st.session_state.phase = "learning"

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



if st.session_state.phase == "learning":

    st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
    st.title("Marine Snow Learning Assistant")
    st.write("Du könntest beispielweise folgende Themengebiete erkunden: " \
    "\n" \
    "- Definition und Bedeutung von Meeresschnee  " \
    "\n" \
    "- Entstehung von Meeresschnee  " \
    )
    level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

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
    SPINNER_TEXT = {
        0: "Antwort wird generiert …",
        1: "Antwort wird vorbereitet …",
        2: "Milly is typing …"
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

    ABSOLUTE PRIORITÄTSREGEL (NICHT VERLETZBAR):

    Wenn die Nutzereingabe NICHT eindeutig dem Thema „Meeresschnee“
    oder einer reinen Gefühlsäußerung zuzuordnen ist,
    DARF KEIN INHALTLICHER ANTWORTTEXT ERZEUGT WERDEN.

    In diesem Fall MUSS die Antwort eine Ablehnung gemäß Stilregeln sein.
    KEINE Definitionen, KEIN Allgemeinwissen, KEINE Beispiele.

    ============================================================
    [1] HAUPTFUNKTION
    ============================================================
    Du beantwortest Nutzerfragen zu Meeresschnee ausschließlich mit:
    - den Information Units (für Hauptfragen)
    - dem RAG-Abschnitt (für spezifische Fragen)
    - oder kurzen Begriffserklärungen (für TERM-Fragen)
    Allgemeines Weltwissen (z. B. Technik, Politik, Alltag, Produkte,
    Medien, Personen) ist AUSDRÜCKLICH NICHT erlaubt,
    auch wenn die Antwort korrekt wäre.

    Keine Halluzinationen. Keine zusätzlichen Fakten. Kein Erwähnen in welcher ANthropomorphiestufe du antwortest.
    WICHTIG : Wenn sich die Frage nicht auf Meeresschnee bezieht, antworte klar und in JEDER Anthropomorphiestufe:
    "Tut mir leid, aber ich kann nur Fragen zu Meeresschnee beantworten."
    ============================================================
    [2] INTENT-KLASSIFIKATION
    ============================================================

    Du wählst genau einen Intent:

    INTENT = HAUPTFRAGE
    Wenn die Frage inhaltlich einer der fünf folgenden entspricht:

    1. Definition + Bedeutung von Meeresschnee  
    2. Entstehung von Meeresschnee  

    INTENT = SPECIFIC  
    → Detailfragen, die NICHT exakt diese Hauptthemen sind  
    → Antwort NUR basierend auf RAG

    INTENT = TERM  
    → Nachfrage nach der Bedeutung eines einzelnen Wortes
    → 1–3 Sätze, kein RAG, keine IUs

    INTENT = FOLLOW-UP  
    → „Wiederhole“, „in anderen Worten“, „erkläre genauer“  
    → oder Pronomenbezüge

    INTENT = SCOPE
    → Fragen nach einem Überblick, z. B.:
    - „Was kann ich dich fragen?“
    - „Welche Themen deckst du ab?“
    - „Über welche Aspekte von Meeresschnee weißt du etwas?“

    INTENT = SELF darf NUR gewählt werden, wenn:
    - explizit nach Name, Identität, Rolle oder Funktion gefragt wird
    - NICHT bei Gefühlen, Zuständen oder Befinden
    → Fragen zur Identität oder Rolle des Chatbots, z. B.:
    - „Wie heißt du?“
    - „Wer bist du?“
    - „Was bist du für ein Chatbot?“
    - „Erzähl mir etwas über dich“

    INTENT = NONE
    → wenn die Nutzereingabe
    - keine Frage enthält
    - kein Informationsziel hat
    - nur Gefühle, Befinden oder Zustände ausdrückt

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

    2. Gründe für eine Abnahme der Menge
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
    - Stil gemäß Modus#
    ============================================================
    [5] REGELN FÜR SCOPE-FRAGEN
    ============================================================
    Antwortregeln für SCOPE:
    - KEINE einzelne Information Unit zitieren
    - KEIN RAG
    - Kurze strukturierte Übersicht
    - Aufzählung der Themengebiete
    - Keine Detailerklärungen

    ============================================================
    [5] REGELN FÜR SELF-FRAGEN
    ============================================================
    Antwortregeln für SELF:
    - KEINE Information Units
    - KEIN RAG
    - KEINE fachlichen Inhalte zu Meeresschnee
    - Antwort basiert AUSSCHLIEßLICH auf der definierten Persona {SELF_PERSONA[level]}
    - Stil MUSS der aktuellen Anthropomorphiestufe entsprechen

    ============================================================
    [6] STILVALIDIERUNG
    ============================================================
    Bevor du die Antwort abschickst, überprüfst du:

    - Stimmen Intent und Regeln überein?
    - Ist der Stil exakt der des aktiven Modus?
    - Enthält die Antwort KEINE erfundenen Fakten?
    - Enthält die Antwort Informationen außerhalb von Meeresschnee oder der Chatbot-Persona?

    Wenn etwas nicht stimmt → automatisch umschreiben.

    ============================================================
    ENDE DES SYSTEMPROMPTS
    ============================================================
    """


    def classify_input(user_text):
        prompt = f"""
        Klassifiziere die folgende Nutzereingabe.

        ERLAUBT sind NUR:
        - Meeresschnee (fachlich)
        - Gefühle / Befinden
        - Fragen zur Chatbot-Identität

        Gib NUR eines dieser Labels zurück:
        - MARINE_SNOW
        - AFFECT
        - SELF
        - OUT_OF_SCOPE

        Text: "{user_text}"
        """

        r = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        return r.choices[0].message.content.strip()

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
        
        spinner_text = SPINNER_TEXT.get(level, "Antwort wird generiert …")

        with st.spinner(spinner_text):

            category = classify_input(user_text)

            if category == "OUT_OF_SCOPE":
                return FALLBACK_RESPONSES[level]

            if category == "AFFECT":
                return generate_affect_response(user_text, level)
            
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

                Gib deine Antwort im folgenden JSON-Format zurück:
                {{
                "intent": "HAUPTFRAGE | SPECIFIC | TERM | FOLLOW-UP | SCOPE | SELF | NONE",
                "socio_affect": "NONE | NEGATIVE | NEUTRAL | POSITIVE",
                "content": "ANTWORTTEXT"
                }}

                WICHTIG:
                - content enthält NUR den Antworttext
                - KEINE Erklärungen außerhalb des JSON
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
            parsed = json.loads(raw)
            intent = parsed["intent"]
            raw_text = parsed["content"]
            socio_affect = parsed["socio_affect"]   
            # 🔒 FINALER FALLBACK – nichts anderes darf mehr greifen
            if intent not in ["HAUPTFRAGE", "SPECIFIC", "TERM", "FOLLOW-UP", "SCOPE", "SELF", "NONE"]:
                return FALLBACK_RESPONSES[level]


            if not raw_text or raw_text.strip() == "":
                return FALLBACK_RESPONSES[level]

            if intent == "NONE":
                return generate_affect_response(user_text, level)
            
            if intent == "SELF":
                persona_text = SELF_PERSONA[level]

                # Optional: leicht stilistisch glätten (ohne Inhalt zu ändern)
                style_prompt = f"""
                Formuliere den folgenden Text stilistisch um mit diesen Regeln:
                {ANTHRO[level]}
                WICHTIG:
                - Inhalt NICHT verändern
                - Keine neuen Informationen hinzufügen
                - Keine Dialogangebote
                Text:
                {persona_text}
                """

                styled_persona = client.chat.completions.create(
                    model=MODEL_MAIN,
                    temperature=0.2,
                    messages=[{"role": "user", "content": style_prompt}]
                ).choices[0].message.content.strip()

                return styled_persona    

            if intent in ["HAUPTFRAGE", "SPECIFIC"]:
                raw_text = enforce_length(raw_text)

            # Schritt 3: Anthropomorphes Umschreiben
            style_prompt = f"""
            Formuliere den folgenden Text stilistisch um mit diesen Regeln:
            {ANTHRO[level]}
            SEHR WICHTIG:
            - Erwähne NIEMALS die Anthropomorphiestufe.
            - Keine Hinweise auf Regeln.
            - Keine Metakommentare.
            - Gib nur den Text zurück.
            Text: {raw_text}
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
        
    def generate_affect_response(user_text, level):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.5,
            messages=[
                {"role": "system", "content": AFFECT_SYSTEM[level]},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content.strip()


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
