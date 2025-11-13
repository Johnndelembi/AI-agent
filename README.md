# Mipango - FastAPI AI Engine

A production-grade AI Engine built with **FastAPI**, **LangGraph**, **LangChain**.  
Features natural language processing, Facebook Graph APIs integration, recommendation engine and RAG system for context with a clean REST APIs architecture.

---

## 🚀 Features

- **RESTful API**: Clean, documented [redoc] FastAPI endpoints
- **AI Recommendation Engine**: Recommendation Engine that uses AI to generate recommendation ooptions to users based on their cycles.
- **Natural Language Processing**: Context-aware Conversational exchange style between AI and the user
- **Facebook Graph APIs**: Leverage facebook graph APIs for whatsapp business integration with the chatbot
- **RAG system**: Retrieval-based system that leverages provided KB and database actions to generate context aware responses
- **Modern Architecture**: Clean separation with routers, services, and models
- **Async Support**: Full async/await support for high performance
- **Auto Documentation**: Interactive API docs at `/docs`
- **Health Checks**: Built-in health monitoring endpoints
- **CORS Support**: Configurable CORS for web clients
- **Thread-based Conversations**: Maintain conversation context across multiple messages

---

## 📁 Project Structure

```
Mipango-AI-Engine/
├── app/
│   ├── routers/          # API route handlers
│   │   ├── chat.py          # Chat endpoints
│   │   ├── whatsapp.py         # Whatsapp integration endpoints
│   │   └── health.py        # Health check endpoints
│   ├── services/            # Business logic layer
│   │   ├── chat_service.py  # Conversational AI service
│   │   └── agent_service.py # AI Engine service
|   |
│   ├── models/              # Request/response models
│   │   └── chat.py          # Pydantic models
│   ├── dependencies.py      # FastAPI dependencies
│   └── main.py             # Application entry point
├── data/                   # Knowledge-base files
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
└── README.md             # This file
```

## 🏗️ Architecture

### Architecture Pattern

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
│  (AI-Engine, LangGraph, Tools)           │
└─────────────────────────────────────────┘
```

### Key Components

- **Controllers**: Handle HTTP requests/responses, validation
- **Services**: Business logic, async operations, state management
- **Models**: Pydantic models for request/response validation
- **Dependencies**: FastAPI dependency injection
- **Core**: LangGraph, Langchain, tools, and LLM ochestration

---
