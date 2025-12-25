# Marine Snow Learning Assistant

## Chatbot Agent with different Anthropomorphic Levels

This repository contains the implementation of an experimental LLM-based learning assistant developed in the context of a bachelor’s thesis.
The system is designed to investigate the effects of anthropomorphic language on learning outcomes and user perception in an educational chatbot.

The prototype focuses on the topic marine snow and combines a controlled dialogue system, a retrieval-augmented generation (RAG) pipeline, and a multi-phase study design including learning, immediate assessment, and delayed retention measurement.

## Core Concept

The system implements three controlled chatbot variants that differ only in their degree of anthropomorphic language:

-Level 0: Neutral, mechanical, non-personal language
-Level 1: Light warmth, limited personal pronouns and emojis
-Level 2: Strongly anthropomorphic, conversational, emotionally expressive

Participants are randomly assigned to one of these conditions.
All variants share the same knowledge base, logic, and response structure to ensure experimental control.

## Setup and Installation

1. Prerequisites

- Python 3.10–3.12
- OpenAI API key
- Google Service Account credentials (for Sheets access)
- Twilio account (optional, for SMS reminders)

2. Environment Variables
   The project uses the following environment variables:

- OPENAI_API_KEY: Your OpenAI API key to enable interaction with GPT models.

Make sure to set these in a .env file or directly in your environment.

3. Installation

```shell
# Install the required packages
$ pip install -r requirements.txt
```

# Additional dependencies

```shell
# Install the required packages
$ pip install chromadb rapidfuzz pdfplumber gspread
```

4. Running

- Run the Streamlit application:

```shell
# Running the first Survey
$ python -m streamlit run streamlit_agent/survey_v2.py

#Running the second Survey
$ python -m streamlit run streamlit_agent/survey_retention_task_v0.py

#Running the Test Framework
$ python -m streamlit run streamlit_agent/chatbot_v2.py
```

# Overview over used Technologies

- Streamlit – Web-based frontend and study orchestration
- OpenAI API – Language models for controlled response generation
- ChromaDB – Vector database for retrieval-augmented generation
- pdfplumber – Extraction and preprocessing of scientific PDF content
- Google Sheets API – Persistent cloud-based data storage
- Twilio API – Automated SMS reminders for delayed follow-up

The system is deployed using the Streamlit Community Cloud, providing:

- public web access
- reproducible execution environment
- secure handling of API keys via secrets
- version-controlled deployment via GitHub

The Weblinks for the application are:

- https://bachelorthesis-manuel-schwarz-survey-v1.streamlit.app/ ( first survey )
- https://bachelorthesis-manuel-schwarz-retention-task.streamlit.app/ ( second survey )
