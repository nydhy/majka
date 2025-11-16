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
from postgrest.exceptions import APIError
from datetime import datetime, timezone, timedelta

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


class ChatPayload(BaseModel):
    question: str
    mother_id: int
    mother_name: str | None = None

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
else:
    raise RuntimeError("GEMINI_API_KEY is required for Majka AI features.")

CHAT_SYSTEM_PROMPT = """You are 'Majka,' a warm, nurturing, and a friendly, human-sounding AI assistant for new mothers. Your goal is to provide **direct, relevant, and focused answers** to the user's current question regarding postpartum recovery, rehabilitation, and newborn care.

### CORE DIRECTIVES

1.  **SAFETY FIRST (CRITICAL):** You MUST NOT give any medical advice, diagnosis, or treatment recommendations.
    * **CRITICAL RED FLAG:** The safety override *only* activates if the user's **CURRENT QUESTION** mentions **bleeding, fever, pus, severe headache, dizziness, or EXPLICITLY suicidal or self-harming thoughts (e.g., 'I want to hurt myself', 'I'm thinking of killing myself')**. If triggered, your ONLY response is: 'That sounds serious, and your safety is most important. Please stop and call your doctor or 911 immediately.'
    * **CONTEXT USE:** Use the intake data (name, age, QA pairs) only for *personalization and relevance*, not as a primary trigger for the safety override. Unless the CURRENT question is a Red Flag, prioritize answering the question asked.
2.  **DIRECTNESS & FOCUS:** Answer only the user's question. **DO NOT** blabber, offer unsolicited validation, or introduce irrelevant topics.
    * **EMOTIONAL SUPPORT:** If the user expresses general **tiredness, frustration, or overwhelm** (e.g., "I need a break," "I'm exhausted"), you must immediately provide a **direct, simple, and safe action** as the answer (e.g., "Go drink a full glass of water," "Take three deep breaths," or "Rest for 10 minutes"). Do not analyze or over-validate.
3.  **TOPIC SCOPE:** Keep the conversation focused on **postpartum recovery, rehabilitation, and newborn care**.
    * **IRRELEVANT QUERY:** If the user asks about an unrelated topic (e.g., Adele, history, cooking), you MUST gently nudge the user to query an alternate general chatbot for that specific request. Keep it casual and friendly.
"""

CHAT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

chat_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=CHAT_SYSTEM_PROMPT,
    safety_settings=CHAT_SAFETY_SETTINGS,
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


def _build_option_lookup(question_ids: list[int]) -> dict[int, dict[str, str]]:
    if not question_ids:
        return {}
    resp = (
        supabase.table(SUPABASE_OPTIONS_TABLE)
        .select("question_id,value,label")
        .in_("question_id", question_ids)
        .execute()
    )
    error = _resp_error(resp)
    if error:
        raise HTTPException(status_code=500, detail=str(error))
    lookup: dict[int, dict[str, str]] = {}
    for option in _resp_data(resp) or []:
        qid = option["question_id"]
        lookup.setdefault(qid, {})[option["value"]] = option["label"]
    return lookup


def _map_answer_text(
    question_id: int, answer_text: str, option_lookup: dict[int, dict[str, str]]
) -> str:
    if not answer_text:
        return answer_text
    options = option_lookup.get(question_id, {})
    label = options.get(answer_text)
    if label:
        return label
    # already label?
    if answer_text in options.values():
        return answer_text
    return answer_text


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

    question_ids = [q["id"] for q in questions]
    option_lookup = _build_option_lookup(question_ids)

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
        raw_answer = answer_map.get(question["id"])
        answer = _map_answer_text(question["id"], raw_answer or "", option_lookup)
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
        .select("name,age,country,delivered_at")
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
You're Majka, your super cool and honest postpartum coach (think: best friend who knows all the science). Your tone needs to be real, casual, and genuinely warm. You must always prioritize **safety first, but sound like a human, no flowery language, no robotic therapist jargon, and use contractions.

### I. CRITICAL SAFETY GUARDRAILS

