import streamlit as st
import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
import pdfplumber
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import random

# ============================================================
# ENV
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_MAIN = "gpt-4.1"
MODEL_SPELL = "gpt-4o-mini"

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="Marine Snow Chatbot", page_icon="🌊")
st.title("🌊 Marine Snow Learning Assistant – RAG + IE + Anthropomorphismus")

level = st.radio("Anthropomorphiestufe:", [0, 1, 2], horizontal=True)

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

AVATARS = {
    0: "🟧",
    1: "🧑🏻",
    2: "https://raw.githubusercontent.com/einfachManu/Bachelor_thesis/main/Anthropomorpic_icon.png"
}

GREETINGS = {
    0: "Hallo. Ich beantworte deine Fragen präzise und sachlich. Bitte stelle zuerst die 5 Hauptfragen zum Thema Meeresschnee.",
    1: "Hallo! Ich unterstütze dich gern bei deinen Fragen. Stelle mir jetzt die 5 Hauptfragen zum Thema Meeresschnee🙂",
    2: "Hey! Ich bin Milly 😊🌊 Frag mich alles, was du wissen möchtest! Leg jetzt los mit deinen 5 Hauptfragen, welche du mir stellen solltest 😊."
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
[2b] ZUORDNUNG DER INFORMATION UNITS (IUs) ZU DEN HAUPTTHEMEN
============================================================

Wenn du INTENT = HAUPTFRAGE gewählt hast, verwendest du ausschließlich die
Information Units der folgenden Kategorien:

1. Definition + Bedeutung von Meeresschnee
   → verwende ausschließlich IEs["definition"] UND IEs["importance"]

2. Sammlung & Untersuchung von Meeresschnee
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

- Stimmen Intent & Regeln überein?
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

    return attempt[:TARGET_MAX]

# ============================================================
# CHATBOT PIPELINE als Funktion für Tests
# ============================================================

def generate_answer(user_text, level, return_raw=False):
    # Rechtschreibung
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


# ============================================================
# TESTING FRAMEWORK – Anthropomorphismus + Inhaltsvalidierung
# ============================================================

KEYWORDS = {
    "definition": ["Aggregat%","Partikel" "Struktur%","größer","500", "zerbrech%", "robust%", "Mikroorganismen", "Tonmineral%", "Form%", "allg%", "kategor%"],
    "importance": ["Transport%", "Nahrung%", "Leben%", "Wohn%"],
    "sampling": ["Tauch%", "Flasch%", "aufbewa%", "Kamera", "Analys%"],
    "sampling_problems": ["holog%", "zerbrech%", "absetz%", "Transpo%", "Messverzerrun%", "Proble%"],
    "formation": ["Ström%", "biol%", "kleb%", "verkleb%", "verbind%" , "stoß%", "zusammen%" ,"sink%", "absink%"],
    "degradation": ["fress%", "Fraß" "zersetz%", "absink%", "verdrift%"]
}

TEST_QUERIES = {
    "definition": [
    "Was ist Meeresschnee?",
    "Erkläre Meeresschnee.",
    "Definiere Meeresschnee.",
    "Beschreibe kurz.",
    "Was versteht man unter Meeresschnee?",
    "Gib eine Definition von Meeresschnee.",
    "Worum handelt es sich bei Meeresschnee?",
    "Was bedeutet der Begriff Meeresschnee?",
    "Was genau ist Meeresschnee?",
    "Kannst du Meeresschnee definieren?"
    ],
    "sampling": [
    "Wie wird Meeresschnee gesammelt?",
    "Wie sampelt man Meeresschnee?",
    "Wie gewinnt man Proben von Meeresschnee?",
    "Wie wird Meeresschnee in der Forschung entnommen?",
    "Wie nimmt man Proben von Meeresschnee?",
    "Wie erfolgt die Probenahme von Meeresschnee?",
    "Wie gelangt man an Meeresschneeproben?",
    "Welche Methoden nutzt man zur Sammlung von Meeresschnee?"
    ],
    "formation": [
    "Wie entsteht Meeresschnee?",
    "Wodurch bildet sich Meeresschnee?",
    "Welche Prozesse führen zu Meeresschnee?",
    "Wie kommt Meeresschnee zustande?",
    "Wie formt sich Meeresschnee?",
    "Wie entsteht das Phänomen Meeresschnee?",
    "Welche Mechanismen erzeugen Meeresschnee?",
    ],
    "importance": [
    "Warum ist Meeresschnee wichtig?",
    "Weshalb ist Meeresschnee von Bedeutung?",
    "Warum braucht man Meeresschnee für das Ökosystem?",
    "Welche Funktion erfüllt Meeresschnee?",
    "Warum spielt Meeresschnee im Meer eine große Rolle?",
    "Wieso ist Meeresschnee ökologisch relevant?",
    "Welche ökologische Rolle übernimmt Meeresschnee?"
    ], 
    "degradation": [
    "Wie zerfällt Meeresschnee?",
    "Wie wird Meeresschnee abgebaut?",
    "Warum verschwindet Meeresschnee?",
    "Welche Prozesse führen zum Zerfall von Meeresschnee?",
    "Warum nimmt die Menge an Meeresschnee ab?"
]
}

# Regeln für Tests
ANTHRO_RULES_TEST = {
    0: {
        "max_emojis": 0,
        "forbidden_pronouns": [" ich ", " wir ", " du ", " mich ", " mir ", " uns ", " dich ", " euch ", " ihr ", " ihrer " , " dein ", " deine ", " mein ", " meine ", " unser ", " unsere ", " euer ", " eure ", " ihre ", " seine "],
    },
    1: {
        "max_emojis": 5,
        "forbidden_pronouns": [],
    },
    2: {
        "max_emojis": 20,
        "forbidden_pronouns": [],
    }
}

def count_emojis(text):
    return sum(bool(re.match(r'[\U0001F300-\U0001FAFF]', c)) for c in text)

def match_keyword(text, pattern):
    regex = pattern.replace("%", ".*")
    return re.search(regex, text, re.IGNORECASE) is not None

def keyword_coverage(text, topic, min_ratio=0.75):
    kw_list = KEYWORDS[topic]
    hits = sum(match_keyword(text, kw) for kw in kw_list)
    ratio = hits / len(kw_list)
    return ratio, ratio >= min_ratio


def contains_forbidden_pronouns(text, pronouns):
    return any(p in text.lower() for p in pronouns)

def run_single_test():
    topic = random.choice(list(TEST_QUERIES.keys()))
    question = random.choice(TEST_QUERIES[topic])
    level = random.choice([0, 1, 2])

    # Antwort über die echte Chatbot-Pipeline
    styled_answer, raw_answer = generate_answer(
    question, level, return_raw=True
)

    length_ok = TARGET_MIN <= len(raw_answer) <= TARGET_MAX

    # Tests
    coverage_ok = keyword_coverage(raw_answer, topic, min_ratio=0.75)

    return {
    "topic": topic,
    "question": question,
    "level": level,
    "raw_length": len(raw_answer),
    "raw_length_ok": length_ok,
    "styled_length": len(styled_answer),
    "emoji_count": count_emojis(styled_answer),
    "keyword_ok": coverage_ok,
    "raw_preview": raw_answer[:300] + "...",
    "styled_preview": styled_answer[:300] + "...",
    }


# Optional: Streamlit Testbutton
if st.button("Automatischen Test ausführen"):
    result = run_single_test()
    st.write(result)
# ============================================================
# BULK TEST (100 Testfälle)
# ============================================================

def run_bulk_test(n=10, min_keyword_ratio=0.75):
    results = []
    failures = 0

    print("\n===== STARTE BULK-TEST =====\n")

    for i in range(1, n + 1):

        topic = random.choice(list(TEST_QUERIES.keys()))
        question = random.choice(TEST_QUERIES[topic])
        level = random.choice([0, 1, 2])

        # ====================================================
        # MODELLAUFRUF (RAW + STYLED)
        # ====================================================
        try:
            styled_answer, raw_answer = generate_answer(
                question, level, return_raw=True
            )
        except Exception as e:
            print(f"[{i}] ❌ Fehler im Modellaufruf: {e}")
            failures += 1
            continue

        # ====================================================
        # TESTS – INHALT (RAW)
        # ====================================================

        raw_length = len(raw_answer)
        raw_length_ok = TARGET_MIN <= raw_length <= TARGET_MAX

        kw_ratio, kw_ok = keyword_coverage(
            raw_answer, topic, min_keyword_ratio
        )

        # ====================================================
        # TESTS – STIL (STYLED)
        # ====================================================

        emoji_count = count_emojis(styled_answer)
        emoji_ok = emoji_count <= ANTHRO_RULES_TEST[level]["max_emojis"]

        pronoun_violation = contains_forbidden_pronouns(
            styled_answer,
            ANTHRO_RULES_TEST[level]["forbidden_pronouns"]
        )
        pronoun_ok = not pronoun_violation

        # ====================================================
        # GESAMTBEWERTUNG
        # ====================================================

        test_ok = all([
            raw_length_ok,
            kw_ok,
            emoji_ok,
            pronoun_ok
        ])

        # ====================================================
        # LOGGING
        # ====================================================

        print(f"[{i}] Topic: {topic}, Level: {level}")
        print(f"     - RAW length: {raw_length} → {'OK' if raw_length_ok else 'FAIL'}")
        print(f"     - keyword coverage: {kw_ratio*100:.1f}% → {'OK' if kw_ok else 'FAIL'}")
        print(f"     - emojis: {emoji_count}/{ANTHRO_RULES_TEST[level]['max_emojis']} → {'OK' if emoji_ok else 'FAIL'}")
        print(f"     - pronouns OK: {pronoun_ok}")
        print(f"     - question: {question}")
        print(f"     - raw Answer: {raw_answer}")
        print(f"     → {'✔ TEST PASSED' if test_ok else '❌ TEST FAILED'}")
        print()

        results.append({
            "topic": topic,
            "level": level,

            # RAW
            "raw_length": raw_length,
            "raw_length_ok": raw_length_ok,
            "keyword_ratio": kw_ratio,
            "keyword_ok": kw_ok,

            # STYLED
            "emoji_count": emoji_count,
            "emoji_ok": emoji_ok,
            "pronoun_ok": pronoun_ok,

            # Gesamt
            "test_ok": test_ok
        })

        if not test_ok:
            failures += 1

    # ====================================================
    # GESAMTSTATISTIK
    # ====================================================

    passed = n - failures
    print("\n===== BULK-TEST FERTIG =====")
    print(f"Gesamt: {n} Testfälle")
    print(f"Bestanden: {passed}")
    print(f"Fehlgeschlagen: {failures}")
    print(f"Erfolgsquote: {passed / n * 100:.2f}%")

    return results

def analyze_results(results):
    df = pd.DataFrame(results)

    print("\n===== ANALYSE: BASISSTATISTIK =====")

    cols = [
        "test_ok",
        "level",
        "topic",
        "raw_length_ok",
        "keyword_ok",
        "emoji_ok",
        "pronoun_ok"
    ]

    print(df[cols].head())

    return df

def plot_heatmap(df):
    df_fail = df[df["test_ok"] == False]

    pivot = df_fail.pivot_table(
        index="level",
        columns="topic",
        aggfunc="size",
        fill_value=0
    )

    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, fmt="d", cmap="Reds")
    plt.title("Fehlerhäufigkeit nach Anthropomorphiestufe und Topic")
    plt.xlabel("Topic")
    plt.ylabel("Anthropomorphiestufe")
    plt.tight_layout()
    plt.show()

