import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
from rapidfuzz import fuzz
import chromadb
import pdfplumber
import uuid

# ============================================================
# ENV + OPENAI CLIENT
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# GPT model routing
MODEL_IE = "gpt-4.1"
MODEL_INTENT = "gpt-4.1-mini"
MODEL_SPELLING = "gpt-4o-mini"

# ============================================================
# STREAMLIT UI SETUP
# ============================================================

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("🌊 Marine Snow Learning Assistant – RAG + IE + Anthropomorphism Chatbot")
# ============================================================
# AVATARS + GREETING (corrected & ordered)
# ============================================================

AVATARS = {
    0: "🟧",   # mechanical assistant
    1: "🧑🏻",   # neutral emoji avatar
    2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
}

GREETING = {
    0: "Hallo. Ich beantworte Fragen rund um Meeresschnee in einem sachlichen, klaren Stil.",
    1: "Hallo. Ich unterstütze dich bei Fragen rund um das Thema Meeresschnee und liefere dir klare, präzise Informationen.",
    2: "Hi, ich bin Milly, deine persönliche Expertin für Meeresschnee. Frag mich jederzeit und ich helfe dir gern weiter!"
}

# ============================================================
# SELECT ANTHRO LEVEL
# ============================================================

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)
assistant_avatar = AVATARS[level]

# ============================================================
# SHOW GREETING ONLY ONCE
# ============================================================

if "welcome_shown" not in st.session_state:
    with st.chat_message("assistant", avatar=assistant_avatar):
        st.write(GREETING[level])
    st.session_state["welcome_shown"] = True


# ============================================================
# INFORMATION UNITS (3 per topic)
# ============================================================

