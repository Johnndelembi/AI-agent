# Debugger Rule: AI Agent (revamp-openai)

name: AI Agent (revamp-openai)

when:
  files:
    - basic_chatbot.py
    - streamlit_app.py
  branches:
    - revamp-openai

start:
  - label: Run Streamlit UI
    command: bash -lc "python3 -m pip install -r requirements.txt && streamlit run streamlit_app.py"
    cwd: .
    long: true
  - label: Run CLI chatbot
    command: bash -lc "python3 -m pip install -r requirements.txt && python3 basic_chatbot.py"
    cwd: .
    long: true

attach:
  - when: process == 'streamlit'
    type: web
    url: http://localhost:8501

breakpoints:
  - file: basic_chatbot.py
    line: 3312
    condition: "True"

notes:
  - Ensure .env contains CHATBOT_MODEL and CHATBOT_API_KEY
  - If PIL or kokoro missing, pip install pillow kokoro soundfile torch
  - For tests: python3 test_basic_chatbot.py