def plot_errors_by_level(df):
    df_fail = df[df["test_ok"] == False]

    level_counts = df_fail["level"].value_counts().sort_index()

    plt.figure(figsize=(7, 4))
    level_counts.plot(kind="bar", color="salmon")
    plt.title("Fehler nach Anthropomorphiestufe")
    plt.xlabel("Level")
    plt.ylabel("Fehleranzahl")
    plt.show()

def plot_errors_by_topic(df):
    df_fail = df[df["test_ok"] == False]

    topic_counts = df_fail["topic"].value_counts()

    plt.figure(figsize=(9, 4))
    topic_counts.plot(kind="bar", color="lightblue")
    plt.title("Fehler nach Topic")
    plt.xlabel("Topic")
    plt.ylabel("Fehleranzahl")
    plt.show()

def plot_error_types(df):
    df_fail = df[df["test_ok"] == False]

    counts = {
        "length": (~df_fail["raw_length_ok"]).sum(),
        "emoji": (~df_fail["emoji_ok"]).sum(),
        "pronoun": (~df_fail["pronoun_ok"]).sum(),
        "keyword": (~df_fail["keyword_ok"]).sum()
    }

    plt.figure(figsize=(7, 4))
    plt.bar(counts.keys(), counts.values(), color="orange")
    plt.title("Fehlerhäufigkeit nach Testkategorie")
    plt.xlabel("Kategorie")
    plt.ylabel("Fehleranzahl")
    plt.show()

if st.button("Bulk Test ausführen"):
    results = run_bulk_test()   # hier plural beachten
    df = analyze_results(results)

    # Heatmap
    fig1 = plot_heatmap(df)
    st.pyplot(fig1)

    # Fehler nach Level
    fig2 = plot_errors_by_level(df)
    st.pyplot(fig2)

    # Fehler nach Topic
    fig3 = plot_errors_by_topic(df)
    st.pyplot(fig3)

    # Fehler nach Kategorie
    fig4 = plot_error_types(df)
    st.pyplot(fig4)
