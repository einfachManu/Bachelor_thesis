############################################################
# RETENTION TASK – MARINE SNOW STUDY (GOOGLE SHEETS)
############################################################

import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

############################################################
# GOOGLE SHEETS BACKEND
############################################################

@st.cache_resource
def get_gsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
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

    try:
        ws = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(data.keys()))

    ws.append_row(list(data.values()))

############################################################
# RETENTION QUESTIONS (TAG 2)
############################################################

retention_questions = [
    {
        "nr": 0,
        "type": "likert",
        "text": "Wie gut erinnerst du dich aktuell noch an die Inhalte zum Thema Meeresschnee?(1 = gar nicht, 7 = sehr gut)"
    },
    {
        "nr": 1,
        "type": "single",
        "text": "Was trifft am ehesten auf Meeresschnee zu?",
        "options": [
            "Absinkende Aggregate aus biologischem und nicht-biologischem Material",
            "Eiskristalle, die sich aus Meerwasser bilden",
            "Reine Ansammlungen lebender Mikroorganismen",
            "Ablagerungen, die ausschließlich am Meeresboden vorkommen"
        ]
    },
    {
        "nr": 2,
        "type": "multi",
        "text": "Welche Vorgänge sind an der Bildung von Meeresschnee beteiligt? (2 Antworten auswählen)",
        "options": [
            "Zusammenlagerung kleiner Partikel",
            "Produktion organischen Materials durch Meeresorganismen",
            "Gefrierprozesse im Meerwasser",
            "Ablagerung vulkanischer Asche"
        ]
    },
    {
        "nr": 3,
        "type": "paragraph",
        "text": "Warum ist Meeresschnee wichtig für das Leben im Meer? Nenne zwei Gründe."
    },
    {
        "nr": 4,
        "type": "paragraph",
        "text": "Welche Auswirkungen könnte es auf das marine Ökosystem haben, wenn weniger Meeresschnee in große Tiefen gelangt?"
    },
    {
        "nr": 5,
        "type": "short",
        "text": "Welche Eigenschaft oder Funktion von Meeresschnee ist dir besonders im Gedächtnis geblieben?"
    }
]

############################################################
# SESSION STATE INIT
############################################################

if "phase" not in st.session_state:
    st.session_state.phase = "enter_id"

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "retention_index" not in st.session_state:
    st.session_state.retention_index = 0

############################################################
# PHASE 1 – USER ID EINGEBEN
############################################################

if st.session_state.phase == "enter_id":

    st.title("Retention Task – Teil 2")

    st.write(
        "Bitte gib deine persönliche Teilnehmer-ID ein, "
        "die du am Ende der ersten Umfrage erhalten hast."
    )

    entered_id = st.text_input("Teilnehmer-ID")

    if st.button("Weiter"):
        if entered_id.isdigit():
            st.session_state.user_id = int(entered_id)
            st.session_state.phase = "retention"
            st.rerun()
        else:
            st.error("Bitte gib eine gültige numerische ID ein.")

############################################################
# PHASE 2 – RETENTION UMFRAGE
############################################################

if st.session_state.phase == "retention":

    q = retention_questions[st.session_state.retention_index]

    st.subheader(f"Frage {q['nr'] + 1}")
    st.write(q["text"])

    if q["type"] == "likert":
        answer = st.slider("", 1, 7)

    elif q["type"] == "single":
        answer = st.radio("", q["options"])

    elif q["type"] == "multi":
        answer = st.multiselect("", q["options"])

    elif q["type"] == "short":
        answer = st.text_input("")

    elif q["type"] == "paragraph":
        answer = st.text_area("", height=150)

    if st.button("Weiter"):
        save_row("retention_responses", {
            "type": "retention_response",
            "user_id": st.session_state.user_id,
            "question_nr": q["nr"],
            "question_text": q["text"],
            "answer": str(answer),
            "timestamp": datetime.now().isoformat()
        })

        st.session_state.retention_index += 1

        if st.session_state.retention_index >= len(retention_questions):
            st.session_state.phase = "end"

        st.rerun()

############################################################
# PHASE 3 – ABSCHLUSS
############################################################

if st.session_state.phase == "end":
    st.success("🎉 Vielen Dank für deine Teilnahme am zweiten Teil der Umfrage!")
