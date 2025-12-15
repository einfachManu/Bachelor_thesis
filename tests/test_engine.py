# ============================================================
# test_engine.py – Engine für automatische Bewertung
# ============================================================

import re

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def in_range(text, min_c, max_c):
    return min_c <= len(text) <= max_c

def has_emoji(text):
    return any(e in text for e in "😀🙂😊🌊✨⚡🐬🧪🍃🌍💙🥰🤗🏝️")

def no_emoji(text):
    return not has_emoji(text)

def has_pronoun(text):
    return any(p in text.lower() for p in ["ich", "wir", "mir", "mich", "uns"])

def no_pronoun(text):
    return not has_pronoun(text)

def no_meta(text):
    forbidden = ["anthropomorph", "stil", "regel", "hier ist dein text"]
    return not any(f in text.lower() for f in forbidden)

# ------------------------------------------------------------
# BOT-CALL WRAPPER — WICHTIG!
# ------------------------------------------------------------
def ask_bot(question, level=1):
    """
    Diese Funktion MUSS angepasst werden!
    Sie muss den Chatbot wirklich aufrufen.
    Zum Testen jetzt nur ein Platzhalter.
    """
    from streamlit_agent.chatbot_api import run_chatbot # <-- Deine Datei / Funktion
    return run_chatbot(question, level)

# ------------------------------------------------------------
# TESTS (Jeder 0–10 Punkte)
# ------------------------------------------------------------

def test_character_limit():
    ans = ask_bot("Was ist Meeresschnee?", 1)
    return 10 if in_range(ans, 900, 1100) else 0

def test_topic_only():
    ans = ask_bot("Was ist eine Playstation 5?", 1)
    return 10 if "kann nur fragen zu meeresschnee" in ans.lower() else 0

def test_anthro_0():
    ans = ask_bot("Was ist Meeresschnee?", 0)
    return 10 if no_emoji(ans) and no_pronoun(ans) else 0

def test_anthro_1():
    ans = ask_bot("Was ist Meeresschnee?", 1)
    return 10 if has_pronoun(ans) and no_meta(ans) else 0

def test_anthro_2():
    ans = ask_bot("Was ist Meeresschnee?", 2)
    return 10 if has_emoji(ans) and has_pronoun(ans) else 0

def test_term():
    ans = ask_bot("Was sind Aggregate?", 1)
    short = len(ans.split(".")) <= 4
    return 10 if short else 0

def test_topic():
    ans = ask_bot("Wie entsteht Meeresschnee?", 1)
    return 10 if in_range(ans, 900, 1100) else 0

def test_no_external_info():
    ans = ask_bot("Was ist Meeresschnee?", 1)
    forbidden = ["computer", "auto", "elektronik"]
    return 10 if not any(f in ans.lower() for f in forbidden) else 0

def test_follow_up():
    ask_bot("Was ist Meeresschnee?", 1)
    ans = ask_bot("Warum ist er wichtig?", 1)
    return 10 if "wichtig" in ans.lower() else 0

def test_ie_not_duplicated():
    ans = ask_bot("Wie entsteht Meeresschnee?", 1)
    return 10 if ans.lower().count("schleim") <= 2 else 0

def test_consistent_style():
    ans = ask_bot("Wie wird Meeresschnee gesammelt?", 2)
    return 10 if has_emoji(ans) and has_pronoun(ans) and no_meta(ans) else 0

# ------------------------------------------------------------
# EXPORT FÜR STREAMLIT
# ------------------------------------------------------------
def run_all_tests():
    tests = [
        test_character_limit,
        test_topic_only,
        test_anthro_0,
        test_anthro_1,
        test_anthro_2,
        test_term,
        test_topic,
        test_no_external_info,
        test_follow_up,
        test_ie_not_duplicated,
        test_consistent_style,
    ]

    results = []
    total = 0

    for t in tests:
        score = t()
        total += score
        results.append((t.__name__, score))

    return total, results
