# ============================================================
# coverage_report.py
# ============================================================

from test_engine import run_all_tests

def generate_report():
    total, results = run_all_tests()

    report = {
        "gesamt_score": total,
        "ergebnis_details": [
            {"test": name, "punkte": score} for name, score in results
        ],
        "abgedeckte_dimensionen": [
            "Anthropomorphie",
            "Intent-Klassifikation",
            "RAG-Konformität",
            "IE-Regeln",
            "Zeichenlimit",
            "Follow-Up-Mechanismus",
            "Off-Topic-Blockierung",
            "Stil-Konstanz",
        ]
    }

    return report

if __name__ == "__main__":
    rep = generate_report()
    print(rep)
