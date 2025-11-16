import argparse
import cv2
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import platform

# ============================================================
#  CONFIG
# ============================================================
# Choose which exercise to track:
# Level 1:
#   "breathing", "pelvic_floor", "pelvic_tilt", "heel_slide",
#   "glute_bridge", "walking"
# Level 2:
#   "bodyweight_squat", "stationary_lunge", "bird_dog",
#   "dead_bug", "modified_plank", "bent_over_row",
#   "bicep_curl", "overhead_press"
# Level 3:
#   "goblet_squat", "weighted_lunge", "single_leg_deadlift",
#   "squat_jump", "run_intervals", "hiit"
CURRENT_EXERCISE = "overhead_press"
SESSION_DURATION_SECONDS = 6 * 60  # auto-end session after 6 minutes

VOICE_ENABLED = True
SPEECH_INTERVAL = 3.0   # seconds between spoken corrections

# ============================================================
#  MEDIAPIPE SETUP
# ============================================================
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

LS = mp_pose.PoseLandmark.LEFT_SHOULDER.value
RS = mp_pose.PoseLandmark.RIGHT_SHOULDER.value
LH = mp_pose.PoseLandmark.LEFT_HIP.value
RH = mp_pose.PoseLandmark.RIGHT_HIP.value
LK = mp_pose.PoseLandmark.LEFT_KNEE.value
LA = mp_pose.PoseLandmark.LEFT_ANKLE.value
LW = mp_pose.PoseLandmark.LEFT_WRIST.value
RA = mp_pose.PoseLandmark.RIGHT_ANKLE.value
LE = mp_pose.PoseLandmark.LEFT_ELBOW.value

# ============================================================
#  TTS SETUP (mac-friendly)
# ============================================================
if VOICE_ENABLED:
    try:
        if platform.system() == "Darwin":
            tts_engine = pyttsx3.init("nsss")
        else:
            tts_engine = pyttsx3.init()
        tts_engine.setProperty("rate", 180)
        tts_engine.setProperty("volume", 1.0)
    except Exception as e:
        print("⚠️  Could not initialize pyttsx3:", e)
        VOICE_ENABLED = False
        tts_engine = None
else:
    tts_engine = None


def speak(text: str):
    if not VOICE_ENABLED or not text:
        return
    try:
        tts_engine.stop()
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        print("⚠️  TTS error:", e)


