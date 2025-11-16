# Majka – Postpartum Companion

Majka is a full-stack companion app that helps new mothers rebuild strength, track their intake answers, and receive AI‑assisted guidance.

## Features
- **FastAPI backend** connected to Supabase for mothers/questions/answers.
- **Gemini-powered plan** generation that factors in answers + delivery date.
- **Guided session launcher** that opens the posture-tracking `MLH.py` exercise coach.
- **Chatbot widget** powered by `/ask-majka` so moms can ask follow-up questions.

## Tech Stack
| Area | Technology |
| --- | --- |
| Frontend | React 19 + Vite, CSS modules |
| Backend API | FastAPI, Supabase client, Google Generative AI |
| Guided Sessions | OpenCV + MediaPipe (`MLH.py`) |
| Chatbot API | FastAPI, Gemini (optional ElevenLabs TTS) |

## Getting Started
### 1. Install Dependencies
```bash
python -m venv gkenv && source gkenv/bin/activate  # or gkenv\Scripts\activate on Windows
pip install -r backend/requirements.txt

cd frontend
npm install
```

### 2. Configure Environment
Create `backend/.env`:
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
GEMINI_API_KEY=...
GOOGLE_API_KEY=...         # for Majka chatbot (falls back to GEMINI_API_KEY)
ELEVENLABS_API_KEY=...     # optional if you plan to enable TTS later
MAX_QUESTION_ORDER=18
```
Set `frontend/.env` for API URLs if they differ from defaults:
```
VITE_API_URL=http://localhost:8000
# Optional: override chatbot base URL (defaults to VITE_API_URL)
# VITE_BOT_API_URL=http://localhost:8000
```

### 3. Run Services
```bash
# FastAPI API
uvicorn backend.main:app --reload --port 8000
# React frontend
cd frontend && npm run dev
```

## Key Endpoints
| Endpoint | Description |
| --- | --- |
| `POST /api/mothers` | Sign-up a mother profile. |
| `POST /api/auth/login` | Log in and resume unanswered questions. |
| `GET /api/questions` | Fetch ordered intake questions + options. |
| `POST /api/answers` | Save or update a single answer. |
| `POST /api/recommendations` | Run Gemini to generate a structured plan. |
| `POST /api/guided-session` | Launch `MLH.py` for the selected exercise. |
| `POST /ask-majka` | Chatbot conversation endpoint (Gemini). |

## Project Structure
```
backend/
  main.py          # FastAPI app
  MLH.py           # Guided exercise tracker
  requirements.txt
frontend/
  src/App.jsx      # Main React flow
  src/App.css
  src/assets/
logo/              # Brand artwork
```

## Guided Sessions (MLH.py)
- Accepts `--exercise <key>` (e.g., `bird_dog`) to track a specific move.
- Uses MediaPipe pose estimation + pyttsx3 TTS.
- Auto-closes after 6 minutes or when window closed.

## Chatbot Widget
After the plan is generated, a round Majka logo appears bottom-right. Clicking it opens the chat panel which sends requests to `/ask-majka` and displays Majka’s replies.

---
Feel free to open issues or contribute improvements to make Majka even more supportive for mothers everywhere!
