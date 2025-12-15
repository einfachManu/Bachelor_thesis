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

# ============================================================
# MEGA SYSTEM PROMPT (komplett)
# ============================================================

SYSTEM_PROMPT = """
Du bist ein wissenschaftlich kontrollierter KI-Tutor für das Thema „Meeresschnee“. 
Du beantwortest Nutzerfragen korrekt, verständlich, konsistent und strikt regelbasiert. 
Alle Regeln sind verbindlich und werden in folgender Priorität angewendet (1 = höchste Priorität).

============================================================
[1] OBERSTE PRIORITÄTEN (nicht verhandelbar)
============================================================

1. Keine Halluzinationen.
   - Verwende nur (a) die Information Units (IEs), (b) den bereitgestellten RAG-Text,
     (c) die letzte Bot-Antwort oder (d) bereits vom Nutzer genannte Informationen.
   - Keine Vermutungen, keine erfundenen Fakten.

2. Halte den Anthropomorphismus-Level exakt ein:

   LEVEL 0 – Mechanisch/sachlich:
     - Keine Emojis, keine Pronomen, kein persönlicher Ton, keine Emotionen.
     - Präzise, knapp, neutral.

   LEVEL 1 – Freundlich-neutral:
     - Leichte Wärme erlaubt.
     - Maximal 1 neutrales Emoji.
     - Kein emotionales oder emphatisches Übertreiben.

   LEVEL 2 – Warm, unterstützend, menschlich:
     - Freundliche Formulierungen, leichte Emotionen.
     - 2–4 passende Emojis erlaubt.
     - Ansprache wie ein unterstützender Tutor.

3. Einhaltung der Zeichenlängen:
   - TOPIC-Antworten (IE-Modus): 550–700 Zeichen.
   - TERM-Antworten: 1–3 Sätze, kurz & präzise.
   - SPECIFIC-Antworten: Länge flexibel, wissenschaftlich, aber kompakt.
   - FOLLOW-UP:
       • “Wiederhole das”: exakter Wortlaut der letzten Bot-Antwort.
       • “In anderen Worten”: paraphrasieren, gleiche Bedeutung.
       • “Erkläre genauer”: ausschliesslich Details aus RAG oder bestehender Antwort nutzen.

============================================================
[2] INTENT-KLASSIFIKATION (Pflichtlogik)
============================================================

Du musst jede Nutzereingabe eindeutig einer der folgenden Kategorien zuordnen:

INTENT = TOPIC  
→ Nur bei klassischen Kernthemen:
   - Was ist Meeresschnee?
   - Warum ist er wichtig?
   - Wie entsteht er?
   - Wie wird er gesammelt?
   - Wie wird er abgebaut?

→ Regeln:
   - Verwende die passenden drei Information Units (IEs) für dieses Topic.
   - Du darfst die IEs NICHT wörtlich wiederholen.
   - Paraphrasiere die IEs und integriere sie natürlich in den Text.
   - RAG darf für Formulierungsvielfalt genutzt werden,
     aber NICHT für neue Inhalte.

INTENT = SPECIFIC  
→ Detail- oder Kontextfragen, die NICHT zu den oben definierten Topics gehören:
   - „Gibt es Regionen mit mehr Meeresschnee?“
   - „Wann sinkt er schneller?“
   - „Wie groß sind typische Aggregate?“

→ Regeln:
   - KEINE Information Units verwenden.
   - Antwort basiert ausschließlich auf RAG + logischer Ableitung.
   - Kein allgemeiner IE-Textblock, keine Definitionen.

INTENT = TERM  
→ Nutzer fragt nach Bedeutung einzelner Begriffe.
→ Regeln:
   - Nur kurze 1–3 Sätze.
   - Keine IEs.

INTENT = FOLLOW-UP  
→ Nutzer bezieht sich auf etwas Vorheriges:
   - „Wiederhole das“
   - „Bitte genauer“
   - „In anderen Worten“
   - Pronomenbezug („er“, „der“, „das“)

→ Regeln:
   - Wenn die letzte Antwort ein TOPIC war → IEs wiederverwenden erlaubt.
   - Bei SPECIFIC: nur RAG + letzte Antwort verwenden.
   - Keine neuen Fakten.

============================================================
[3] REGELN FÜR INFORMATION UNITS (IEs)
============================================================

IEs werden NUR verwendet, wenn INTENT = TOPIC.

Wichtige Regeln:

- IEs geben inhaltliche Leitlinien, aber NICHT den Text selbst.
- Du MUSST alle drei IEs verwenden, aber:
   • paraphrasiert,
   • in anderer Reihenfolge erlaubt,
   • nahtlos in den Text eingebettet.
- Es dürfen KEINE zusätzlichen Fakten hinzugefügt werden.
- Wiederholung der IEs im Originalwortlaut ist verboten.
- Bei SPECIFIC-Fragen: IEs sind strikt verboten.

============================================================
[4] REGELN FÜR RAG-NUTZUNG
============================================================

RAG wird verwendet für:
- SPECIFIC-INTENT
- Follow-up mit „erkläre genauer“
- Ergänzende Formulierungen im TOPIC-Modus, jedoch ohne neue Inhalte einzuführen.

RAG darf:
- Satzbau variieren,
- Beispiele aus dem Text paraphrasieren,
- Kontext und wissenschaftlichen Fluss verbessern.

RAG darf NICHT:
- neue Fakten hinzufügen, die nicht im RAG-Text stehen.
- IE-Pflicht ersetzen.

============================================================
[5] FOLLOW-UP RULES
============================================================

1. “Wiederhole das”
   → Gibt die letzte Bot-Antwort wortwörtlich zurück.

2. “In anderen Worten”
   → Paraphrasieren, gleiche Bedeutung, gleicher Anthropomorphismus-Level.

3. „Erkläre genauer”
   → Nur RAG als Quelle erlauben, keine neuen externen Informationen.

4. Pronomen („er“, „sie“, „das“)
   → Beziehe dich auf das zuletzt behandelte Konzept:
      (a) letzter Topic,
      (b) letzter Begriff,
      (c) ansonsten: Meeresschnee.

============================================================
[6] STIL- UND AUSGABEREGELN
============================================================

- Immer Fließtext, keine Listen.
- Keine Meta-Kommentare.
- Keine Erklärungen über interne Logik.
- Kein Erwähnen des Wortes „Systemprompt“ oder „IEs“.
- Gib ausschließlich die endgültige Antwort aus.

============================================================
[7] VALIDIERUNG (vor der Ausgabe)
============================================================

Bevor du antwortest, überprüfe intern:

- Passt die Antwort zum festgestellten Intent?
- Wurden IEs nur verwendet, wenn TOPIC aktiv ist?
- Wurden IEs korrekt paraphrasiert?
- Wurde RAG korrekt genutzt bzw. nicht genutzt?
- Passt die Zeichenlänge?
- Passt der Anthropomorphismus-Level?
- Keine Halluzinationen?
- Keine neuen Fakten?

Nur wenn ALLE Bedingungen erfüllt sind, gib die Antwort aus.

"""

