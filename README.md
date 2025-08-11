# AI Research & Study Assistant – Conversational Chatbot

A modern, production-ready conversational AI assistant for content creation, research, and social media management.  
Built with [LangGraph](https://github.com/langchain-ai/langgraph), [LangChain](https://github.com/langchain-ai/langchain), [Streamlit](https://streamlit.io/), and Google Gemini.  
Includes real-time web search (Tavily), web page browsing, and a beautiful chat UI.

---

## Features

- **Conversational AI**: Powered by Google Gemini, OpenAI, or Anthropic (configurable).
- **Modern Chat UI**: Streamlit web app with instant user bubbles and natural assistant responses.
- **Web Search**: Integrates Tavily for up-to-date information.
- **Web Page Browsing**: Reads and summarizes content from any URL.
- **Content Creation**: Generates LinkedIn posts, Twitter threads, and more.
- **Content Scheduling**: Simulate scheduling posts for later.
- **Text-to-Speech (TTS)**: Convert AI responses to audio using Kokoro TTS.
- **Extensible Tools**: Easily add or swap tools and LLMs.
- **Robust Error Handling**: Clean error messages and dev-friendly warnings.
- **Testing**: Includes a comprehensive test suite for all major features.
- **Environment-based Config**: All keys/settings via `.env` file.
- **Startup-Friendly**: Minimal, readable, and easy to extend.

---

## Quick Start

### Option 1: Docker (Recommended)

#### 1. Clone the Repository
```sh
git clone <your-repo-url>
cd AI-agent
```

#### 2. Setup Environment
```sh
# Copy environment template
cp env.template .env

# Edit with your API keys
nano .env  # or use your preferred editor
```

#### 3. Run with Docker Compose
```sh
# Production mode
docker-compose up -d

# Development mode (with live reloading)
docker-compose -f docker-compose.dev.yml up -d
```

#### 4. Access the Application
Open your browser to: http://localhost:8501

📖 **For detailed Docker instructions, see [DOCKER_README.md](DOCKER_README.md)**

### Option 2: Local Development

#### 1. Clone the Repository
```sh
git clone <your-repo-url>
cd AI-agent
```

#### 2. Create and Activate a Virtual Environment
```sh
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

#### 3. Install Dependencies
```sh
pip install -r requirements.txt
```

**If you encounter NumPy compatibility issues:**
```sh
# Run the compatibility fix script
python fix_numpy_compatibility.py

# Or manually install compatible versions
pip install "numpy<2.0" "scipy<2.0" kokoro==0.7.16 soundfile torch
```

#### 4. Configure Environment Variables

Create a `.env` file in the project root:

```
# LLM configuration
CHATBOT_MODEL=openai:gpt-4             # or another supported model
CHATBOT_API_KEY=your-openai-api-key    # OpenAI, Anthropic, or Google API key

# Tavily Search
TAVILY_API_KEY=your-tavily-api-key     # Get from https://app.tavily.com/

# (Optional) LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=basic_chatbot
```

---

## Usage

### **Web App (Recommended)**

Launch the Streamlit chat UI:

```sh
streamlit run streamlit_app.py
```

- Open your browser to the local URL shown (usually http://localhost:8501).
- Type your message and press Enter.
- Your message appears instantly; the assistant’s response appears as soon as it’s ready.

### **Command-Line Chatbot**

```sh
python basic_chatbot.py
```

- Interact with the agent via the terminal.

### **Text-to-Speech (TTS) Features**

The AI assistant can convert responses to audio using multiple TTS engines with voice customization:

- **In Streamlit**: Use the "🔊 Generate Audio Response" or "🎤 Speak Last Response" buttons in the sidebar
- **In Chat**: Ask the AI to "speak this response" or "generate audio for this"
- **Direct Tool**: Use the `generate_audio_response` tool with any text
- **Automatic Playback**: Audio players appear directly in the chat interface

**TTS Engines:**
- **🎭 Kokoro**: High-quality, AI-powered TTS (primary engine)
- **⚡ PyTTSx3**: Fast, system-based TTS with optimized female voice settings (fallback engine)

**Voice Customization:**
- **Female Voice Selection**: Automatically selects high-quality female voices (Samantha, Victoria, Karen, Alice, Fiona)
- **Optimized Settings**: 
  - Speech Rate: 180 WPM (faster, more natural)
  - Volume: 0.95 (clear and audible)
  - Pitch: 1.1 (slightly higher for female-like sound)
- **Voice Configuration Utility**: Use `python voice_config.py` to explore and customize voices

**Performance Optimizations:**
- **Text Length Limiting**: Automatically truncates long responses (500 chars max)
- **Pipeline Caching**: Reuses TTS pipeline for faster subsequent generations
- **Progress Logging**: Shows real-time generation progress
- **Automatic Cleanup**: Keeps only 5 most recent audio files
- **Speed**: PyTTSx3 generates ~400-600 characters/second for typical responses

**Audio File Management:**
- **Single File Per Response**: Each AI response generates one complete audio file
- **Automatic Cleanup**: Only the 5 most recent audio files are kept
- **Unique Naming**: Files are named `response_{timestamp}.wav` (e.g., `response_1703123456.wav`)
- **Storage Location**: Audio files are saved in the `audio_output/` directory
- **Format**: High-quality WAV files at 24kHz sample rate

**TTS Configuration:**
```bash
# In your .env file
TTS_VOICE=af_heart        # Voice type (default: af_heart)
TTS_LANG_CODE=b           # Language code (default: b)
# TTS_PREFER_FAST=true      # Prefer faster TTS engine (default: true) - REMOVED
```

---

## How the Chat UI Works

- **Instant Feedback:** Your message appears in the chat immediately.
- **Natural Flow:** The assistant’s response is generated in the background and appears in its own bubble.
- **No Delays:** No more waiting for both bubbles to appear at once.
- **Classic Chat Experience:** Just like modern messaging apps.

---

## Testing

Run the test suite to verify all features:

```sh
python test_basic_chatbot.py
```

- Tests cover LinkedIn post generation, Twitter threads, scheduling, web browsing, error handling, and end-to-end chat flow.

### TTS Testing

Test the Text-to-Speech functionality:

```sh
python test_tts.py
```

- Verifies TTS audio generation and single file creation
- Tests audio concatenation and file management
- Shows audio file size and approximate duration

**Performance Testing:**
```sh
python test_tts_performance.py
```

- Tests TTS performance with different text lengths
- Compares generation speed and quality
- Shows characters per second processing rate

---

## Project Structure

```
AI-agent/
├── basic_chatbot.py         # Main chatbot logic and tools
├── streamlit_app.py         # Streamlit web app UI
├── test_basic_chatbot.py    # Automated tests for all features
├── test_tts.py             # TTS functionality tests
├── test_tts_performance.py  # TTS performance benchmarking
├── test_voice_speed.py      # Voice speed and quality tests
├── voice_config.py          # Voice configuration utility
├── kokoro_config.py         # Kokoro TTS configuration
├── fix_numpy_compatibility.py # NumPy compatibility fixer
├── requirements.txt         # All dependencies
├── README.md               # This file
├── audio_output/           # Generated audio files (auto-created)
│   ├── response_1703123456.wav
│   ├── response_1703123457.wav
│   └── ... (max 5 files)
├── static/                 # (Optional) Static assets for UI
└── templates/              # (Optional) HTML templates
```

---

## Environment Variables

| Variable            | Description                                         |
|---------------------|-----------------------------------------------------|
| CHATBOT_MODEL       | LLM model string (e.g., `gemini-pro`, `openai:gpt-4.1`) |
| CHATBOT_API_KEY     | API key for the selected LLM provider               |
| TAVILY_API_KEY      | Tavily Search Engine API key                        |
| TTS_VOICE           | TTS voice to use (default: `af_heart`)              |
| TTS_LANG_CODE       | TTS language code (default: `b`)                    |
| LANGSMITH_TRACING   | Set to `true` to enable LangSmith tracing           |
| LANGSMITH_ENDPOINT  | LangSmith API endpoint                              |
| LANGSMITH_API_KEY   | LangSmith API key                                   |
| LANGSMITH_PROJECT   | Project name for LangSmith traces                   |

---

## Extending the Chatbot

- **Add More Tools:** Import and add new tools to the `tools` list in `basic_chatbot.py`.
- **Change LLM Provider:** Update `CHATBOT_MODEL` and `CHATBOT_API_KEY` in `.env`.
- **UI Customization:** Edit `streamlit_app.py` for new features or design tweaks.
- **TTS Customization:** Modify voice settings and audio processing in `basic_chatbot.py`.
- **Testing:** Add or modify tests in `test_basic_chatbot.py` and `test_tts.py`.

---

## TTS Troubleshooting

### **Common Issues:**

**TTS Not Available:**
```bash
# Fix NumPy compatibility issues
python fix_numpy_compatibility.py

# Or install manually with compatible versions
pip install "numpy<2.0" "scipy<2.0" kokoro==0.7.16 soundfile torch
```

**Audio Files Not Playing:**
- Check if `audio_output/` directory exists
- Verify file permissions
- Ensure browser supports WAV playback

**Poor Audio Quality:**
- Adjust `TTS_VOICE` setting in `.env`
- Try different `TTS_LANG_CODE` values
- Check system audio settings

**NumPy Compatibility Issues:**
```bash
# Run the compatibility fix script
python fix_numpy_compatibility.py

# Or manually downgrade NumPy
pip install "numpy<2.0" "scipy<2.0"
```

**Disk Space Issues:**
- Audio files are automatically cleaned up (keeps last 10)
- Manual cleanup: `rm audio_output/*.wav`

### **Advanced TTS Usage:**

**Custom Voice Configuration:**
```python
# In basic_chatbot.py, modify TTS settings
TTS_VOICE = "af_heart"      # Available voices: af_heart, af_angry, etc.
TTS_LANG_CODE = "b"         # Language codes: a, b, c, etc.
```

**Batch Audio Generation:**
```python
from basic_chatbot import generate_tts_audio

# Generate audio for multiple texts
texts = ["Hello world", "How are you?", "Goodbye"]
for text in texts:
    audio_files = generate_tts_audio(text)
    print(f"Generated: {audio_files}")
```

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/docs/)
- [Tavily Search](https://app.tavily.com/)
- [Streamlit](https://streamlit.io/)
- [Google Gemini](https://ai.google.dev/)
- [Kokoro TTS](https://github.com/kokoro-ai/kokoro) - Text-to-Speech engine

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
