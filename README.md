# LangChain 🤝 Streamlit agent

## Chatbot Agent for SQL Database Interaction

This repository contains the code for a chatbot agent that interacts with a SQL database containing sales data from a Superstore data set. The chatbot is capable of answering questions and generating SQL queries based on user inputs. The chatbot has two distinct versions (treatments) based on the provision of explanations:

1. Automatic Explanation Version: The chatbot automatically provides an explanation alongside its answer.
2. User-Invoked Explanation Version: The explanation is only displayed when the user voluntarily clicks a button to expand the explanation.

## Features

- The chatbot interacts with a SQLite database that contains interaction data, which includes user queries and chatbot responses.
- Explanations for the chatbot's answers can either be provided automatically or via a button.
- The content of the explanations is the same in both versions; only the method of provision differs.

## Setup and Usage

1. Prerequisites

- Python 3.x
- OpenAI API Key

2. Environment Variables
   The project uses the following environment variables:

- OPENAI_API_KEY: Your OpenAI API key to enable interaction with GPT models.

Make sure to set these in a .env file or directly in your environment.

3. Installation

```shell
# Install the required packages
$ pip install -r requirements.txt ## Ist heruntergeladen
```

4. Running

- Run the Streamlit application:

```shell
# Install the required packages
$ streamlit run streamlit_agent/data_assistant_thesis_prototype.py
#-> funktioniert bei mir nicht anstatt dem, das hier hernehmen:
$ python -m streamlit run streamlit_agent/data_assistant_thesis_prototype.py

$ pip install chromadb rapidfuzz
```
