# AI Agent - FastAPI Conversational AI Assistant

A production-ready conversational AI assistant API built with **FastAPI**, **LangGraph**, **LangChain**, and Google Gemini.  
Features real-time web search (Tavily), web page browsing, text-to-speech (TTS), and a clean REST API architecture.

---

## 🚀 Features

- **RESTful API**: Clean, documented FastAPI endpoints
- **Conversational AI**: Powered by Google Gemini, OpenAI, or Anthropic (configurable)
- **Web Search**: Integrates Tavily for up-to-date information
- **Web Page Browsing**: Reads and summarizes content from any URL
- **Content Creation**: Generates LinkedIn posts, Twitter threads, and more
- **Text-to-Speech (TTS)**: Convert AI responses to audio using Kokoro TTS
- **Modern Architecture**: Clean separation with controllers, services, and models
- **Async Support**: Full async/await support for high performance
- **Auto Documentation**: Interactive API docs at `/docs`
- **Health Checks**: Built-in health monitoring endpoints
- **CORS Support**: Configurable CORS for web clients
- **Thread-based Conversations**: Maintain conversation context across multiple messages

---

## 📁 Project Structure

```
AI-agent/
├── app/
│   ├── controllers/          # API route handlers
│   │   ├── chat.py          # Chat endpoints
│   │   ├── audio.py         # TTS endpoints
│   │   └── health.py        # Health check endpoints
│   ├── services/            # Business logic layer
│   │   ├── chat_service.py  # Conversational AI service
│   │   └── audio_service.py # TTS service
│   ├── models/              # Request/response models
│   │   └── chat.py          # Pydantic models
│   ├── dependencies.py      # FastAPI dependencies
│   └── main.py             # Application entry point
├── basic_chatbot.py        # Core chatbot logic and tools
├── audio_output/           # Generated audio files
├── data/                   # Database files
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
└── README.md             # This file
```

---

## 🏃 Quick Start

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
docker-compose up -d
```

#### 4. Access the API
- **Swagger UI**: http://localhost:8000/docs (Interactive API testing)
- **ReDoc**: http://localhost:8000/redoc (Beautiful documentation)
- **Health Check**: http://localhost:8000/health

### Option 2: Local Development

#### 1. Create and Activate Virtual Environment
```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 2. Install Dependencies
```sh
pip install -r requirements.txt
```

#### 3. Configure Environment Variables

Create a `.env` file:

```env
# LLM configuration
CHATBOT_MODEL=openai:gpt-5.1           # or another supported model
CHATBOT_API_KEY=your-openai-api-key    # OpenAI, Anthropic, or Google API key

# Tavily Search
TAVILY_API_KEY=your-tavily-api-key     # Get from https://app.tavily.com/

# TTS Configuration
TTS_VOICE=af_heart                     # Voice type
TTS_LANG_CODE=b                        # Language code

# (Optional) LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=ai_agent
```

#### 4. Run the Server
```sh
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 API Endpoints

### Health & Info

#### `GET /` - Root endpoint
```json
{
  "name": "AI Agent API",
  "version": "2.0.0",
  "description": "FastAPI-based conversational AI assistant"
}
```

#### `GET /health` - Health check
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "chat": true,
    "audio": true
  }
}
```

### Chat Endpoints

#### `POST /chat/message` - Send a chat message
**Request:**
```json
{
  "message": "What is the capital of France?",
  "thread_id": "user-123"
}
```

**Response:**
```json
{
  "response": "The capital of France is Paris...",
  "thread_id": "user-123"
}
```

#### `POST /chat/history` - Get chat history
**Request:**
```json
{
  "thread_id": "user-123"
}
```

**Response:**
```json
{
  "thread_id": "user-123",
  "messages": [
    {"type": "HumanMessage", "content": "Hello"},
    {"type": "AIMessage", "content": "Hi there!"}
  ]
}
```

#### `DELETE /chat/history/{thread_id}` - Clear chat history
**Response:**
```json
{
  "status": "success",
  "message": "History cleared for thread user-123"
}
```

### Audio Endpoints

#### `POST /audio/generate` - Generate audio from text
**Request:**
```json
{
  "text": "Hello, world!",
  "voice": "af_heart"
}
```

**Response:**
```json
{
  "audio_url": "/audio/files/response_1234567890.wav",
  "duration": 2.5
}
```

#### `GET /audio/files/{filename}` - Download audio file
Returns the audio file as `audio/wav`.

#### `GET /audio/available` - Check TTS availability
```json
{
  "available": true,
  "message": "TTS service is available"
}
```

---

## 🔧 API Usage Examples

### Using cURL