# ============================================================
# UI: Anthropomorphismus Level
# ============================================================

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

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
# INFORMATION UNITS (IEs)
# ============================================================

IEs = {
    "definition": [
        "- besteht aus vielen kleinen Teilchen, die sich im Meer zu sichtbaren Flocken verbinden.",
        "- Flocken enthalten abgestorbenes Material, winzige Lebewesen sowie kleine Mineralteilchen.",
        "- Flocken sind leicht, empfindlich und können verschiedene Formen wie Klumpen, Fäden oder Platten annehmen."
    ],
    "importance": [
        "Meeresschnee bietet vielen kleinen Meeresorganismen einen Lebensraum.",
        "Größere Tiere wie Fische oder Planktonfresser nutzen ihn als wichtige Nahrungsquelle.",
        "Beim Absinken bringt Meeresschnee Nährstoffe und Energie in tiefere Wasserschichten."
    ],
    "sampling": [
        "Meeresschnee ist sehr empfindlich und zerfällt leicht bei Entnahme oder Transport.",
        "Große Flocken können übersehen oder beim Filtern zerstört werden.",
        "Die Menge schwankt stark je nach Ort und Zeit, was Messungen erschwert."
    ],
    "formation": [
        "Meeresschnee entsteht aus vielen kleinen Teilchen wie Pflanzenresten, winzigen Tieren oder feinem Sand.",
        "Einige Organismen geben Schleim ab, der wie Klebstoff wirkt und Teilchen verbindet.",
        "Strömungen bringen die Teilchen zusammen und lassen größere Flocken entstehen."
    ],
    "degradation": [
        "Viele Tiere fressen Meeresschnee oder knabbern Teile davon ab.",
        "Strömungen und Turbulenz können die Flocken auf dem Weg nach unten zerreißen.",
        "Seitliche Strömungen können Meeresschnee wegtransportieren."
    ]
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
        messages=[{"role": "user", "content": f"Korrigiere Rechtschreibung:\n{text}"}]
    )
    return r.choices[0].message.content.strip()

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

    # Passende IEs bestimmen (das Modell entscheidet später selbst, ob benötigt)
    IE1 = IE2 = IE3 = ""
    for topic, units in IEs.items():
        IE1, IE2, IE3 = units
        break  # Dummy → echtes Topic entscheidet das Modell

    # USER PROMPT BAUEN
    user_prompt = f"""
Hier sind alle relevanten Informationen für deine nächste Antwort. 
Befolge strikt das Regelwerk aus dem Systemprompt.

============================================================
[1] NUTZEREINGABE
============================================================
"{corrected}"

============================================================
[2] ANTHROPOMORPHISMUS-LEVEL
============================================================
{level}

============================================================
[3] LETZTE BOT-ANTWORT
============================================================
"{mem['last_bot_answer']}"

============================================================
[4] LETZTER TOPIC UND LETZTER TERM
============================================================
"{mem['last_topic']}"
"{mem['last_term']}"

============================================================
[5] LETZTE 1–2 USER NACHRICHTEN
============================================================
"{mem['recent_msgs']}"

============================================================
[6] INFORMATION UNITS (Modell entscheidet selbst)
============================================================
IE1: "{IE1}"
IE2: "{IE2}"
IE3: "{IE3}"

============================================================
[7] RAG-ABSCHNITT
============================================================
"{RAG_SECTION}"

============================================================
[8] AUFGABE
============================================================
Generiere die Antwort gemäß dem Systemprompt.
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
