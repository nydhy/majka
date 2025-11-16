import difflib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import google.generativeai as genai
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


class RecommendationPayload(BaseModel):
    mother_id: int


class GuidedSessionPayload(BaseModel):
    exercise: str

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EXERCISES = [
    {"key": "breathing", "label": "Breathing"},
    {"key": "pelvic_floor", "label": "Pelvic Floor"},
    {"key": "pelvic_tilt", "label": "Pelvic Tilt", "aliases": ["Pelvic Tilts"]},
    {"key": "heel_slide", "label": "Heel Slide", "aliases": ["Heel Slides"]},
    {"key": "glute_bridge", "label": "Glute Bridge", "aliases": ["Glute Bridges"]},
    {"key": "walking", "label": "Walking", "aliases": ["Gentle Walk"]},
    {"key": "bodyweight_squat", "label": "Bodyweight Squat", "aliases": ["Bodyweight Squats"]},
    {"key": "stationary_lunge", "label": "Stationary Lunge", "aliases": ["Stationary Lunges"]},
    {"key": "bird_dog", "label": "Bird-Dog", "aliases": ["Bird Dog", "Bird Dogs"]},
    {"key": "dead_bug", "label": "Dead Bug", "aliases": ["Dead Bugs"]},
    {"key": "modified_plank", "label": "Modified Plank", "aliases": ["Modified Planks"]},
    {"key": "bent_over_row", "label": "Bent-Over Row", "aliases": ["Bent Over Row", "Bent Over Rows"]},
    {"key": "bicep_curl", "label": "Bicep Curl", "aliases": ["Bicep Curls"]},
    {"key": "overhead_press", "label": "Overhead Press", "aliases": ["Overhead Presses"]},
    {"key": "goblet_squat", "label": "Goblet Squat", "aliases": ["Goblet Squats"]},
    {"key": "weighted_lunge", "label": "Weighted Lunge", "aliases": ["Weighted Lunges"]},
    {"key": "single_leg_deadlift", "label": "Single-Leg Deadlift", "aliases": ["Single Leg Deadlift"]},
    {"key": "squat_jump", "label": "Squat Jump", "aliases": ["Squat Jumps"]},
    {"key": "run_intervals", "label": "Run/Walk", "aliases": ["Run Walk", "Intervals"]},
    {"key": "hiit", "label": "HIIT Posture", "aliases": ["HIIT"]},
]


def _normalize_exercise_label(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return re.sub(r"_+", "_", lowered).strip("_")


EXERCISE_LOOKUP = {}
for entry in EXERCISES:
    key = entry["key"]
    label = entry["label"]
    EXERCISE_LOOKUP[key] = key
    EXERCISE_LOOKUP[_normalize_exercise_label(label)] = key
    for alias in entry.get("aliases", []):
        normalized = _normalize_exercise_label(alias)
        if normalized:
            EXERCISE_LOOKUP[normalized] = key

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY"
    )


if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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


def _resolve_exercise_key(name: str | None) -> str:
    if not name:
        raise HTTPException(status_code=400, detail="Exercise name is required.")
    normalized = _normalize_exercise_label(name)

    def _try_lookup(value: str) -> str | None:
        if value in EXERCISE_LOOKUP:
            return EXERCISE_LOOKUP[value]
        return None

    candidates = [normalized]
    if normalized.endswith("es"):
        candidates.append(normalized[:-2])
    if normalized.endswith("s"):
        candidates.append(normalized[:-1])

    for cand in candidates:
        resolved = _try_lookup(cand)
        if resolved:
            return resolved

    matches = difflib.get_close_matches(
        normalized, list(EXERCISE_LOOKUP.keys()), n=1, cutoff=0.75
    )
    if matches:
        return EXERCISE_LOOKUP[matches[0]]

    raise HTTPException(
        status_code=404,
        detail=f"Exercise '{name}' is not available for guided sessions.",
    )


