# TriGuard AI Medical Triage Assistant v3 - Full Codebase Context

## Overview

This repository contains **TriGuard AI**, a voice-enabled, visual, and text-based medical triage assistant. It is designed for production use, hardened against security vulnerabilities (e.g., injection, stack trace leaks), resource leaks, and async racing conditions.

The architecture consists of:

1. **Backend**: FastAPI with Python 3.10+ and Motor (Async MongoDB). It uses `langgraph` for stateful multi-agent workflows and Groq's APIs for LLaMA 3.1 (LLM) and Whisper (Speech-to-Text). Tavily is used for medical information retrieval.
2. **Frontend**: React 18 with Vite, Tailwind CSS, and Framer Motion. Uses Axios for API communication and features beautiful, responsive UI with animations and dark mode.

---

## Directory Structure

```text
.
├── backend/
│   ├── .env                    # Environment variables (GROQ_API_KEY, TAVILY_API_KEY, MONGODB_URI)
│   ├── requirements.txt        # Python dependencies
│   └── src/
│       ├── main.py             # FastAPI entry point, global exception handlers, lifespan events
│       ├── api/
│       │   └── routes.py       # REST endpoints: /triage, /voice, /image, /xray, /sessions, /reports
│       ├── state/
│       │   └── state.py        # TypedDict definition (TriageState) for LangGraph
│       ├── nodes/              # LangGraph nodes (async)
│       │   ├── classification_node.py
│       │   ├── symptom_extraction_node.py
│       │   ├── tavily_retrieval_node.py
│       │   ├── risk_evaluation_node.py
│       │   └── save_session_node.py
│       ├── tools/              # Actionable modular tools
│       │   ├── groq_llama_tool.py          # LLaMA 3.1 completion wrapper (thread-safe singleton)
│       │   ├── mongodb_tool.py             # Async Motor client, secure atomic updates
│       │   ├── tavily_tool.py              # Medical info retrieval via Tavily
│       │   ├── whisper_tool.py             # Voice transcription using Groq Whisper
│       │   ├── tts_tool.py                 # Text-to-speech using gTTS with resource leak prevention
│       │   ├── nutrition_image_tool.py     # LLaMA vision wrapper
│       │   └── vision_classifier_tool.py
│       └── logging/
│           └── logger.py       # Structured JSON logging
│
├── frontend/
│   ├── .env                    # VITE_API_URL settings
│   ├── package.json            # NPM dependencies
│   ├── vite.config.js          # Vite config
│   └── src/
│       ├── main.jsx            # React root
│       ├── App.jsx             # React Router and main Layout (Sidebar, Topbar)
│       ├── index.css           # Tailwind directives and custom CSS vars
│       ├── App.css             # Additional custom styles
│       ├── api/
│       │   └── client.js       # Axios client with interceptors
│       ├── pages/
│       │   ├── Landing.jsx     # Hero page
│       │   ├── Dashboard.jsx   # Metrics overview
│       │   ├── History.jsx     # Past reports viewer
│       │   └── TriageChat.jsx  # Main conversational UI with voice and text inputs
│       ├── components/
│       │   ├── VoiceToggle.jsx # Microphone active/inactive animated button
│       │   └── RiskBadge.jsx   # Risk severity UI component
│       └── hooks/
│           └── useTriageReports.js # Custom hook for DB fetching
│
├── docker-compose.yml          # Boots mongodb database, backend API, and frontend
├── Dockerfile.backend          # Multi-stage production container for FastAPI
├── Dockerfile.frontend         # Nginx container serving built React app
└── DEPLOYMENT.md               # Instructions for setting up and running via Docker
```

---

## Technical Flow & State Management

### 1. The LangGraph State (`TriageState`)

The agent runs on `LangGraph`, holding state across turns. The state `TypedDict` includes:

