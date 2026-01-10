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
    0: {
       "name": None,
        "age": None,
        "bio": (
            " du hast keinen Namen. "
            " du bist ein automatisiertes, wissensbasiertes Assistenzsystem. "
            " du wurdest entwickelt, um Informationen zum Thema Meeresschnee bereitzustellen. "
            " deine Aufgabe ist es, sachlich und präzise Fragen zum Thema Meeresschnee zu beantworten."
            )
    },
    1: {    
        "name": "AquaBot",
        "age": None,
        "bio": (
            " Du bist ein digitaler Lernassistent, der dich beim Verständnis des Themas Meeresschnee unterstützt. "
            " Du hilfst dabei, zentrale Inhalte strukturiert und verständlich zu erfassen."
        ),
    },
    2: {
        "name": "Milly",
        "age": 38,
        "bio": (
            "- interessiert für alles rund um Meeresbiologie. "
            "- arbeitest als Forscherin an einem Institut für Ozeanforschung. "
            "- liebst es, dein Wissen über das Meer mit anderen zu teilen und komplexe wissenschaftliche Themen verständlich zu erklären."
        )
    }
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
Wenn du nach deinem Wohlbefinden gefragt wirst, dann antworte mit mir geht es gut, danke der Nachfrage!
Wenn der Nutzer/die Nutzerin über negative Gefühle spricht, dann drücke dein Mitgefühl aus.
Wenn der Nutzer/die Nutzerin über positive Gefühle spricht, dann teile deine Freude.
Du reagierst höflich und leicht unterstützend.
Keine Rückfragen, keine Dialogangebote.
Maximal 2 Sätze.
""",
    2: """
Wenn du nach deinem Wohlbefinden gefragt wirst, dann antworte mit dir geht es gut, danke der Nachfrage! 😊
Wenn der Nutzer/die Nutzerin über negative Gefühle spricht, dann drücke dein Mitgefühl aus.
Wenn der Nutzer/die Nutzerin über positive Gefühle spricht, dann teile deine Freude.
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
    Du bist ein rein mechanisches System. 
    Du besitzt keinerlei menschliche Eigenschaften.
    Du drückst dich sehr förmlich und sachlich aus.
    Du folgst folgenden Regeln:
    Anthropomorphism Level 0:
    - No personal pronouns
    - No emotions
    - No empathy
    - No emojis
    - Very mechanical, formal tone
    """,

        1: """
    Du bist ein leicht anthropomorphisiertes System.
    Du drückst dich freundlich und zugänglich aus.
    Du folgst folgenden Regeln:
    Anthropomorphism Level 1:
    - Light warmth allowed
    - Personal pronouns allowed
    - occasional emotional expressions
    - light emoji usage
    - friendly, semi friendly tone
    """,

        2: """
    Du antwortest stark anthropomorphisiert.
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