def _fetch_answer_pairs(mother_id: int):
    questions_resp = (
        supabase.table(SUPABASE_QUESTIONS_TABLE)
        .select("id,text,order_index")
        .eq("is_active", True)
        .lte("order_index", MAX_QUESTION_ORDER)
        .order("order_index")
        .execute()
    )
    q_error = _resp_error(questions_resp)
    if q_error:
        raise HTTPException(status_code=500, detail=str(q_error))

    questions = _resp_data(questions_resp) or []
    question_map = {q["id"]: q for q in questions}

    answers_resp = (
        supabase.table(SUPABASE_ANSWERS_TABLE)
        .select("question_id,answer_text")
        .eq("mother_id", mother_id)
        .execute()
    )
    a_error = _resp_error(answers_resp)
    if a_error:
        raise HTTPException(status_code=500, detail=str(a_error))

    answers = _resp_data(answers_resp) or []
    answer_map = {row["question_id"]: row["answer_text"] for row in answers}

    pairs = []
    for question in questions:
        answer = answer_map.get(question["id"])
        if answer:
            pairs.append(
                {
                    "question": question["text"],
                    "answer": answer,
                    "order_index": question["order_index"],
                }
            )
    return pairs


def _fetch_mother_profile(mother_id: int):
    resp = (
        supabase.table(SUPABASE_MOTHERS_TABLE)
        .select("name,delivered_at")
        .eq("id", mother_id)
        .limit(1)
        .execute()
    )
    error = _resp_error(resp)
    if error:
        raise HTTPException(status_code=500, detail=str(error))
    data = _resp_data(resp) or []
    if not data:
        raise HTTPException(status_code=404, detail="Mother profile not found")
    return data[0]


def _build_recommendation_prompt(
    pairs: list[dict],
    postpartum_weeks: float | None = None,
    delivered_at_str: str | None = None,
    mother_name: str | None = None,
):
    qa_section = "\n".join(
        [
            f"{idx + 1}. Question: {item['question']}\n   Answer: {item['answer']}"
            for idx, item in enumerate(pairs)
        ]
    )
    exercise_section = "\n".join(f"- {exercise['label']}" for exercise in EXERCISES)
    postpartum_text = "Postpartum timing unknown."
    if delivered_at_str and postpartum_weeks is not None:
        postpartum_text = (
            f"Delivery date: {delivered_at_str} "
            f"(approximately {postpartum_weeks:.1f} weeks postpartum)."
        )
    elif postpartum_weeks is not None:
        postpartum_text = f"Approximately {postpartum_weeks:.1f} weeks postpartum."

    name_for_prompt = mother_name or "mama"

    prompt = f"""
You're Majka, your super cool and honest postpartum coach (think: best friend who knows all the science). Your tone needs to be *real, casual, and genuinely warm. You must always prioritize **safety first*, but sound like a human, no flowery language, no robotic therapist jargon, and use contractions.

### I. CRITICAL SAFETY GUARDRAILS

*GUARDRAIL OVERRIDE (CRITICAL):* You MUST inspect the {qa_section} for high-risk red flags. If the mother reports *Fever, Heavy Bleeding (soaking more than one pad in an hour), Severe/Worsening Incision/Perineal Pain (4/10 or higher), or Pelvic Heaviness/Bulging*, the entire 'exercises' array MUST be empty (i.e., []). The 'intro' must explicitly advise the mother to *stop everything right now* and contact her healthcare provider immediately.

### II. CUSTOMIZATION LOGIC & PRIORITY (Enhanced for Variety)

If the Guardrail is NOT active, select exactly 3 to 4 exercises from the {exercise_section} based on the following priority:

1.  *VARIETY INSTRUCTION:* When selecting the final 3 to 4 exercises, and multiple exercises meet the safety criteria, you MUST *prioritize variety. Do not repeat the most recent plan if the request implies the user wants an alternative. Ensure the final selected set is composed of the safest *and most diverse options available.
2.  *PHASE 1 (Healing, Weeks 0-5):* If {postpartum_text} indicates *less than 6 weeks, the plan MUST prioritize **Diaphragmatic Breathing* and *Pelvic Tilts* (Foundation moves). Limit cardiovascular work to *Gentle Walking*. AVOID all others.
3.  *CORE FOCUS (Diastasis Recti/Incontinence):* If core issues are noted, the plan MUST include *Kegels* (if weeks > 6) and *Pelvic Tilts. Strictly **AVOID* any moves that cause abdominal doming.
4.  *STRENGTH & FITNESS (Weeks 6+):* If {postpartum_weeks} is *6 or greater* and there are *no red flags/pain, you may progress to one or two general strength moves like **Glute Bridges* or *Bodyweight Squats*, adjusting complexity based on the pre-pregnancy fitness level.

### III. THE PLAN GENERATION

Based on the directives above, create the JSON response.

* *{postpartum_text}*: [Context describing weeks postpartum and delivery type]
* *{qa_section}*: [Specific answers regarding pain, core issues, and red flags]
* *{exercise_section}*: [The full library of approved exercises and their descriptions]
* *name_for_prompt*: [The user's first name]

Respond with valid JSON in this shape, using the *casual, human tone* in all text fields:
{{
  "greeting": "Hello mama {name_for_prompt}, it's Majka here!",
  "intro": "A short, punchy, and genuinely human opening thought about their current recovery status and week.",
  "exercises": [
    {{
      "title": "...",
      "summary": "one or two punchy, friendly sentences about the move",
      "why": "Why this move is clutch for them right now (in casual, human language, referencing intake answers).",
      "how": "1-2 easy-to-remember, casual cues.",
      "cta_label": "Start Guided Session"
    }}
  ],
  "closing": "A short, casual, human reminder (e.g., 'Seriously, go drink some water' or 'You're doing great, now rest!')."
}}

Do not include backticks or any explanation outside the JSON.
"""
    return prompt.strip()


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


