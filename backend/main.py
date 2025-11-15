import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client

class AnswerPayload(BaseModel):
    session_id: str | None = None
    question: str
    answer: str

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
    "SUPABASE_ANON_KEY"
)
SUPABASE_MOTHERS_TABLE = os.getenv("SUPABASE_MOTHERS_TABLE", "mothers")
SUPABASE_QUESTIONS_TABLE = os.getenv("SUPABASE_QUESTIONS_TABLE", "questions")
SUPABASE_ANSWERS_TABLE = os.getenv("SUPABASE_ANSWERS_TABLE", "answers")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _ensure_mother(session_id: str | None) -> tuple[str, int]:
    """Return (session_id, mother_id). Creates mother when session missing."""
    if session_id:
        try:
            mother_id = int(session_id)
            return session_id, mother_id
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    placeholder_name = f"Session {uuid.uuid4().hex[:8]}"
    response = (
        supabase.table(SUPABASE_MOTHERS_TABLE)
        .insert({"name": placeholder_name})
        .execute()
    )
    if response.error or not response.data:
        raise HTTPException(
            status_code=500, detail=str(response.error or "Unable to create mother")
        )

    mother_id = response.data[0]["id"]
    return str(mother_id), mother_id


def _get_question_id(question_text: str) -> int:
    response = (
        supabase.table(SUPABASE_QUESTIONS_TABLE)
        .select("id")
        .eq("text", question_text)
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Question not configured in DB")

    return response.data[0]["id"]


@app.post("/api/answer")
def save_answer(payload: AnswerPayload):
    session_id, mother_id = _ensure_mother(payload.session_id)
    question_id = _get_question_id(payload.question)
    now = datetime.utcnow().isoformat()

    record = {
        "mother_id": mother_id,
        "question_id": question_id,
        "answer_text": payload.answer,
        "created_at": now,
    }

    response = supabase.table(SUPABASE_ANSWERS_TABLE).insert(record).execute()

    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))

    inserted = response.data[0] if response.data else {}
    return {
        "status": "ok",
        "session_id": session_id,
        "answer_id": inserted.get("id"),
    }