```bash
# Send a chat message
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a joke", "thread_id": "my-thread"}'

# Generate audio
curl -X POST "http://localhost:8000/audio/generate" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, world!"}' \
  | jq -r '.audio_url' \
  | xargs -I {} curl -O "http://localhost:8000{}"

# Health check
curl "http://localhost:8000/health"
```

### Using Python

```python
import requests

# Send chat message
response = requests.post(
    "http://localhost:8000/chat/message",
    json={
        "message": "What's the weather like?",
        "thread_id": "user-456"
    }
)
print(response.json())

# Generate audio
audio_response = requests.post(
    "http://localhost:8000/audio/generate",
    json={"text": "Hello from AI Agent!"}
)
audio_data = audio_response.json()
print(f"Audio URL: {audio_data['audio_url']}")
```

### Using JavaScript/Fetch

```javascript
// Send chat message
const response = await fetch('http://localhost:8000/chat/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Hello AI!',
    thread_id: 'web-user-789'
  })
});
const data = await response.json();
console.log(data.response);
```

---

## 🧪 Testing

### Interactive API Documentation

FastAPI provides automatic interactive documentation in two flavors:

- **Swagger UI**: http://localhost:8000/docs
  - Try out API endpoints directly in your browser
  - Send test requests and see responses
  - Perfect for development and testing

- **ReDoc**: http://localhost:8000/redoc
  - Beautiful, responsive documentation
  - Better for reading and sharing
  - Clean, professional layout
  - Perfect for public API documentation

- **OpenAPI Schema**: http://localhost:8000/openapi.json
  - Raw OpenAPI 3.0 specification
  - Use with code generators and tools

### Manual Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

---

## 🔒 Environment Variables

| Variable            | Description                                         | Default      |
|---------------------|-----------------------------------------------------|--------------|
| `CHATBOT_MODEL`     | LLM model (e.g., `gemini-pro`, `openai:gpt-5.1`)    | Required     |
| `CHATBOT_API_KEY`   | API key for the selected LLM provider              | Required     |
| `TAVILY_API_KEY`    | Tavily Search Engine API key                       | Required     |
| `TTS_VOICE`         | TTS voice to use                                   | `af_heart`   |
| `TTS_LANG_CODE`     | TTS language code                                  | `b`          |
| `LANGSMITH_TRACING` | Enable LangSmith tracing                           | `false`      |
| `LANGSMITH_API_KEY` | LangSmith API key                                  | Optional     |
| `LANGSMITH_PROJECT` | Project name for LangSmith traces                  | `ai_agent`   |

---

## 🏗️ Architecture

### Clean Architecture Pattern

```
┌─────────────────────────────────────────┐
│          Controllers Layer              │
│  (API Routes, Request/Response)         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Services Layer                 │
│  (Business Logic, Async Operations)     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       Core Logic Layer                  │
│  (Chatbot, LangGraph, Tools)           │
└─────────────────────────────────────────┘
```

### Key Components

- **Controllers**: Handle HTTP requests/responses, validation
- **Services**: Business logic, async operations, state management
- **Models**: Pydantic models for request/response validation
- **Dependencies**: FastAPI dependency injection
- **Core**: LangGraph agent, tools, and LLM integration

---

## 🔄 Development

### Running in Development Mode

```bash
# With auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# With custom log level
uvicorn app.main:app --reload --log-level debug
```

### Adding New Endpoints

1. Define models in `app/models/`
2. Create service methods in `app/services/`
3. Add controller routes in `app/controllers/`
4. Register router in `app/main.py`

### Example: Adding a New Endpoint

```python
# 1. Add model (app/models/custom.py)
class CustomRequest(BaseModel):
    data: str

# 2. Add service method (app/services/custom_service.py)
async def process_data(self, data: str) -> str:
    return f"Processed: {data}"

# 3. Add controller (app/controllers/custom.py)
@router.post("/custom")
async def custom_endpoint(request: CustomRequest):
    service = get_custom_service()
    result = await service.process_data(request.data)
    return {"result": result}

# 4. Register in main.py
app.include_router(custom_router)
```

---

## 🚢 Deployment

### Docker Production

```bash
docker-compose up -d
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with Gunicorn (production)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Environment Configuration

For production, ensure you:
1. Set proper CORS origins in `app/main.py`
2. Use environment-specific `.env` files
3. Enable HTTPS/TLS
4. Set up proper logging
5. Configure rate limiting (if needed)

---

## 📖 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/docs/)
- [Tavily Search](https://app.tavily.com/)
- [Google Gemini](https://ai.google.dev/)
- [Kokoro TTS](https://github.com/kokoro-ai/kokoro)

---

## 📝 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📧 Support

For issues and questions, please open an issue on GitHub.