@app.post("/api/recommendations")
def generate_recommendations(payload: RecommendationPayload):
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured on the server.",
        )

    pairs = _fetch_answer_pairs(payload.mother_id)
    if not pairs:
        raise HTTPException(
            status_code=400,
            detail="No answers found for this mother. Please complete the intake first.",
        )

    mother_profile = _fetch_mother_profile(payload.mother_id)
    delivered_at = mother_profile.get("delivered_at")
    postpartum_weeks = None
    delivered_label = None
    if delivered_at:
        try:
            delivered_dt = datetime.fromisoformat(delivered_at.replace("Z", "+00:00"))
            if delivered_dt.tzinfo:
                delivered_dt = delivered_dt.astimezone(timezone.utc).replace(
                    tzinfo=None
                )
            delivered_label = delivered_dt.strftime("%Y-%m-%d")
            diff_days = (datetime.utcnow() - delivered_dt).days
            postpartum_weeks = max(diff_days / 7, 0)
        except ValueError:
            delivered_label = delivered_at

    prompt = _build_recommendation_prompt(
        pairs,
        postpartum_weeks,
        delivered_label,
        mother_profile.get("name"),
    )

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        plan_text = (response.text or "").strip()
        if not plan_text:
            raise ValueError("Empty response from Gemini model")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini error: {exc}") from exc

    plan_struct = None
    cleaned = plan_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        plan_struct = json.loads(cleaned)
    except Exception:
        plan_struct = None

    return {"plan_text": plan_text, "plan": plan_struct}


@app.post("/api/guided-session")
def start_guided_session(payload: GuidedSessionPayload):
    exercise_key = _resolve_exercise_key(payload.exercise)
    script_path = Path(__file__).with_name("MLH.py")
    if not script_path.exists():
        raise HTTPException(
            status_code=500,
            detail="MLH.py script is missing on the server.",
        )
    try:
        subprocess.Popen(
            [sys.executable, str(script_path), "--exercise", exercise_key],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as exc:  # pragma: no cover - best effort launch
        raise HTTPException(
            status_code=500,
            detail=f"Unable to launch guided session: {exc}",
        ) from exc

    return {
        "status": "launching",
        "exercise": exercise_key,
    }
