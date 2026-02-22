# 🛡️ TriGuard AI — Medical Triage Assistant (Monorepo)

TriGuard AI is a production-grade medical triage system designed to provide rapid, safe, and intelligent health risk assessments. Leveraging FastAPI, LangGraph, MongoDB, and React, it offers a multi-modal interface for text, voice, and medical document analysis.

---

## 🏗️ Architecture Overview

The project is structured as a **Monorepo** to maintain a clean separation between the AI-powered backend and the high-end SaaS frontend.

```text
TriGuard-AI/
├── backend/           # FastAPI + LangGraph + MongoDB
│   ├── src/           # API routes, Graph nodes, and Tools
│   ├── .env           # (Excluded from Git) API keys & Mongo URI
│   └── pyproject.toml # Python dependencies
├── frontend/          # React 19 + Vite + Tailwind 4
│   ├── src/           # Components, Pages, and API client
│   └── package.json   # Node dependencies
└── README.md          # Project documentation
```

---

## ✨ Key Features

- 💬 **AI Triage Chat:** Intelligent symptom follow-up using LangGraph.
- 🎙️ **Voice Mode:** Real-time speech-to-text (Whisper) and text-to-speech (gTTS).
- 📄 **OCR Document Analysis:** Upload lab reports or prescriptions for AI summarization.
- 🩻 **X-ray Analysis:** Integration with vision models for chest X-ray pre-diagnosis.
- 📊 **Risk Visualization:** Real-time risk-level color coding (Low, Medium, High, Critical).
- 🏛️ **MongoDB Persistence:** Session history and state management.
- 🌍 **Multilingual Support:** Automatic language detection and response.
- 🛡️ **Crisis Override:** Immediate guidance for emergency symptoms.

---

## 🚀 Getting Started

### Prerequisites

- [Python 3.11+](https://www.python.org/)
- [Node.js 18+](https://nodejs.org/)
- [uv](https://github.com/astral-sh/uv) (Recommended for Python)
- [MongoDB Atlas](https://www.mongodb.com/products/platform/atlas-database) (or local instance)

### 1. Backend Setup

```bash
cd backend
# Install dependencies
uv sync

# Configure Environment
# Create a .env file based on the required keys:
# GROQ_API_KEY, TAVILY_API_KEY, MONGO_URI, etc.
```

### 2. Frontend Setup

```bash
cd frontend
# Install dependencies
npm install
```

### 3. Running the Application

**Start Backend:**

```bash
uv run uvicorn backend.src.main:app --reload --port 8000
```

**Start Frontend:**

```bash
cd frontend
npm run dev
```

---

## 🛠️ Technology Stack

- **Backend:** Python, FastAPI, LangGraph (LangChain), Pydantic, Motor (Async MongoDB).
- **Frontend:** React 19, Vite, Tailwind CSS 4, Framer Motion, Axios.
- **Tools:** Whisper (STT), gTTS (TTS), HuggingFace Vision Models, Groq LLaMA models.

---

## ⚖️ Disclaimer

_TriGuard AI is an AI assistant intended for informational purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition._

---

&copy; 2026 TriGuard AI Team.