IEs = {
    "definition": [
        "Meeresschnee beschreibt die Zusammensetzung vielen kleinen Teilchen, die sich im Meer zu sichtbaren Flocken verbinden.",
        "Diese Flocken enthalten abgestorbenes Material, winzige Lebewesen sowie kleine Mineralteilchen.",
        "Die Flocken sind leicht, empfindlich und können verschiedene Formen wie Klumpen, Fäden oder Platten annehmen."
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
# ANTHROPOMORPHISM LEVEL INSTRUCTIONS
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
- Personal pronouns allowed
- Emotional expressions
- emojis allowed
- converstional, engaging tone
"""
}


# ============================================================
# RAG SETUP — Persistent ChromaDB
# ============================================================

PDF_PATH = "Characteristics_Dynamics_and_Significance_of_Marine_Snow.pdf"

def load_chroma():
    client = chromadb.PersistentClient(path="./chroma_marine_snow")

    # check if collection already exists
    existing = [c.name for c in client.list_collections()]
    if "marine_snow" in existing:
        return client.get_collection("marine_snow")

    # otherwise create
    col = client.create_collection("marine_snow")

    # load PDF
    with pdfplumber.open(PDF_PATH) as pdf:
        docs, ids, meta = [], [], []

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            paragraphs = text.split("\n")
            for para in paragraphs:
                if len(para.strip()) < 50:
                    continue

                doc_id = str(uuid.uuid4())
                docs.append(para.strip())
                ids.append(doc_id)
                meta.append({"page": page_num + 1})

        col.add(documents=docs, ids=ids, metadatas=meta)

    return col

collection = load_chroma()

def rag_query(query):
    result = collection.query(query_texts=[query], n_results=4)
    return "\n".join(result["documents"][0])

# ============================================================
# AUTOCORRECT
# ============================================================

def autocorrect(text):
    prompt = f"""
Correct obvious spelling mistakes without changing meaning.
Return only the corrected text.

{text}
"""
    r = client.chat.completions.create(
        model=MODEL_SPELLING,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

# ============================================================
# OFF-TOPIC GATEKEEPER
# ============================================================

def is_marine_snow_related(user_input):
    prompt = f"""
Determine if the following user question is related to Marine Snow 
or ocean biology topics such as aggregates, particles, formation, sampling, sinking, degradation.

If related → return: YES  
If not related → return: NO

Question: "{user_input}"
"""

    r = client.chat.completions.create(
        model=MODEL_INTENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

# ============================================================
# INTENT CLASSIFIER (TOPIC vs TERM)
# ============================================================
GENERIC_TERMS = [
    "aggregat", "aggregation", "turbulenz", "strömung",
    "organismus", "partikel", "sediment", "kohlenstoff"
]

TOPIC_TERMS = {
    "formation": ["bildung", "entstehung", "formation"],
    "sampling":  ["messung", "probe", "sampling"],
    "importance": ["bedeutung", "relevanz", "wichtigkeit"],
    "degradation": ["zerfall", "abbau", "degradation"],
    "definition": ["definition", "beschreibung"]
}

def detect_term(user_input, threshold=82):
    txt = user_input.lower()

    # Check if it's likely a single-word meaning question
    if len(txt.split()) <= 2:
        return "GENERIC_TERM"

    # Check generic terms
    for term in GENERIC_TERMS:
        if fuzz.partial_ratio(txt, term) >= threshold:
            return "GENERIC_TERM"

    # Check topic-related terms
    for topic, tlist in TOPIC_TERMS.items():
        for t in tlist:
            if fuzz.partial_ratio(txt, t) >= threshold:
                return topic  # return which topic it belongs to

    return None


def classify_intent(user_input):
    txt = user_input.lower().strip()

    # ============================================================
    # STEP 1: TERM DETECTION (FUZZY)
    # ============================================================

    term_result = detect_term(txt)

    # Grundtendenz setzen
    if term_result is None:
        heuristic_vote = "TOPIC_INTENT"
    elif term_result == "GENERIC_TERM":
        heuristic_vote = "TERM_INTENT"
    else:
        # term_result entspricht einem Topic -> TOPIC_INTENT
        heuristic_vote = "TOPIC_INTENT"

    # Sonderregel: Meeresschnee -> immer TOPIC_INTENT
    if "meeresschnee" in txt:
        heuristic_vote = "TOPIC_INTENT"

    # ============================================================
    # STEP 2: LLM VOTE 1
    # ============================================================

    prompt1 = f"""
Klassifiziere diese Frage streng in TERM_INTENT oder TOPIC_INTENT.

TERM_INTENT = Bedeutung eines einzelnen Wortes.
TOPIC_INTENT = Frage zu einem wissenschaftlichen Konzept, Prozess oder Zusammenhang.

Sonderregel: Meeresschnee -> immer TOPIC_INTENT.

Frage: "{user_input}"

Gib NUR TERM_INTENT oder TOPIC_INTENT zurück.
"""

    vote1 = client.chat.completions.create(
        model=MODEL_INTENT,
        temperature=0,
        messages=[{"role": "user", "content": prompt1}]
    ).choices[0].message.content.strip().upper()

    # ============================================================
    # STEP 3: LLM VOTE 2 (kontrastiv)
    # ============================================================

    prompt2 = f"""
Wiederhole die Klassifikation.

TERM_INTENT = Bedeutung eines Einzelbegriffs.
TOPIC_INTENT = Erklärung eines Themenfelds.

Sonderregel: Meeresschnee -> TOPIC_INTENT.

Frage: "{user_input}"

Gib NUR das Label zurück.
"""

    vote2 = client.chat.completions.create(
        model=MODEL_INTENT,
        temperature=0,
        messages=[{"role": "user", "content": prompt2}]
    ).choices[0].message.content.strip().upper()

    # ============================================================
    # STEP 4: MAJORITY VOTE (3 Stimmen)
    # ============================================================

    votes = [heuristic_vote, vote1, vote2]
    votes = [v.upper().strip() for v in votes]

    if votes.count("TOPIC_INTENT") > votes.count("TERM_INTENT"):
        return "TOPIC_INTENT"
    else:
        return "TERM_INTENT"



# ============================================================
# TOPIC CLASS MAPPING
# ============================================================

TOPIC_KEYWORDS = ["definition", "importance", "sampling", "formation", "degradation"]

def classify_topic(user_input):
    prompt = f"""
Du bist ein strenger wissenschaftlicher Klassifizierer.

Ordne die folgende Frage GENAU EINER der fünf Kategorien zu:

1. definition     = Was ist Meeresschnee? Woraus besteht er? Was beschreibt er?
2. importance     = Warum ist Meeresschnee wichtig? Welche Rolle spielt er?
3. sampling       = Wie wird Meeresschnee gesammelt, gemessen oder beobachtet?
4. formation      = Wie entsteht Meeresschnee? Welche Prozesse führen zu seiner Bildung?
5. degradation    = Wie zerfällt, sinkt oder verschwindet Meeresschnee?

REGELN:
- Gib **nur das reine Label** zurück: definition / importance / sampling / formation / degradation
- Keine zusätzlichen Wörter, keine Begründung.

Frage:
\"{user_input}\"
"""

    r = client.chat.completions.create(
        model=MODEL_INTENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return r.choices[0].message.content.strip().lower()
def fuzzy_topic(user_input):
    txt = user_input.lower()
    for topic, keys in TOPIC_KEYWORDS.items():
        for k in keys:
            if fuzz.partial_ratio(txt, k) > 75:
                return topic
    return "definition"

# ============================================================
# IE ANSWER GENERATOR
# ============================================================

def generate_IE_answer(topic, user_query, level):
    ies = IEs[topic]
    rag_text = rag_query(user_query)

    prompt = f"""
Write a 550–700 character explanation.  
You MUST include these three information units exactly once:

IE1: {ies[0]}
IE2: {ies[1]}
IE3: {ies[2]}

Rules:
- You may add connecting neutral sentences.
- No new facts beyond the information units or the paper excerpt.
- Full sentences only.

Paper Excerpt:
{rag_text}

Anthropomorphism Rules:
{ANTHRO[level]}
"""

    r = client.chat.completions.create(
        model=MODEL_IE,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return r.choices[0].message.content

# ============================================================
# WORD EXPLAINER
# ============================================================

def generate_explainer(text):
    r = client.chat.completions.create(
        model=MODEL_INTENT,
        messages=[{"role": "user", "content": f"Explain this word in simple German: {text}"}],
        temperature=0
    )
    return r.choices[0].message.content

# ============================================================
# STREAMLIT CHAT INTERFACE
# ============================================================

if "chat" not in st.session_state:
    st.session_state.chat = []

if "chat" not in st.session_state:
    st.session_state.chat = []
else:
    # Falls noch alte Einträge ohne "avatar" existieren: Session leeren
    if any(not isinstance(m, dict) or "avatar" not in m for m in st.session_state.chat):
        st.session_state.chat = []

# display chat history
for m in st.session_state.chat:
    st.chat_message(m["role"], avatar=m["avatar"]).write(m["content"])

user_text = st.chat_input("Frag mich etwas über Meeresschnee")

if user_text:
    corrected = autocorrect(user_text)

    # log user message
    st.session_state.chat.append({"role": "user", "content": user_text, "avatar": None})
    st.chat_message("user").write(user_text)

    # OFF TOPIC FILTER
    if is_marine_snow_related(corrected) == "NO":
        answer = "Ich kann nur Fragen zu Meeresschnee oder verwandten ozeanbiologischen Themen beantworten."
    else:
        intent = classify_intent(corrected)

        if intent == "TERM_INTENT":
            answer = generate_explainer(corrected)
        else:
            topic = classify_topic(corrected)
            answer = generate_IE_answer(topic, corrected, level)

    st.chat_message("assistant", avatar=assistant_avatar).write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer, "avatar": assistant_avatar})