# ============================================================
#  GEOMETRY + SCORING
# ============================================================
def calculate_angle(a, b, c):
    """Angle at point b given points a, b, c in pixel coords."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    c = np.array(c, dtype=float)
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-6
    cosine = np.dot(ba, bc) / denom
    cosine = np.clip(cosine, -1.0, 1.0)
    return np.degrees(np.arccos(cosine))


def get_xy(landmarks, idx, shape):
    h, w, _ = shape
    lm = landmarks[idx]
    return np.array([lm.x * w, lm.y * h], dtype=float)


def score_range(value, lo, hi, margin=20.0):
    """
    Returns a score in [0,1] based on how close value is to the [lo, hi] range.
      - 1.0 in the middle of the range
      - ~0.5 near the edges
      - 0.0 when farther than 'margin' outside the range
    """
    if lo <= value <= hi:
        mid = 0.5 * (lo + hi)
        half = 0.5 * (hi - lo)
        if half <= 0:
            return 1.0
        return max(0.0, 1.0 - abs(value - mid) / half)
    if value < lo:
        diff = lo - value
    else:
        diff = value - hi
    return max(0.0, 1.0 - diff / margin)


# ============================================================
#  LEVEL 1 EXERCISES
# ============================================================
def eval_breathing(landmarks, shape):
    feedback = [
        "Inhale wide into your ribs and back.",
        "Exhale slowly through the mouth.",
        "Keep your shoulders relaxed away from your ears.",
    ]
    return True, feedback, 1.0   # always 'good' – we just guide


def eval_pelvic_floor(landmarks, shape):
    feedback = [
        "Gently squeeze and lift around the vagina and rectum.",
        "Hold for 3 to 5 seconds, then fully relax.",
        "Do not hold your breath while you squeeze.",
    ]
    return True, feedback, 1.0


def eval_pelvic_tilt(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    rs = get_xy(landmarks, RS, shape)
    lh = get_xy(landmarks, LH, shape)
    rh = get_xy(landmarks, RH, shape)

    shoulder_mid = (ls + rs) / 2
    hip_mid = (lh + rh) / 2
    w = shape[1]

    dx = abs(shoulder_mid[0] - hip_mid[0])
    # 0 shift = perfect, 0.15*w = worst
    score = max(0.0, 1.0 - dx / (0.15 * w + 1e-6))
    score = float(np.clip(score, 0.0, 1.0))

    correct = score >= 0.7
    feedback = []

    if not correct:
        feedback.append("Keep your ribs stacked over your pelvis, not leaning too far.")
    else:
        feedback.append("Nice neutral posture. Gently rock your pelvis forward and back.")

    return correct, feedback, score


def eval_heel_slide(landmarks, shape):
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    la = get_xy(landmarks, LA, shape)

    knee_angle = calculate_angle(lh, lk, la)
    score_angle = score_range(knee_angle, 140, 180, margin=30)

    pelvis_shift = abs(lh[1] - lk[1])
    score_pelvis = max(0.0, 1.0 - pelvis_shift / (0.2 * shape[0] + 1e-6))

    score = float(np.clip(min(score_angle, score_pelvis), 0.0, 1.0))
    correct = score >= 0.7
    feedback = []

    if score_angle < 0.7:
        feedback.append("Slide your heel slowly along the floor, keep your knee pointing to the ceiling.")
    else:
        feedback.append("Straighten the leg fully, then bend back in with control.")

    if score_pelvis < 0.7:
        feedback.append("Keep your pelvis steady, avoid rocking side to side.")

    return correct, feedback, score


def eval_glute_bridge(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)

    hip_angle = calculate_angle(ls, lh, lk)  # shoulder-hip-knee
    score = score_range(hip_angle, 160, 210, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if hip_angle < 160:
        feedback.append("Lift your hips so your body makes a straight line from shoulders to knees.")
    elif hip_angle > 210:
        feedback.append("Keep your ribs soft, avoid arching your low back too much.")
    else:
        feedback.append("Nice bridge height. Keep ribs soft and glutes gently engaged.")

    return correct, feedback, score


def eval_walking(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    rs = get_xy(landmarks, RS, shape)
    lh = get_xy(landmarks, LH, shape)
    rh = get_xy(landmarks, RH, shape)

    shoulder_mid = (ls + rs) / 2
    hip_mid = (lh + rh) / 2

    dx = abs(shoulder_mid[0] - hip_mid[0])
    dy = abs(shoulder_mid[1] - hip_mid[1])

    score_balance = max(0.0, 1.0 - dx / (0.20 * shape[1] + 1e-6))
    score_shoulder_relax = max(0.0, 1.0 - dy / (0.10 * shape[0] + 1e-6))

    score = float(np.clip(min(score_balance, score_shoulder_relax), 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if score_balance < 0.7:
        feedback.append("Keep your chest stacked over your hips, not leaning too far.")
    else:
        feedback.append("Nice upright posture. Take short, easy steps.")

    if score_shoulder_relax < 0.7:
        feedback.append("Relax the shoulders and let your arms swing naturally.")

    return correct, feedback, score


# ============================================================
#  LEVEL 2 EXERCISES
# ============================================================
def eval_squat(landmarks, shape):
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    la = get_xy(landmarks, LA, shape)
    ls = get_xy(landmarks, LS, shape)

    knee_angle = calculate_angle(lh, lk, la)
    torso_angle = calculate_angle(ls, lh, lk)

    score_knee = score_range(knee_angle, 60, 140, margin=30)
    score_torso = score_range(torso_angle, 140, 200, margin=40)

    score = float(np.clip(min(score_knee, score_torso), 0.0, 1.0))
    correct = score >= 0.7
    feedback = []

    if score_knee < 0.7:
        if knee_angle > 140:
            feedback.append("Sit a bit lower into your squat, like sitting back into a chair.")
        else:
            feedback.append("You are going very deep, only go as low as feels safe.")
    else:
        feedback.append("Good squat depth, keep weight in the middle of your feet.")

    if score_torso < 0.7:
        feedback.append("Keep your chest more lifted, avoid collapsing forward.")

    return correct, feedback, score


def eval_lunge(landmarks, shape):
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    la = get_xy(landmarks, LA, shape)

    knee_angle = calculate_angle(lh, lk, la)
    score_angle = score_range(knee_angle, 70, 110, margin=25)

    knee_foot_x = abs(lk[0] - la[0])
    score_stack = max(0.0, 1.0 - knee_foot_x / (0.15 * shape[1] + 1e-6))

    score = float(np.clip(min(score_angle, score_stack), 0.0, 1.0))
    correct = score >= 0.7
    feedback = []

    if score_angle < 0.7:
        feedback.append("Bend your front knee so it is roughly over your ankle.")
    else:
        feedback.append("Nice lunge position, keep your front knee over your ankle.")

    if score_stack < 0.7:
        feedback.append("Keep your front knee stacked over your foot, not drifting inward or outward.")

    return correct, feedback, score


def eval_bird_dog(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    rs = get_xy(landmarks, RS, shape)
    lh = get_xy(landmarks, LH, shape)
    rh = get_xy(landmarks, RH, shape)
    lw = get_xy(landmarks, LW, shape)
    ra = get_xy(landmarks, RA, shape)

    feedback = []

    # level shoulders/hips
    sd = abs(ls[1] - rs[1])
    hd = abs(lh[1] - rh[1])
    score_level = max(0.0, 1.0 - max(sd, hd) / (0.05 * shape[0] + 1e-6))

    trunk_vec = (rh + lh) / 2 - (rs + ls) / 2
    arm_vec = lw - ls
    leg_vec = ra - rh

    def ang(v1, v2):
        v1 = v1 / (np.linalg.norm(v1) + 1e-6)
        v2 = v2 / (np.linalg.norm(v2) + 1e-6)
        return np.degrees(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)))

    arm_angle = ang(trunk_vec, arm_vec)
    leg_angle = ang(trunk_vec, leg_vec)

    score_arm = max(0.0, 1.0 - arm_angle / 40.0)
    score_leg = max(0.0, 1.0 - leg_angle / 40.0)

    score = float(np.clip(min(score_level, score_arm, score_leg), 0.0, 1.0))
    correct = score >= 0.7

    if score_level < 0.7:
        feedback.append("Keep your hips and shoulders level, avoid tilting to one side.")
    else:
        feedback.append("Nice level hips and shoulders.")

    if score_arm < 0.7:
        feedback.append("Reach your arm straight forward from your shoulder, not out to the side.")
    if score_leg < 0.7:
        feedback.append("Reach your leg straight back from your hip, not out to the side.")

    if correct:
        feedback.append("Great bird-dog. Keep your core gently engaged and breathe.")

    return correct, feedback, score


def eval_dead_bug(landmarks, shape):
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    la = get_xy(landmarks, LA, shape)
    ls = get_xy(landmarks, LS, shape)
    le = get_xy(landmarks, LE, shape)
    lw = get_xy(landmarks, LW, shape)

    hip_knee_angle = calculate_angle(lh, lk, la)
    shoulder_angle = calculate_angle(ls, le, lw)

    score_legs = score_range(hip_knee_angle, 70, 110, margin=25)
    score_arms = score_range(shoulder_angle, 70, 150, margin=30)

    score = float(np.clip(min(score_legs, score_arms), 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if score_legs < 0.7:
        feedback.append("Bend your hips and knees to about 90 degrees over your hips.")
    else:
        feedback.append("Good leg position, keep your shins parallel to the floor.")

    if score_arms < 0.7:
        feedback.append("Reach your arms more toward the ceiling with soft elbows.")
    else:
        feedback.append("Nice arm position, keep ribs heavy toward the mat.")

    return correct, feedback, score


def eval_modified_plank(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)

    body_angle = calculate_angle(ls, lh, lk)
    score = score_range(body_angle, 160, 200, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if correct:
        feedback.append("Nice plank line. Keep your neck long and breathe steadily.")
    else:
        feedback.append("Aim for a straight line from shoulders through hips to knees.")

    return correct, feedback, score


def eval_bent_over_row(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)

    torso_angle = calculate_angle(lk, lh, ls)
    score = score_range(torso_angle, 120, 180, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if correct:
        feedback.append("Nice hip hinge. Keep your back flat as you row.")
    else:
        feedback.append("Hinge from your hips with a flat back, not rounding.")

    return correct, feedback, score


def eval_bicep_curl(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    le = get_xy(landmarks, LE, shape)
    lw = get_xy(landmarks, LW, shape)

    elbow_angle = calculate_angle(ls, le, lw)
    score = score_range(elbow_angle, 40, 150, margin=40)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if elbow_angle < 40:
        feedback.append("Lower your hands a bit and fully straighten without locking.")
    elif elbow_angle > 150:
        feedback.append("Curl your hands up toward your shoulders with control.")
    else:
        feedback.append("Great curl range. Keep your elbows close to your ribs.")

    return correct, feedback, score


def eval_overhead_press(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    le = get_xy(landmarks, LE, shape)
    lw = get_xy(landmarks, LW, shape)

    elbow_angle = calculate_angle(ls, le, lw)
    score = score_range(elbow_angle, 60, 160, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if score < 0.7:
        feedback.append("Start with elbows under wrists and press up keeping ribs down.")
    else:
        feedback.append("Press up toward the ceiling, keeping ribs down and spine neutral.")

    return correct, feedback, score


# ============================================================
#  LEVEL 3 EXERCISES
# ============================================================
def eval_single_leg_deadlift(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    ra = get_xy(landmarks, RA, shape)

    torso_angle = calculate_angle(lk, lh, ls)
    score_torso = score_range(torso_angle, 120, 180, margin=30)

    body_vec = ls - lh
    leg_vec = ra - lh
    body_vec = body_vec / (np.linalg.norm(body_vec) + 1e-6)
    leg_vec = leg_vec / (np.linalg.norm(leg_vec) + 1e-6)
    angle = np.degrees(np.arccos(np.clip(np.dot(body_vec, leg_vec), -1.0, 1.0)))
    score_leg = max(0.0, 1.0 - angle / 40.0)

    score = float(np.clip(min(score_torso, score_leg), 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if score_torso < 0.7:
        feedback.append("Hinge from your hips with a long spine, like a see-saw.")
    else:
        feedback.append("Nice hip hinge. Keep your back long and core engaged.")

    if score_leg < 0.7:
        feedback.append("Reach your back leg in line with your torso, not hanging down.")

    return correct, feedback, score


def eval_squat_jump(landmarks, shape):
    correct, feedback, score = eval_squat(landmarks, shape)
    feedback.insert(0, "Focus on a soft landing with knees tracking over toes.")
    return correct, feedback, score


def eval_run_intervals(landmarks, shape):
    return eval_walking(landmarks, shape)


def eval_hiit(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    rs = get_xy(landmarks, RS, shape)
    lh = get_xy(landmarks, LH, shape)
    rh = get_xy(landmarks, RH, shape)

    shoulder_mid = (ls + rs) / 2
    hip_mid = (lh + rh) / 2

    dx = abs(shoulder_mid[0] - hip_mid[0])
    score = max(0.0, 1.0 - dx / (0.25 * shape[1] + 1e-6))
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= 0.7

    feedback = []
    if correct:
        feedback.append("Nice upright posture. Keep moves controlled and breathe.")
    else:
        feedback.append("Keep your chest more stacked over your hips while you move.")

    return correct, feedback, score


# ============================================================
#  EXERCISE REGISTRY
# ============================================================
EXERCISE_REGISTRY = {
    # Level 1
    "breathing":          {"label": "Breathing",          "fn": eval_breathing},
    "pelvic_floor":       {"label": "Pelvic Floor",       "fn": eval_pelvic_floor},
    "pelvic_tilt":        {"label": "Pelvic Tilt",        "fn": eval_pelvic_tilt},
    "heel_slide":         {"label": "Heel Slide",         "fn": eval_heel_slide},
    "glute_bridge":       {"label": "Glute Bridge",       "fn": eval_glute_bridge},
    "walking":            {"label": "Walking",            "fn": eval_walking},

    # Level 2
    "bodyweight_squat":   {"label": "Bodyweight Squat",   "fn": eval_squat},
    "stationary_lunge":   {"label": "Stationary Lunge",   "fn": eval_lunge},
    "bird_dog":           {"label": "Bird-Dog",           "fn": eval_bird_dog},
    "dead_bug":           {"label": "Dead Bug",           "fn": eval_dead_bug},
    "modified_plank":     {"label": "Modified Plank",     "fn": eval_modified_plank},
    "bent_over_row":      {"label": "Bent-Over Row",      "fn": eval_bent_over_row},
    "bicep_curl":         {"label": "Bicep Curl",         "fn": eval_bicep_curl},
    "overhead_press":     {"label": "Overhead Press",     "fn": eval_overhead_press},

    # Level 3
    "goblet_squat":       {"label": "Goblet Squat",       "fn": eval_squat},
    "weighted_lunge":     {"label": "Weighted Lunge",     "fn": eval_lunge},
    "single_leg_deadlift":{"label": "Single-Leg Deadlift","fn": eval_single_leg_deadlift},
    "squat_jump":         {"label": "Squat Jump",         "fn": eval_squat_jump},
    "run_intervals":      {"label": "Run/Walk",           "fn": eval_run_intervals},
    "hiit":               {"label": "HIIT Posture",       "fn": eval_hiit},
}


# ============================================================
#  MAIN LOOP
# ============================================================
def main(selected_exercise: str | None = None):
    backend_flag = None
    system_name = platform.system()
    if system_name == "Darwin":
        backend_flag = cv2.CAP_AVFOUNDATION
    elif system_name == "Windows":
        backend_flag = cv2.CAP_DSHOW

    if backend_flag is not None:
        cap = cv2.VideoCapture(1, backend_flag)
    else:
        cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return

    last_speech_time = 0.0
    session_start = time.time()

    exercise_key = (selected_exercise or CURRENT_EXERCISE) or "glute_bridge"
    cfg = EXERCISE_REGISTRY.get(exercise_key, EXERCISE_REGISTRY["glute_bridge"])
    window_title = cfg["label"]
    evaluator = cfg["fn"]

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while cap.isOpened():
            if time.time() - session_start >= SESSION_DURATION_SECONDS:
                print("[INFO] Majka session complete - auto closing after 6 minutes.")
                break
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            status_text = "NO POSE"
            status_color = (128, 128, 128)
            feedback = []
            score = 0.0

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # --- Evaluate form ---
                correct, feedback, score = evaluator(landmarks, frame.shape)
                score = float(np.clip(score, 0.0, 1.0))

                # Map score 0→1 to RED→GREEN (BGR)
                g = int(255 * score)
                r = int(255 * (1.0 - score))
                line_color = (0, g, r)

                status_text = "CORRECT" if score >= 0.7 else "ADJUST"
                status_color = line_color

                # --- Draw skeleton (heat-map color, THICC lines & circles) ---
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(
                        color=line_color,
                        thickness=8,        # thicker outline at joints
                        circle_radius=8     # bigger default joint circles
                    ),
                    connection_drawing_spec=mp_drawing.DrawingSpec(
                        color=line_color,
                        thickness=6,        # thicker lines between joints
                        circle_radius=4
                    ),
                )

                # Extra: large solid dots at every landmark (heatmap feel)
                h, w, _ = frame.shape
                for lm in landmarks:
                    x = int(lm.x * w)
                    y = int(lm.y * h)
                    cv2.circle(frame, (x, y), 12, line_color, -1)  # radius 12 = big dots

                # --- Voice feedback when off ---
                now = time.time()
                if score < 0.7 and feedback and now - last_speech_time > SPEECH_INTERVAL:
                    speak(feedback[0])
                    last_speech_time = now

            # Status bar
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 0), -1)
            cv2.putText(
                frame,
                f"{window_title}: {status_text}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                status_color,
                2,
                cv2.LINE_AA,
            )

            # Feedback overlay
            y = 60
            for line in feedback[:3]:
                cv2.putText(
                    frame,
                    line,
                    (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                y += 24

            cv2.imshow(window_title, frame)
            if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                break
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Majka guided session tracker.")
    parser.add_argument(
        "--exercise",
        type=str,
        default=CURRENT_EXERCISE,
        help="Exercise key from EXERCISE_REGISTRY (e.g., bird_dog)",
    )
    args = parser.parse_args()
    main(args.exercise)
