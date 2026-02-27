# 🛡️ TriGuard AI — Multimodal Medical Triage Assistant (V5.0)

TriGuard AI is a production-grade multimodal medical triage system designed to provide rapid, safe, and intelligent health risk assessments. Version 5.0 introduces a dedicated document processing pipeline and revolutionary conversational continuity, allowing the system to bridge context across image and text turns.

---

## 🚀 What's New in Version 5.0 (V5)

The **V5 "Multimodal Bridge" Update** focus on pipeline maturity and user experience:

- 📄 **Deep Document Pipeline**: A dedicated `DOCUMENT → OCR → TEXT` flow. Uploading medical reports, prescriptions, or lab results automatically triggers high-precision OCR and feeds extracted symptoms into the clinical text engine.
- 🧠 **V5.1 Follow-up Context Patch**: Real-time context bridging. The AI now remembers prior X-ray, skin, or document findings during subsequent text-based questions (e.g., "Why am I getting this pain?" after an X-ray upload).
- ⚡ **Performance 2.0**:
  - **Single-Pass Vision**: Unified vision classification reduces document analysis latency by 50%.
  - **O(1) Scale**: Safety guards now use constant-time history scanning regardless of conversation length.
- 🛡️ **Granular Error Handling**: New `vision_error` and `ocr_completed` safety flags ensure structured, helpful fallbacks instead of blank outputs or hallucinations.
- 🌍 **Native Multilingual**: Triage instructions are now embedded directly in the LLM prompt, eliminating sequential translation round-trips for non-English users.

---

## ✨ Key Features

- 💬 **Multimodal AI Triage:** Intelligent analysis for Text, Voice, Body Images (Skin/Dermatology), and X-rays.
- 🎙️ **Voice First UX:** Seamless Whisper STT and gTTS integration for hands-free medical input.
- 🩻 **Radiology Screening:** Specialized pre-diagnosis nodes for chest X-ray analysis (Note: For screening only).
- � **Deterministic Logic:** Orchestrated via **LangGraph**, ensuring clinical routing follows strict protocols rather than unpredictable LLM decisions.
- 📊 **Risk Scoring Engine:** Real-time risk-level calculation (Low to Critical) with structured Red-Flag detection.
- 🏛️ **Persistence with Privacy:** Opt-in session history (`use_history`) with MongoDB secondary persistence.
- 🥗 **Integrated Nutrition:** Triage-aware dietary advice provided alongside medical assessments.
- 🛡️ **Judge Validator:** An internal AI "Judge" validates every response for hallucinations, medical safety, and adherence to triage constraints before it reaches the user.

---

## 🏗️ Architecture Overview

The project follows a modular **Monorepo** structure:

```text
TriGuard-AI/
├── backend/           # FastAPI + LangGraph + MongoDB
│   ├── src/
│   │   ├── nodes/     # Pure node logic (Vision, OCR, Brain, Risk, etc.)
│   │   ├── graph/     # LangGraph state machines and routing
│   │   ├── tools/     # API connectors (Groq, Tavily, MongoDB)
│   │   └── state/     # TypedDict state contracts
│   └── tests/         # Comprehensive V5 test suite
├── frontend/          # React 19 + Framer Motion + Tailwind 4
└── README.md          # Version 5.0 Documentation
```

---

## 🛠️ Technology Stack

- **Reasoning/NLP:** Groq LLaMA 3.1 70B (Brain), LLaMA 3 8B (Classification).
- **Vision/OCR:** Groq Vision-LLaVA, Tesseract/OCR-Engine.
- **Orchestration:** LangGraph (Stateful Multi-actor Graph).
- **Backend:** Python 3.11, FastAPI, Pydantic V2, Motor.
- **Frontend:** React 19, Framer Motion (premium animations), Tailwind CSS 4.
- **Search:** Tavily AI (Medical web search).

---

## 🚀 Getting Started

1. **Install uv**: `pip install uv`
2. **Setup Backend**: `cd backend && uv sync`
3. **Setup Frontend**: `cd frontend && npm install`
4. **Environment**: Add `GROQ_API_KEY`, `TAVILY_API_KEY`, and `MONGO_URI` to `backend/.env`.

---

## ⚖️ Disclaimer

_TriGuard AI is an AI assistant intended for informational purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition._

---

&copy; 2026 TriGuard AI Team | [Repository](https://github.com/620593/TriGuard-AI-Medical-Triage-Assistant)
