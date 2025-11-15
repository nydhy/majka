import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client


class MotherPayload(BaseModel):
    name: str
    age: int | None = None
    country: str | None = None
    delivered_at: datetime | None = None


class AnswerPayload(BaseModel):
    mother_id: int
    question_id: int
    answer: str

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
    "SUPABASE_ANON_KEY"
)
SUPABASE_MOTHERS_TABLE = os.getenv("SUPABASE_MOTHERS_TABLE", "mothers")
SUPABASE_QUESTIONS_TABLE = os.getenv("SUPABASE_QUESTIONS_TABLE", "questions")
SUPABASE_ANSWERS_TABLE = os.getenv("SUPABASE_ANSWERS_TABLE", "answers")
SUPABASE_OPTIONS_TABLE = os.getenv("SUPABASE_OPTIONS_TABLE", "question_options")

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

def _resp_error(resp):
    return getattr(resp, "error", None)


def _resp_data(resp):
    return getattr(resp, "data", None)


@app.post("/api/mothers")
def create_mother(payload: MotherPayload):
    try:
        record = {
            "name": payload.name,
            "age": payload.age,
            "country": payload.country,
            "delivered_at": payload.delivered_at.isoformat()
            if payload.delivered_at
            else None,
        }

        response = supabase.table(SUPABASE_MOTHERS_TABLE).insert(record).execute()
        error = _resp_error(response)
        data = _resp_data(response)
        if error or not data:
            raise HTTPException(
                status_code=500,
                detail=str(error or "Unable to create mother record"),
            )

        return {"mother_id": data[0]["id"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/questions")
def list_questions():
    questions_resp = (
        supabase.table(SUPABASE_QUESTIONS_TABLE)
        .select("id,text,order_index,is_active")
        .eq("is_active", True)
        .order("order_index")
        .execute()
    )
    error = _resp_error(questions_resp)
    if error:
        raise HTTPException(status_code=500, detail=str(error))

    questions = _resp_data(questions_resp) or []
    if not questions:
        return []

    question_ids = [q["id"] for q in questions]
    options_by_question: dict[int, list[dict]] = {qid: [] for qid in question_ids}
    if question_ids:
        options_resp = (
            supabase.table(SUPABASE_OPTIONS_TABLE)
            .select("id,question_id,label,value,order_index")
            .in_("question_id", question_ids)
            .order("order_index")
            .execute()
        )
        error = _resp_error(options_resp)
        if error:
            raise HTTPException(status_code=500, detail=str(error))
        for option in _resp_data(options_resp) or []:
            options_by_question.setdefault(option["question_id"], []).append(option)

    result = []
    for question in questions:
        result.append(
            {
                "id": question["id"],
                "text": question["text"],
                "order_index": question["order_index"],
                "options": options_by_question.get(question["id"], []),
            }
        )
    return result


@app.post("/api/answers")
@app.post("/api/answer")
def save_answer(payload: AnswerPayload):
    now = datetime.utcnow().isoformat()

    record = {
        "mother_id": payload.mother_id,
        "question_id": payload.question_id,
        "answer_text": payload.answer,
        "created_at": now,
    }

    response = supabase.table(SUPABASE_ANSWERS_TABLE).insert(record).execute()
    error = _resp_error(response)
    if error:
        raise HTTPException(status_code=500, detail=str(error))

    data = _resp_data(response) or []
    inserted = data[0] if data else {}
    return {
        "status": "ok",
        "answer_id": inserted.get("id"),
    }