- `messages`: List of chat dialogs (user + assistant).
- `symptoms`: List of extracted strings.
- `risk_level`: String (low, medium, high, critical).
- `risk_score`: Float.
- `next_action`: E.g., `ask_followup`, `priority_interrupt`.
- `vision_findings`: Dict.

### 2. Node Execution (18 LangGraph Nodes)

The backend leverages an extensive AI-agent graph composed of 18 distinct nodes in `backend/src/nodes/`:

#### Session & State Management

1. `load_session_node`: Hydrates state from MongoDB.
2. `save_session_node`: Writes state checkpoints back to MongoDB.
3. `load_history_node`: Fetches historical triage reports for context.
4. `save_history_node`: Archives completed triage interactions.

#### Core Triage Pipeline

5. `symptom_extraction_node`: Uses LLaMA to pull explicit symptoms from raw text.
6. `tavily_retrieval_node`: Searches relevant medical literature using Tavily.
7. `disease_retrieval_node`: Compares symptoms to known disease vectors.
8. `risk_evaluation_node`: Computes severity (low, medium, high, critical) combining rules + LLMs.
9. `llm_brain_node`: Orchestrates complex logic, reasoning, and context routing.
10. `response_node`: Generates the final conversational reply output.

#### Specialized Pipelines & Vision

11. `medical_vision_node`: Processes general uploaded symptoms/body images using LLaMA vision.
12. `xray_analysis_node`: Detects fractures, anomalies, and runs specific radiological evaluations.
13. `ocr_processing_node`: Pulls raw text from medical lab reports and charts.
14. `nutrition_node`: Specialized flow for meal/diet tracking via images or text.
15. `mental_health_node`: Separates psychological routing from physical symptom tracks.

#### Validation & Follow-Ups

16. `followup_node`: Asks clarifying questions if confidence is low.
17. `symptom_followup_node`: Tracks answers to direct symptom follow-ups.
18. `judge_validator_node`: Independent LLM check to prevent dangerous hallucinated outputs before replying to the user.
19. `classification_node`: Determines if the user input is medical, emergency, or casual. (Included in core routing).

### 3. Key Hardening Features (v3)

**Backend:**

- **Startup Architectures**: Uses FastAPI `@asynccontextmanager` `lifespan` handler to connect Mongo and compile the LangGraph instance once, putting it in `app.state.graph`.
- **Async Efficiency**: Bound IO tasks to `asyncio.to_thread` and refactored native MongoDB commands to `motor.motor_asyncio`. No blocking calls in `FastAPI`.
- **Thread Safety**: Uses `threading.Lock()` to secure global variables holding the `.client` objects in Groq and Tavily wrappers against race conditions under async load.
- **Resource Management**: Ephemeral TTS audio tracks and cached images are safely wiped in `_cleanup_old_files` to prevent disk leaks.
- **Security**: Strict payload size limitations (max 10MB) combined with `python-magic` MIME filetype checking to prevent malicious multipart form data.
- **Error Handling**: Wrapped Object ID references inside `try / except InvalidId` to prevent crash-vectors when invalid sessions strings are provided. Also implemented a `@app.exception_handler` to swallow stack-traces on 500 errors.

**Frontend:**

- **State Integrity**: Replaced raw object modifications with functional React `setState((prev) => ...)` to avoid message queues corrupting under high async loads (out of order replies).
- **Unique IDs**: Moved mapping IDs from `Date.now()` to strict `crypto.randomUUID()` so messages cannot collide and cause React rendering glitches.
- **UI Guardrails**: Inputs disable while `isLoading` is true, ensuring users don't spam requests and overwhelm the state graph.

## Developer Next Steps

To run:

1. Copy `.env.example` -> `.env` and fill keys (Groq, Tavily).
2. Ensure MongoDB is running (or use Docker).
3. Backend: `cd backend && uv pip install -r requirements.txt && fastapi run src/main.py --port 8000`
4. Frontend: `cd frontend && npm install && npm run dev`
5. Alternatively: `docker-compose up --build -d`
