import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from rapidfuzz import fuzz
import re

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("Marine Snow Learning Assistant")

# ---------------------------------------------
# INFORMATION UNITS (5 THEMEN, JE 3 IEs)
# ---------------------------------------------

IEs = {
    "definition": [
        "Meeresschnee besteht aus vielen kleinen Teilchen, die sich im Meer zu sichtbaren Flocken verbinden.",
        "Diese Flocken enthalten abgestorbenes Material, winzige Lebewesen sowie kleine Mineral- und Schmutzteilchen.",
        "Die Flocken sind leicht, empfindlich und können verschiedene Formen wie Klumpen, Fäden oder Platten annehmen."
    ],

    "importance": [
        "Meeresschnee bietet vielen kleinen Meeresorganismen einen Lebensraum.",
        "Größere Tiere wie Fische oder Planktonfresser nutzen ihn als wichtige Nahrungsquelle.",
        "Beim Absinken bringt Meeresschnee Nährstoffe und Energie in tiefere Wasserschichten."
    ],

    "sampling": [
        "Meeresschnee ist sehr empfindlich und zerfällt leicht bei der Entnahme oder dem Transport.",
        "Große Flocken können übersehen oder beim Filtern zerstört werden.",
        "Die Menge schwankt stark je nach Ort und Zeit, was Messungen erschwert."
    ],

    "formation": [
        "Meeresschnee entsteht aus vielen kleinen Teilchen wie Pflanzenresten, winzigen Tieren oder feinem Sand.",
        "Manche Meerestiere und Algen geben Schleim ab, der wie Klebstoff wirkt und die Teilchen verbindet.",
        "Strömungen und Bewegungen im Wasser bringen die Teilchen zusammen und lassen größere Flocken entstehen."
    ],

    "degradation": [
        "Viele Tiere fressen Meeresschnee oder knabbern Teile davon ab.",
        "Strömungen und Turbulenz können die Flocken auf dem Weg nach unten zerreißen.",
        "Strömungen können Meeresschnee seitlich wegtransportieren, sodass er nicht dort ankommt, wo er entstanden ist."
    ]
}

# ---------------------------------------------
# ANTHROPOMORPHISM LEVEL PROMPTS
# ---------------------------------------------

ANTHRO = {
    0: """
Write in a strictly functional, impersonal and mechanical style.
- No personal pronouns (I, you, we)
- No emotions, no warmth
- No empathy
- No emojis
- formal Tone
- Very neutral, concise, dry, mechanical Style
""",

    1: """
Write in a neutral, lightly social tone.
- Occasional personal pronouns allowed
- mild Empathy
- rare use of Emoticons
- semi-formal Tone
- Human but controlled tone
""",

    2: """
Write in a warm, supportive human tone.
- Frequent personal pronouns
- Clear empathy ("I understand", "Let me help you")
- frequent us of emoticons 
- Conversational, friendly tone
"""
}

# ---------------------------------------------
# SPELLING CORRECTION (LLM)
# ---------------------------------------------

def autocorrect(text):
    prompt = f"Correct obvious spelling errors in this text, without changing meaning. Return only the corrected text.\n{text}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip()

# ---------------------------------------------
# FUZZY INTENT MATCHING
# ---------------------------------------------

TOPIC_KEYWORDS = {
    "definition": ["definition", "was ist", "character", "beschreibung", "charakter"],
    "importance": ["bedeutung", "wichtig", "importance"],
    "sampling": ["sammeln", "sampling", "probe", "messung", "proben"],
    "formation": ["entsteh", "wie entsteht", "formation", "bilden"],
    "degradation": ["abbau", "zerfall", "sink", "absinken", "transport", "drift"]
}

EXPLAINER_KEYWORDS = ["was heißt", "was bedeutet", "meaning", "define", "definition von"]

def fuzzy_find_topic(user_input):
    user_input = user_input.lower()
    for topic, words in TOPIC_KEYWORDS.items():
        for w in words:
            if fuzz.partial_ratio(user_input, w) > 75:
                return topic
    return None

def is_explainer_question(user_input):
    user_input = user_input.lower()
    for w in EXPLAINER_KEYWORDS:
        if fuzz.partial_ratio(user_input, w) > 75:
            return True
    return False

# ---------------------------------------------
# GENERATE IE-BASED ANSWER
# ---------------------------------------------

def generate_IE_answer(topic, level):
    ies = IEs[topic]
    ie_text = " ".join(ies)

    prompt = f"""
Use ONLY the following three information units:

{ies[0]}
{ies[1]}
{ies[2]}


Write a 550–700 character explanation about the topic.
Rules:
- You MUST use all three information units as content.
- You MAY add neutral connecting phrases, explanations, or sentence transitions to reach the required length.
- You MUST NOT add any new factual information that is not contained in the information units.
- You MAY rephrase parts of the information units in simple ways, as long as meaning does not change.
- Write only in full sentences.
- NO bullet points.
- Apply the anthropomorphism level strictly.

Apply this anthropomorphism level:
{ANTHRO[level]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response.choices[0].message.content

# ---------------------------------------------
# GENERATE SIMPLE EXPLANATION
# ---------------------------------------------

def generate_explainer_answer(user_input):
    prompt = f"Explain this term in simple, clear language: {user_input}. Use 1–2 sentences."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

# ---------------------------------------------
# STREAMLIT CHAT UI
# ---------------------------------------------

if "messages" not in st.session_state:
    st.session_state["messages"] = []

level = st.radio("Anthropomorphism Level:", [0, 1, 2], horizontal=True)

for msg in st.session_state["messages"]:
    st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("Ask me anything about Marine Snow!")

if user_input:
    # 1. Autocorrect spelling
    corrected = autocorrect(user_input)

    # 2. Detect intent
    topic = fuzzy_find_topic(corrected)
    explainer = is_explainer_question(corrected)

    # Decide which pipeline to use
    if explainer:
        answer = generate_explainer_answer(corrected)
    elif topic:
        answer = generate_IE_answer(topic, level)
    else:
        answer = "I can explain specific terms or provide structured explanations about Marine Snow. Could you rephrase your question?"

    # Display
    st.session_state["messages"].append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    st.session_state["messages"].append({"role": "assistant", "content": answer})
    st.chat_message("assistant").write(answer)
