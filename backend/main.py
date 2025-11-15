import os
from datetime import datetime

import bcrypt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client


class MotherPayload(BaseModel):
    name: str
    password: str
    age: int | None = None
    country: str | None = None
    delivered_at: datetime | None = None


class LoginPayload(BaseModel):
    name: str
    password: str


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
MAX_QUESTION_ORDER = int(os.getenv("MAX_QUESTION_ORDER", "18"))

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


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


@app.post("/api/mothers")
def create_mother(payload: MotherPayload):
    try:
        existing_resp = (
            supabase.table(SUPABASE_MOTHERS_TABLE)
            .select("id")
            .eq("name", payload.name)
            .limit(1)
            .execute()
        )
        if _resp_error(existing_resp):
            raise HTTPException(
                status_code=500, detail=str(_resp_error(existing_resp))
            )
        if _resp_data(existing_resp):
            raise HTTPException(
                status_code=409, detail="A profile with this name already exists"
            )

        record = {
            "name": payload.name,
            "password_hash": _hash_password(payload.password),
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


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    resp = (
        supabase.table(SUPABASE_MOTHERS_TABLE)
        .select("id,password_hash,name,age,country,delivered_at")
        .eq("name", payload.name)
        .limit(1)
        .execute()
    )
    error = _resp_error(resp)
    if error:
        raise HTTPException(status_code=500, detail=str(error))

    mother = (_resp_data(resp) or [])
    if not mother:
        raise HTTPException(status_code=401, detail="Invalid name or password")

    record = mother[0]
    if not _verify_password(payload.password, record.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid name or password")

    answers_resp = (
        supabase.table(SUPABASE_ANSWERS_TABLE)
        .select("question_id,answer_text")
        .eq("mother_id", record["id"])
        .order("question_id")
        .execute()
    )
    answers_error = _resp_error(answers_resp)
    answered_question_ids = set()
    answered_map: dict[str, str] = {}
    if answers_error:
        raise HTTPException(status_code=500, detail=str(answers_error))
    for answer in _resp_data(answers_resp) or []:
        qid = answer["question_id"]
        answered_question_ids.add(qid)
        answered_map[str(qid)] = answer.get("answer_text")

    questions_resp = (
        supabase.table(SUPABASE_QUESTIONS_TABLE)
        .select("id,order_index")
        .eq("is_active", True)
        .lte("order_index", MAX_QUESTION_ORDER)
        .order("order_index")
        .execute()
    )
    questions_error = _resp_error(questions_resp)
    if questions_error:
        raise HTTPException(status_code=500, detail=str(questions_error))

    questions = _resp_data(questions_resp) or []
    resume_question_id = None
    for question in questions:
        if question["id"] not in answered_question_ids:
            resume_question_id = question["id"]
            break

    valid_ids = {str(q["id"]) for q in questions}
    filtered_answers = {
        key: value for key, value in answered_map.items() if key in valid_ids
    }

    return {
        "mother_id": record["id"],
        "profile": {
            "name": record.get("name"),
            "age": record.get("age"),
            "country": record.get("country"),
            "delivered_at": record.get("delivered_at"),
        },
        "resume_question_id": resume_question_id,
        "answered_answers": filtered_answers,
    }


@app.get("/api/questions")
def list_questions():
    questions_resp = (
        supabase.table(SUPABASE_QUESTIONS_TABLE)
        .select("id,text,order_index,is_active")
        .eq("is_active", True)
        .lte("order_index", MAX_QUESTION_ORDER)
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

    cleanup = (
        supabase.table(SUPABASE_ANSWERS_TABLE)
        .delete()
        .eq("mother_id", payload.mother_id)
        .eq("question_id", payload.question_id)
        .execute()
    )
    cleanup_error = _resp_error(cleanup)
    if cleanup_error:
        raise HTTPException(status_code=500, detail=str(cleanup_error))

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