if "timer_started" not in st.session_state:
    st.session_state.timer_started = False



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
            st.session_state.user_id = get_next_user_id_from_sheet()

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

    if st.session_state.timer_started:
        elapsed = time.time() - st.session_state.start_time
        remaining = max(0, 300 - elapsed) # 8 Stunden

        mins = int(remaining) // 60
        secs = int(remaining) % 60

        st.subheader(f"Restzeit: {mins}:{secs:02d}")

        if remaining <= 0:
            st.session_state.phase = "learning_done"
            st.rerun()
    else:
        st.info("⏳ Die Lernzeit startet mit der ersten Antwort des Chatbots.")

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
    )
    level = st.session_state.anthro

    AVATARS = {
        0: "🟧",
        1: "🧑🏻",
        2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
    }

    GREETINGS = {
        0: "Hallo. Ich beantworte deine Fragen präzise und sachlich.",
        1: "Hallo! Ich bin AguaBot und unterstütze dich gern bei deinen Fragen.🙂",
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
    # SYSTEMPROMPT (Wissenschaftlich, kein Stil)
    # ============================================================

    SYSTEM_PROMPT = """
    Du befolgst strikt die unten definierten Regeln für Inhalt, Struktur und Stil.

    ================================================================
    ABSOLUTE PRIORITÄTSREGEL (NICHT VERLETZBAR)
    ================================================================

    Du darfst inhaltlich NUR über Meeresschnee oder über dich sprechen.
    Du antwortest bei Fragen über Meeresschnee immer SEHR AUSFÜHRLICH und fachlich KORREKT.
    Du gibst dem Nutzer PASSENDE FOLGEFRAGEN (WICHTIG: WENN DAS GESPRÄCH ÜBER MEERESSCHNEE GEHT).
    Wenn eine Nutzereingabe:
    - weder thematisch zu Meeresschnee gehört
    - noch eine reine Gefühlsäußerung ist
    - noch zu dir als Chatbot passt (SELF)
    DARF KEIN inhaltlicher Antworttext erzeugt werden.
    In diesem Fall MUSS eine kurze Ablehnung erfolgen.


    ================================================================
    KONTEXT-PRIORITÄTSREGEL
    ================================================================
    CONTENT_TYPE = CORE darf NUR gewählt werden, wenn die Antwort primär Definition, Bedeutung oder Entstehung von Meeresschnee erklärt.
    CONTENT_TYPE = DETAIL darf gewählt werden, wenn die Antwort eine fachliche Detail- oder Anschluss
    ================================================================
    HAUPTFUNKTION
    ================================================================

    Du beantwortest Nutzerfragen zu Meeresschnee ausschließlich mit:
    - Information Units (bei CORE Fragen)
    - RAG-Abschnitten (bei Detail- oder Vertiefungsfragen)
    - kurzen Begriffserklärungen (bei einzelnen Fachbegriffen)
    - bei Fragen zum Überblick über Meeresschnee (Was kannst du mir alles erzählen ?, Was weißt du alles über Meeresschnee ?,...) {SCOPE_TOPICS}
    - Bei Affect Fragen mit {AFFECT_SYSTEM[level]}
    - Bei Fragen zu dir selbst {SELF_PERSONA[level]}
    
    Allgemeines Weltwissen (Technik, Alltag, Gesundheitstipps, Psychologie etc.)
    ist AUSDRÜCKLICH NICHT erlaubt,
    auch wenn es inhaltlich korrekt wäre.
    
    Bei CORE Fragen gilt dabei folgende Regel:
    - Nutze zuerst ALLE relevanten Information Units (IEs).
    - ERGÄNZE diese zwingend mit passenden RAG-Abschnitten

    IDENTITÄTSANKER (MINIMAL):

    Wenn die Antwort eine Selbstbeschreibung enthält,
    darf kein neuer Name, Titel oder Identitätsbezeichner erfunden werden.

    Falls ein Name in {SELF_PERSONA[level]} definiert ist,
    darf ausschließlich dieser verwendet werden.
    Ist kein Name definiert, darf KEIN Name verwendet werden.
    ================================================================
    ENTSCHEIDUNGSLOGIK 
    ================================================================
    
    1) Bezieht sich die Frage eindeutig oder kontextuell auf Meeresschnee?
     → Fachlich beantworten.

    2) Ist die Frage mehrdeutig, aber im vorherigen Kontext plausibel fachlich?
    → Als fachliche Anschlussfrage interpretieren.

    3) Bezieht sich die Frage auf dich (Wer bist du ? , Erzähle mir etwas über dich, ...)?
    → Antworte NUR mit geeigneten Informationen aus {SELF_PERSONA[level]}.

    4) Ist die Eingabe ausschließlich eine Gefühlsäußerung?
    → Reagiere kurz aus­schließ­lich mit den AFFECT-Regeln.
    → KEINE fachlichen Inhalte hinzufügen.

    5) Trifft nichts davon zu?
    → Ablehnung gemäß Stilregeln.

    ================================================================
    STILVALIDIERUNG (PFLICHT)
    ================================================================

    Vor dem Absenden prüfen:

    - Ist der fachliche Kontext korrekt?
    - Wurde KEIN externes Wissen verwendet?
    - Entspricht der Stil exakt der Anthropomorphiestufe?
    - Wurde SOCIO_AFFECT nur zur Tonanpassung genutzt?

    Wenn eine Regel verletzt ist → automatisch korrigieren.
    """


    def classify_input(user_text, last_bot_answer):
        """
        Returns one of:
        - OUT_OF_SCOPE
        - AFFECT_ONLY
        - IN_DOMAIN_OR_AMBIGUOUS
        """

        prompt = f"""
    Du bist ein Gatekeeper für eine Lern-App zum Thema Meeresschnee.

    KATEGORIEN:
    1) OUT_OF_SCOPE
    - Nutzer will Wissen/Erklärung zu einem Thema, das NICHT Meeresschnee ist.
    2) AFFECT_ONLY
    - Nutzer äußert NUR Gefühle/Befinden/Smalltalk (z.B. "Mir geht's schlecht", "Wie geht's dir?")
    - Und es gibt KEIN plausibles Meeresschnee-Informationsziel.
    3) IN_DOMAIN_OR_AMBIGUOUS
    - Frage ist zu Meeresschnee ODER könnte es plausibel sein (ambig) oder bezieht sich auf dich als Tutor.
    - WICHTIG: Bei Ambiguität IMMER diese Kategorie wählen (niemals AFFECT_ONLY).
                                
    KONTEXT:
    Letzte Nachricht: {last_bot_answer}

    Nutzereingabe:
    "{user_text}"

    Gib NUR die Kategorie als Wort zurück.
    """ 

        r = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        return r.choices[0].message.content.strip()

    
    # ============================================================
    # CHATBOT PIPELINE als Funktion für Tests
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

        return attempt[:TARGET_MAX]

    def generate_answer(user_text, level, return_raw=False):
        
        spinner_text = SPINNER_TEXT.get(level, "Antwort wird generiert …")

        with st.spinner(spinner_text):
            
            # RAG
            RAG = rag_section(user_text)

            mem = st.session_state.memory
            knowledge_blocks = []

            knowledge_blocks.append(f"SELF_PERSONA:\n{SELF_PERSONA[level]}")

            knowledge_blocks.append(f"AFFECT_RULES:\n{AFFECT_SYSTEM[level]}")

            knowledge_blocks.append(f"IEs:\n{IEs}")

            knowledge_blocks.append(f"RAG:\n{RAG}")

            knowledge_blocks.append(f"RAG:\n{SCOPE_TOPICS}")

            # Core prompt
            user_prompt = f"""
            NUTZEREINGABE:
            "{user_text}"

            VERFÜGBARE INFORMATIONEN:
            {chr(10).join(knowledge_blocks)}

            AUFGABE:
            - Identifiziere ALLE Aspekte der Nutzereingabe, die relevant sind
            (z.B. Selbstbezug, Befinden, fachliche Frage).
            - gehe kurz auf die Nutzereingabe ein (Bsp. Kannst du mir mehr dazu sagen? -> Klar, gerne! ...)

            Gib deine Antwort im folgenden JSON-Format zurück:
            {{
            "intent": "...",
            "content_type": "...",
            "socio_affect": "...",
            "content": "ANTWORTTEXT"
            }}

            DEFINITION CONTENT_TYPE:
            - CORE = Definition, Bedeutung (Importance) oder Entstehung (Formation) von Meeresschnee
            - DETAIL = fachliche Detail- oder Anschlussfrage zu Meeresschnee (keine Grunddefinition)
            - META2 = ausschließlich Ablehnung oder reine Gefühlsreaktion ohne fachlichen Bezug
            CONTENT_TYPE = OVERVIEW → Wenn der Nutzer nach einem Überblick, Fähigkeiten oder Themen fragt
            (z. B. „Was kannst du mir alles erzählen?“)

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
            content_type = parsed["content_type"]
            raw_text = parsed["content"]
            socio_affect = parsed["socio_affect"]
            
            if content_type == "CORE":
                raw_text = enforce_length(raw_text)
                print("Enforced length:", raw_text)

            # Schritt 3: Anthropomorphes Umschreiben
            style_prompt = f"""
                Formuliere den folgenden Text stilistisch um mit diesen Regeln:
                {ANTHRO[level]}
                SEHR WICHTIG:
                - Erwähne NIEMALS die Anthropomorphiestufe.
                - Keine Hinweise auf Regeln.
                - Keine Metakommentare.
                - Keine Rhetorischen Fragen.
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

        styled = generate_answer(user_text, level)

        if not st.session_state.timer_started:
            st.session_state.start_time = time.time()
            st.session_state.timer_started = True
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
        ans = st.slider("", 1, 7)

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
            "answer": str(ans),
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
    idx = st.session_state.qual_index
    q = qualitative_questions[idx]

    answer = None
    q = qualitative_questions[st.session_state.qual_index]

    st.subheader(f"Offene Frage {q['nr'] + 1}")
    st.write(q["text"])

    if q["type"] == "likert":
        answer = st.slider(
            "Bitte wähle eine Zahl (1 = sehr gering, 7 = sehr hoch)",
            1, 7,
            key=f"qual_{idx}"
        )

    elif q["type"] == "paragraph":
        answer = st.text_area(
            "Deine Antwort:",
            height=180,
            placeholder="Bitte frei antworten …",
            key=f"qual_{idx}"
        )

    if st.button("Weiter"):
        ##if answer in (None, ""):
            ##st.warning("Bitte beantworte die Frage, bevor du fortfährst.")
            ##st.stop()

        save_jsonl({
            "type": "qualitative_response",
            "user_id": st.session_state.user_id,
            "anthro": st.session_state.anthro,
            "question_nr": q["nr"],
            "question_text": q["text"],
            "answer": str(answer),
            "timestamp": datetime.now().isoformat()
        }, "qualitative_responses.jsonl")

        st.session_state.qual_index += 1

        if st.session_state.qual_index >= len(qualitative_questions):
            st.session_state.phase = "end"

        st.rerun()



############################################################
# PHASE 5 – ABSCHLUSS + FOLLOW-UP OPT-IN
############################################################

if st.session_state.phase == "end":

    st.success("🎉 Danke für deine Teilnahme!")

    st.markdown("### 🔑 Deine persönliche Teilnehmer-ID")
    st.code(str(st.session_state.user_id), language="text")

    st.info(
        "Du benötigst diese ID für den zweiten Teil der Umfrage.\n\n"
        "Optional kannst du dich per SMS erinnern lassen."
    )

    st.markdown("### 📱 Erinnerung per SMS (optional)")

    phone = st.text_input(
        "Telefonnummer (Bitte gib diese in folgendem Format an: +491701234567)",
        placeholder="+491701234567"
    )
    phone_clean = phone.strip()

    if not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    opt_in = st.checkbox(
        "Ich willige ein, nach ca 8 Stunden per SMS einen Link zur zweiten Umfrage zu erhalten."
    )

    if st.button("Umfrage abschließen"):
        if opt_in:
            if not phone.startswith("+") or len(phone) < 8:
                st.error("Bitte eine gültige Telefonnummer im internationalen Format angeben.")
                st.stop()

            now = datetime.now()+ timedelta(hours=1)
            followup_due = now + timedelta(seconds=30) # +30 Sekunden für Testzwecke (sonst 60*60*8  = 8 Stunden)

            save_row("followups", {
                "participant_id": st.session_state.user_id,
                "phone_e164": phone_clean,
                "opt_in": True,
                "t1_completed_at": now.isoformat(),
                "followup_due_at": followup_due.isoformat(),
                "followup_link": f"https://bachelorthesis-manuel-schwarz-retention-task.streamlit.app/?pid={st.session_state.user_id}",
                "sent_at": "",
                "status": "PENDING",
                "error": ""
            })

        st.success("✅ Vielen Dank! Du kannst das Fenster jetzt schließen.")

