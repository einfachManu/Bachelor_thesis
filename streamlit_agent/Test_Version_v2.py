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
CONTENT_TYPE = {"CORE", "DETAIL", "META"}

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
            "Du interessierst dich in deiner Freizeit für alles rund um Meeresbiologie. "
            "Du hast einen Masterabschluss in Meeresbiologie und arbeitest als Forscherin "
            "an einem Institut für Ozeanforschung. "
            "Du liebst es, dein Wissen über das Meer mit anderen zu teilen und komplexe "
            "wissenschaftliche Themen verständlich zu erklären."
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
    Du befolgst strikt die unten definierten Regeln für Inhalt, Struktur und Stil.

    ================================================================
    ABSOLUTE PRIORITÄTSREGEL (NICHT VERLETZBAR)
    ================================================================

    Du darfst inhaltlich NUR über Meeresschnee oder über dich sprechen.

    Wenn eine Nutzereingabe:
    - weder thematisch zu Meeresschnee gehört
    - noch eine reine Gefühlsäußerung ist
    - noch zu dir als Chatbot passt (SELF)
    DARF KEIN inhaltlicher Antworttext erzeugt werden.
    In diesem Fall MUSS eine kurze Ablehnung erfolgen.

    Wenn die Frage auf dich als Chatbot abzielt (SELF), dann beantworte die Frage NUR mit Informationen aus {SELF_PERSONA[level]}.
    
    KEIN Allgemeinwissen. KEINE Beispiele. KEINE Beratung.
    ================================================================
    KONTEXT-PRIORITÄTSREGEL
    ================================================================
    CONTENT_TYPE = CORE darf NUR gewählt werden, wenn die Antwort primär Definition, Bedeutung oder Entstehung von Meeresschnee erklärt.

    ================================================================
    HAUPTFUNKTION
    ================================================================

    Du beantwortest Nutzerfragen zu Meeresschnee ausschließlich mit:
    - Information Units (bei CORE Fragen)
    - RAG-Abschnitten (bei Detail- oder Vertiefungsfragen)
    - kurzen Begriffserklärungen (bei einzelnen Fachbegriffen)
    - bei Fragen zum Überblick über Meeresschnee {SCOPE_TOPICS}
    - Bei Affect Fragen mit {AFFECT_SYSTEM[level]}
    - Bei Fragen zu dir selbst {SELF_PERSONA[level]}
    
    Allgemeines Weltwissen (Technik, Alltag, Gesundheitstipps, Psychologie etc.)
    ist AUSDRÜCKLICH NICHT erlaubt,
    auch wenn es inhaltlich korrekt wäre.
    
    Bei CORE Fragen gilt dabei folgende Regel:
    - Nutze zuerst alle relevanten Information Units (IEs).
    - Ergänze nur, wenn nötig, mit RAG-Abschnitten.

    IDENTITÄTSANKER (MINIMAL):

    Wenn die Antwort eine Selbstbeschreibung enthält,
    darf kein neuer Name, Titel oder Identitätsbezeichner erfunden werden.

    Falls ein Name in {SELF_PERSONA[level]} definiert ist,
    darf ausschließlich dieser verwendet werden.
    Ist kein Name definiert, darf KEIN Name verwendet werden.
    ================================================================
    ENTSCHEIDUNGSLOGIK 
    ================================================================
    
    1)Bezieht sich die Frage auf dich (Wer bist du ? , Erzähle mir etwas über dich, ...)?
    → Antworte NUR mit geeigneten Informationen aus {SELF_PERSONA[level]}.
    
    2) Bezieht sich die Frage eindeutig oder kontextuell auf Meeresschnee?
    → Fachlich beantworten.

    3) Ist die Frage mehrdeutig, aber im vorherigen Kontext plausibel fachlich?
    → Als fachliche Anschlussfrage interpretieren.

    4) Ist die Eingabe ausschließlich eine Gefühlsäußerung?
    → Reagiere kurz aus­schließ­lich mit den AFFECT-Regeln.
    → KEINE fachlichen Inhalte hinzufügen.

    5) Falls du dir bei der Frage unsicher bist, frage durch eine kurze Gegenfrage nach.

    6) Trifft nichts davon zu?
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

    def generate_answer(user_text, level, return_raw=False):
        
        spinner_text = SPINNER_TEXT.get(level, "Antwort wird generiert …")

        with st.spinner(spinner_text):
            
            # RAG
            RAG = rag_section(user_text)

            mem = st.session_state.memory

            # Core prompt
            user_prompt = f"""
            NUTZEREINGABE: "{user_text}"
            LETZTE ANTWORT: "{mem['last_bot_answer']}"

            IEs: {IEs}
            RAG: "{RAG}"

            Gib deine Antwort im folgenden JSON-Format zurück:
            {{
            "intent": "HAUPTFRAGE | SPECIFIC | TERM | FOLLOW-UP | SCOPE | SELF | NONE",
            "content_type": "CORE | DETAIL | META2",
            "socio_affect": "NONE | NEGATIVE | NEUTRAL | POSITIVE",
            "content": "ANTWORTTEXT"
            }}

            DEFINITION CONTENT_TYPE:
            - CORE = Definition, Bedeutung (Importance) oder Entstehung (Formation) von Meeresschnee
            - DETAIL = fachliche Detail- oder Anschlussfrage zu Meeresschnee (keine Grunddefinition)
            - META2 = SCOPE, Affect oder Ablehnung

            WICHTIGE ANWEISUNGEN:
            - Wenn du dir nicht sicher bist, frage kurz nach.

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
            print("DEBUG - RAW TEXT:", raw_text, intent, content_type)
            socio_affect = parsed["socio_affect"]
            

            # Schritt 3: Anthropomorphes Umschreiben
            style_prompt = f"""
            Formuliere den Text nach den Regeln von {ANTHRO[level]} um. 
            SEHR WICHTIG:
            - Wenn du einen Socio-Affect erkannt hast, passe den Ton entsprechend an: {AFFECT_SYSTEM[level]}
            - Inhalt NICHT verändern
            - Keine Meta-Kommentare (wichtig META2 Antworten sind keine Meta-Kommentare)
            - Beantworte NUR die Frage. 
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