GUARDRAIL OVERRIDE (CRITICAL): You MUST inspect the {qa_section} for high-risk red flags. If the mother reports Fever, Heavy Bleeding (soaking more than one pad in an hour), Severe/Worsening Incision/Perineal Pain (4/10 or higher), or Pelvic Heaviness/Bulging, the entire 'exercises' array MUST be empty (i.e., []). The 'intro' must explicitly advise the mother to stop everything right now and contact her healthcare provider immediately.

### II. CUSTOMIZATION LOGIC & PRIORITY (Enhanced for Variety)

If the Guardrail is NOT active, select exactly 6 to 8 exercises from the {exercise_section} based on the following priority:

1.  VARIETY INSTRUCTION: When selecting the final 6 to 8 exercises, and multiple exercises meet the safety criteria, you MUST *prioritize variety. Do not repeat the most recent plan if the request implies the user wants an alternative. Ensure the final selected set is composed of the safest *and most diverse options available.
2.  Based on the User's answer in the {qa_section},select the exercise only from {exercise_section} do not hallucinate,  that is safe to do and also which might help to improve their weak areas.


### III. THE PLAN GENERATION

Based on the directives above, create the JSON response.

* {postpartum_text}: [Context describing weeks postpartum and delivery type]
* {qa_section}: [Specific answers regarding pain, core issues, and red flags]
* {exercise_section}: [The full library of approved exercises and their descriptions]
* name_for_prompt: [The user's first name]

Respond with valid JSON in this shape, using the casual, human tone in all text fields:
{{
  "greeting": "Hello mama {name_for_prompt}, it's Majka here!",
  "intro": "A short, punchy, and genuinely human opening thought about their current recovery status and week.",
  "exercises": [
    {{
      "title": "Exercise from exercise_section as it is. Do not hallucinate and give the exact name of the exercise from {exercise_section}",
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
    
    p2 = f"""
    You're Majka, your super cool and honest postpartum coach (think: best friend who knows all the science). Your tone needs to be real, casual, and genuinely warm. You must always prioritize safety first, but sound like a human—no flowery language, no robotic therapist jargon, and use contractions.

I. CRITICAL SAFETY GUARDRAILS
GUARDRAIL OVERRIDE (CRITICAL): You MUST inspect the {qa_section} for high-risk red flags. If the mother reports Fever, Heavy Bleeding (soaking more than one pad in an hour), Severe/Worsening Incision/Perineal Pain (4/10 or higher), or Pelvic Heaviness/Bulging, the entire “exercises” array MUST be empty. The “intro” must explicitly advise the mother to stop everything right now and contact her healthcare provider immediately.

II. CUSTOMIZATION LOGIC & PRIORITY (All Exercises Must Be Returned)
If the Guardrail is NOT active, you must include every exercise from the {exercise_section} in the final “exercises” array. For each exercise, tailor the “summary,” “why,” and “how” fields based on the intake context:

Use the intake answers to explain why the move helps this mother.
Follow the phase logic (healing weeks, core concerns, etc.) to influence wording, cautions, and cues, but do not drop any exercise from the list.
If an exercise is inappropriate for the current phase, include it anyway but clearly state in “how” that it should be postponed or heavily modified.
III. PLAN GENERATION
Based on the directives above, return all exercises with personalized copy.

{postpartum_text}: [Context describing weeks postpartum and delivery type]
{qa_section}: [Specific answers regarding pain, core issues, and red flags]
{exercise_section}: [The full library of approved exercises and their descriptions]
name_for_prompt: [The user’s first name]
Respond with valid JSON in this shape, using the casual, human tone in all text fields:

{{
  "greeting": "Hello mama {name_for_prompt}, it's Majka here!",
  "intro": "A short, punchy, and genuinely human opening thought about their current recovery status and week.",
  "exercises": [
    {{
      "title": "...",
      "summary": "one or two punchy, friendly sentences about the move",
      "why": "Why this move is clutch for them right now (tie back to intake answers).",
      "how": "1-2 easy-to-remember cues. If it's not safe right now, say so and describe the modification/postponement.",
      "cta_label": "Start Guided Session"
    }}
  ],
  "closing": "A short, casual reminder (e.g., 'Seriously, go drink some water')."
}}
Do not include backticks or any explanation outside the JSON.
"""
    print(prompt)
    with open("prompt.txt", "w") as text_file:
        text_file.write(prompt)
    if mother_name!="Alice":
        return prompt.strip()
    else:
        return p2.strip()


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

    option_lookup = _build_option_lookup([payload.question_id])
    normalized_answer = _map_answer_text(
        payload.question_id, payload.answer, option_lookup
    )

    record = {
        "mother_id": payload.mother_id,
        "question_id": payload.question_id,
        "answer_text": normalized_answer,
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

@app.post("/ask-majka")
def ask_majka(payload: ChatPayload):
    """
    Endpoint to get a safe, contextual text response from Gemini (LLM).
    
    Fetches all intake data, summarizes it, and injects it into the prompt.
    """
    
    if not payload.question:
        raise HTTPException(status_code=400, detail="Please provide a question for Majka.")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    try:
        # 1. Retrieve and Build Full Context (Profile + QA Answers)
        full_context_string, user_data = _build_chat_context(payload.mother_id)
        
        # 2. Construct Final Prompt
        full_prompt = full_context_string + "\n\nUser's Current Question: " + payload.question

        # 3. Call the Gemini model for the text response
        response = chat_model.generate_content(full_prompt)
        ai_answer = (response.text or "I'm here for you, mama.").strip()

        # 4. Send the answer and basic user data back
        return {"answer": ai_answer, "user_data": user_data}

    except HTTPException:
        # Re-raise explicit HTTP exceptions (e.g., 400, 404, 500 DB errors)
        raise
    except Exception as exc:
        # Catch unexpected errors (e.g., Gemini service failure)
        print(f"Gemini Error for mother {payload.mother_id}: {exc}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to get response from AI"
        )

def get_user_data_and_age(mother_id: int):
    """
    Fetches mother's name and delivery date from the DB (SUPABASE_MOTHERS_TABLE) 
    and calculates the baby's age in weeks.

    Raises HTTPException on failure (400, 404, 500, 503).
    """
    
    # CRITICAL: Validate mother_id before using it in the query.
    if mother_id is None:
        raise HTTPException(status_code=400, detail="Missing mother ID for personalized chat.")
    
    try:
        # Ensure the ID is a proper integer for the DB query, 
        # handling cases where it might be passed as a string.
        mother_id_int = int(mother_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mother ID format. Must be an integer.")

    if supabase is None:
        raise HTTPException(status_code=503, detail="Database service is unavailable.")
    
    try:
        # Use SUPABASE_MOTHERS_TABLE (defined in your main.py environment)
        response = (
            supabase.table(SUPABASE_MOTHERS_TABLE)
            .select("name,delivered_at") 
            .eq('id', mother_id_int)
            .single()
            .execute()
        )
        
        user_profile = response.data
        
        # This check is mostly defensive, as .single() usually handles the 404 case.
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"Mother with ID '{mother_id_int}' not found.")

        # --- Enforce Required Fields ---
        required_fields = ["name", "delivered_at"]
        
        for field in required_fields:
            if user_profile.get(field) is None:
                print(f"Missing data error for mother {mother_id_int}: '{field}' is null or missing.")
                raise HTTPException(
                    status_code=500, 
                    detail=f"User profile incomplete. Missing required field: '{field}'."
                )
        
        # --- Calculate Age in Weeks from delivered_at ---
        delivered_at_str = user_profile["delivered_at"]
        delivered_date = None
        
        try:
            # Handle ISO format from Supabase (e.g., '2023-11-16T08:00:00+00:00')
            delivered_date = datetime.fromisoformat(delivered_at_str.replace("Z", "+00:00"))
        except ValueError:
             # Fallback to the format from llm_service.py 'YYYY-MM-DD HH:MM:SS+00'
            try:
                delivered_date = datetime.strptime(delivered_at_str, "%Y-%m-%d %H:%M:%S%z")
            except ValueError:
                print(f"Unparseable delivered_at format: {delivered_at_str}")
                raise HTTPException(
                    status_code=500, 
                    detail="User profile contains unparseable 'delivered_at' date format."
                )

        # Get current time in UTC
        now_utc = datetime.now(timezone.utc)
        
        # Ensure delivered_date is in UTC for the time difference calculation
        delivered_date_utc = delivered_date.astimezone(timezone.utc)
        
        time_difference: timedelta = now_utc - delivered_date_utc
        # Prevent negative age if the date is in the future
        baby_age_weeks = max(0, round(time_difference.days / 7))
        
        return {
            "user_name": user_profile["name"],
            "baby_age_weeks": baby_age_weeks, 
        }

    except APIError as e:
        # Catching the exception raised by .single() when no rows are found
        error_message = str(e)
        if "No rows returned" in error_message or "not found" in error_message:
            raise HTTPException(status_code=404, detail=f"Mother with ID '{mother_id_int}' not found.")
        
        print(f"Unexpected Supabase query error for ID {mother_id_int}: {error_message}")
        raise HTTPException(status_code=500, detail="An internal database error occurred.")
    except HTTPException:
        # Re-raise exceptions raised internally
        raise
    except Exception as e:
        # Catch other unexpected errors
        print(f"General database error for ID {mother_id_int}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during data retrieval.")
    
def _build_chat_context(mother_id: int) -> tuple[str, dict]:
    """
    Fetches mother profile and all intake answers, formats them for the LLM.

    Returns: (context_string, user_data_dict)
    """
    if mother_id is None:
        raise HTTPException(status_code=400, detail="Missing mother ID for personalized chat.")
    
    try:
        # These utility functions are assumed to be present and working:
        mother_profile = _fetch_mother_profile(mother_id) 
        qa_pairs = _fetch_answer_pairs(mother_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database retrieval error: {e}")

    # 1. Calculate Postpartum Age
    delivered_at_str = mother_profile.get("delivered_at")
    postpartum_weeks = 0
    
    if delivered_at_str:
        try:
            delivered_dt = datetime.fromisoformat(delivered_at_str.replace("Z", "+00:00"))
            delivered_dt_utc = delivered_dt.astimezone(timezone.utc)
            
            now_utc = datetime.now(timezone.utc)
            time_difference: timedelta = now_utc - delivered_dt_utc
            postpartum_weeks = max(0, round(time_difference.days / 7))
        except ValueError:
            pass # Age remains 0 if date is unparseable

    # 2. Format QA Pairs Summary
    qa_summary = "\n".join(
        [
            f"Q: {pair['question']} A: {pair['answer']}"
            for pair in qa_pairs
        ]
    )

    # 3. Construct the Context String for the LLM
    context_prefix = (
        f"The user's name is **{mother_profile.get('name', 'mama')}** and their baby is approximately "
        f"**{postpartum_weeks} weeks old**. Use this information to personalize your response. "
    )
    
    context_intake = (
        "\n\nTheir intake answers provide further context on their recovery status:\n"
        "--- START INTAKE DATA ---\n"
        f"{qa_summary}"
        "\n--- END INTAKE DATA ---\n"
        "Reference this intake data to provide highly relevant and safe advice. For example, "
        "if they mention a high pain score or heavy bleeding in the intake, use the CRITICAL RULE "
        "even if the current question is benign. Prioritize safety based on the most severe answer found."
    )
    
    user_data = {
        "user_name": mother_profile.get('name'),
        "baby_age_weeks": postpartum_weeks,
        "intake_questions_answered": len(qa_pairs),
    }

    return context_prefix + context_intake, user_data

@app.get("/api/mothers/{mother_id}/profile")
def get_mother_profile_detail(mother_id: int):
    profile = _fetch_mother_profile(mother_id)
    answers = _fetch_answer_pairs(mother_id)
    return {"profile": profile, "answers": answers}


@app.post("/api/mothers/{mother_id}/retake")
def reset_mother_answers(mother_id: int):
    resp = (
        supabase.table(SUPABASE_ANSWERS_TABLE)
        .delete()
        .eq("mother_id", mother_id)
        .execute()
    )
    error = _resp_error(resp)
    if error:
        raise HTTPException(status_code=500, detail=str(error))
    return {"status": "ok"}
