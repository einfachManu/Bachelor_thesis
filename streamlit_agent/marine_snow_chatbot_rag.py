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
# AVATARS & GREETINGS
# ============================================================

AVATARS = {
    0: "🟧",   # mechanical assistant
    1: "🙂",   # neutral emoji avatar
    2: "LLM_data_assistant-main/Anthropomorpic_icon.png"   
}

GREETINGS = {
    0: "",
    1: "Hello.",
    2: "Hi! Schön, dass du da bist 😊"
}

# ============================================================
# INFORMATION UNITS (3 per topic)
# ============================================================

IEs = {
    "definition": [
        "Meeresschnee besteht aus vielen kleinen Teilchen, die sich im Meer zu sichtbaren Flocken verbinden.",
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
- Very mechanical tone
""",

    1: """
Anthropomorphism Level 1:
- Light warmth allowed
- Personal pronouns allowed
- No emojis
""",

    2: """
Anthropomorphism Level 2:
- Warm, supportive tone
- Personal pronouns
- Emotional expressions
- 1–3 emojis
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

def classify_intent(user_input):
    prompt = f"""
Classify into:
TOPIC_INTENT → explanation of a Marine Snow topic
TERM_INTENT → meaning of a single word

User question: "{user_input}"

Return only TOPIC_INTENT or TERM_INTENT.
"""
    r = client.chat.completions.create(
        model=MODEL_INTENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

# ============================================================
# TOPIC CLASS MAPPING
# ============================================================

TOPIC_KEYWORDS = {
    "definition": ["was ist", "definier", "meeresschnee"],
    "importance": ["warum wichtig", "bedeutung"],
    "sampling": ["probe", "messung", "sammeln"],
    "formation": ["entsteht", "entstehung", "bildung"],
    "degradation": ["abbau", "zerfall", "sinken", "drift"]
}

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

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

assistant_avatar = AVATARS[level]
assistant_greeting = GREETINGS[level]

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
            topic = fuzzy_topic(corrected)
            answer = generate_IE_answer(topic, corrected, level)

    # show greeting once per answer if level > 0
    if assistant_greeting:
        st.chat_message("assistant", avatar=assistant_avatar).write(assistant_greeting)

    st.chat_message("assistant", avatar=assistant_avatar).write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer, "avatar": assistant_avatar})
