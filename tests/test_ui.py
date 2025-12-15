# ============================================================
# test_ui.py – Streamlit Oberfläche für Chatbot-Testsystem
# ============================================================

import streamlit as st
import pandas as pd
from test_engine import run_all_tests

st.set_page_config(page_title="Chatbot Testsystem", page_icon="🧪", layout="centered")

st.title("🧪 Automatische Test-Suite für den Marine Snow Chatbot")

st.write("Dieses Interface führt alle Tests automatisch aus und zeigt Score, Details und Coverage.")


if st.button("🔍 Tests ausführen"):
    total, results = run_all_tests()

    st.subheader("📊 Gesamtscore")
    st.metric("Score (max 110)", total)

    st.subheader("📝 Testdetails")

    df = pd.DataFrame(results, columns=["Testname", "Punkte"])
    st.table(df)

    st.subheader("📈 Visualisierung")

    st.bar_chart(df.set_index("Testname"))

    st.success("Tests abgeschlossen!")
else:
    st.info("Klicke auf den Button, um die Tests zu starten.")
