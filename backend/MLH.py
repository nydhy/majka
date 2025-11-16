import argparse
import cv2
import mediapipe as mp
import numpy as np
import time
import pyttsx3
import platform
import threading

# ============================================================
#  CONFIG
# ============================================================
CURRENT_EXERCISE = "overhead_press"
SESSION_DURATION_SECONDS = 6 * 60  # auto-end session after 6 minutes

VOICE_ENABLED = True
SPEECH_INTERVAL = 2.0   # seconds between spoken corrections

SMOOTHING_FACTOR = 0.2
GOOD_THRESH = 0.80
EXCELLENT_THRESH = 0.90
MASTERED_THRESH = 0.999
REP_SCORE_THRESHOLD = 0.80

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
        print("??  Could not initialize pyttsx3:", e)
        VOICE_ENABLED = False
        tts_engine = None
else:
    tts_engine = None

tts_lock = threading.Lock()


def _speak_thread_safe(text: str):
    if not tts_engine or not text:
        return
    if not tts_lock.acquire(blocking=False):
        return
    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        print("??  TTS error:", e)
    finally:
        if tts_lock.locked():
            tts_lock.release()


def speak(text: str):
    if not VOICE_ENABLED or not text or not tts_engine:
        return
    try:
        threading.Thread(target=_speak_thread_safe, args=(text,), daemon=True).start()
    except Exception as e:
        print("??  Could not start TTS thread:", e)


# ============================================================
#  BREATHING COACH
# ============================================================
class BreathingCoach:
    """Guided breathing session that calibrates and then guides in real time."""

    def __init__(self, session_duration_sec=120):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.app_state = "CALIBRATING"
        self.breath_state = "Welcome"
        self.session_duration_sec = session_duration_sec
        self.session_start_time = None
        self.session_complete = False

        self.calibration_cycles_goal = 3
        self.calibration_breaths = []
        self.inhale_start_time = None
        self.exhale_start_time = None
        self.last_calib_state = "Exhale"

        self.inhale_duration = 4.0
        self.exhale_duration = 6.0
        self.cycle_duration = self.inhale_duration + self.exhale_duration
        self.pacer_start_time = None

        self.shoulder_y_prev = 0
        self.MOVEMENT_THRESHOLD = 0.005
        self.SHRUG_THRESHOLD = 0.015
        self.shrug_warning = False

    def _run_calibration_logic(self, movement, current_time):
        if movement > self.MOVEMENT_THRESHOLD:
            self.breath_state = "Inhale"
        elif movement < -self.MOVEMENT_THRESHOLD:
            self.breath_state = "Exhale"

        if self.breath_state == "Inhale" and self.last_calib_state == "Exhale":
            if self.exhale_start_time and self.inhale_start_time:
                inhale_dur = self.exhale_start_time - self.inhale_start_time
                exhale_dur = current_time - self.exhale_start_time
                self.calibration_breaths.append((inhale_dur, exhale_dur))
            self.inhale_start_time = current_time
            self.last_calib_state = "Inhale"
        elif self.breath_state == "Exhale" and self.last_calib_state == "Inhale":
            self.exhale_start_time = current_time
            self.last_calib_state = "Exhale"

        if len(self.calibration_breaths) >= self.calibration_cycles_goal:
            self._calculate_pacer()
            self.app_state = "GUIDING"

    def _calculate_pacer(self):
        if self.calibration_breaths:
            inhales = [b[0] for b in self.calibration_breaths]
            exhales = [b[1] for b in self.calibration_breaths]
            self.inhale_duration = float(np.clip(np.mean(inhales), 2.0, 10.0))
            self.exhale_duration = float(np.clip(np.mean(exhales), 2.0, 10.0))
        self.cycle_duration = self.inhale_duration + self.exhale_duration
        now = time.time()
        self.session_start_time = now
        self.pacer_start_time = now

    def _run_guiding_logic(self, current_time):
        if not self.pacer_start_time:
            self.pacer_start_time = current_time
        elapsed_since_start = current_time - self.pacer_start_time
        time_in_cycle = elapsed_since_start % self.cycle_duration
        self.breath_state = (
            "Inhale" if time_in_cycle < self.inhale_duration else "Exhale"
        )

    def _check_shrugs(self, movement):
        self.shrug_warning = movement > self.SHRUG_THRESHOLD

    def process_frame(self, frame):
        current_time = time.time()
        frame = cv2.flip(frame, 1)
        frame_h, frame_w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if self.session_start_time and not self.session_complete:
            if current_time - self.session_start_time > self.session_duration_sec:
                self.session_complete = True
                self.app_state = "COMPLETE"

        movement = 0.0
        if results.pose_landmarks and not self.session_complete:
            landmarks = results.pose_landmarks.landmark
            shoulder_y = (
                landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y
                + landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
            ) / 2
            if self.shoulder_y_prev == 0:
                self.shoulder_y_prev = shoulder_y
            movement = self.shoulder_y_prev - shoulder_y
            self.shoulder_y_prev = shoulder_y
            self._check_shrugs(movement)
            if self.app_state == "CALIBRATING":
                self._run_calibration_logic(movement, current_time)
            elif self.app_state == "GUIDING":
                self._run_guiding_logic(current_time)
        elif not results.pose_landmarks:
            self.app_state = "CALIBRATING"
            self.breath_state = "Welcome"
            self.calibration_breaths = []
            self.inhale_start_time = None
            self.exhale_start_time = None
            self.pacer_start_time = None
            self.session_start_time = None
            self.shoulder_y_prev = 0

        return self._draw_ui(frame, frame_h, frame_w)

    def _draw_ui(self, frame, frame_h, frame_w):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame_w, 90), (60, 60, 60), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        if self.session_complete:
            feedback_text = "Great job! Session complete."
            color = (170, 255, 170)
        elif self.shrug_warning:
            feedback_text = "Gently relax your shoulders..."
            color = (150, 150, 255)
        elif self.app_state == "CALIBRATING":
            feedback_text = (
                f"Breathe normally... (Calibrating {len(self.calibration_breaths)+1}/"
                f"{self.calibration_cycles_goal})"
            )
            color = (255, 255, 180)
        elif self.app_state == "GUIDING":
            if self.breath_state == "Inhale":
                feedback_text = "Inhale..."
                color = (230, 255, 230)
            else:
                feedback_text = "Exhale..."
                color = (255, 230, 255)
        else:
            feedback_text = "Welcome. Please find a relaxed position."
            color = (255, 255, 255)

        cv2.putText(
            frame,
            feedback_text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            color,
            2,
            cv2.LINE_AA,
        )

        if self.session_complete:
            timer_text = "Time: Complete!"
        elif self.session_start_time:
            remaining = max(
                0, int(self.session_duration_sec - (time.time() - self.session_start_time))
            )
            minutes = remaining // 60
            seconds = remaining % 60
            timer_text = f"Time: {minutes:02d}:{seconds:02d}"
        else:
            minutes = self.session_duration_sec // 60
            seconds = self.session_duration_sec % 60
            timer_text = f"Time: {minutes:02d}:{seconds:02d}"

        cv2.putText(
            frame,
            timer_text,
            (frame_w - 180, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    def close(self):
        self.pose.close()


# ============================================================
#  GEOMETRY + SCORING
# ============================================================
def calculate_angle(a, b, c):
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
    if lo <= value <= hi:
        mid = 0.5 * (lo + hi)
        half = 0.5 * (hi - lo)
        if half <= 0:
            return 1.0
        return max(0.0, 1.0 - abs(value - mid) / half)
    diff = lo - value if value < lo else value - hi
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
    return True, feedback, 1.0


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
    score = max(0.0, 1.0 - dx / (0.15 * w + 1e-6))
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= GOOD_THRESH
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
    score_angle = score_range(knee_angle, 80, 180, margin=30)
    pelvis_shift = abs(lh[1] - lk[1])
    score_pelvis = max(0.0, 1.0 - pelvis_shift / (0.2 * shape[0] + 1e-6))
    score = float(np.clip(min(score_angle, score_pelvis), 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if score_angle < GOOD_THRESH:
        feedback.append("Slide your heel slowly along the floor, keep your knee pointing to the ceiling.")
    else:
        feedback.append("Straighten the leg fully, then bend back in with control.")
    if score_pelvis < GOOD_THRESH:
        feedback.append("Keep your pelvis steady, avoid rocking side to side.")
    return correct, feedback, score


def eval_glute_bridge(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    hip_angle = calculate_angle(ls, lh, lk)
    score = score_range(hip_angle, 160, 210, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= GOOD_THRESH
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
    correct = score >= GOOD_THRESH
    feedback = []
    if score_balance < GOOD_THRESH:
        feedback.append("Keep your chest stacked over your hips, not leaning too far.")
    else:
        feedback.append("Nice upright posture. Take short, easy steps.")
    if score_shoulder_relax < GOOD_THRESH:
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
    score_knee = score_range(knee_angle, 60, 170, margin=30)
    score_torso = score_range(torso_angle, 140, 200, margin=40)
    score = float(np.clip(min(score_knee, score_torso), 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if score_knee < 0.7 and knee_angle > 140:
        feedback.append("Sit a bit lower into your squat, like sitting back into a chair.")
    elif score_knee < 0.7 and knee_angle < 60:
        feedback.append("You are going very deep, only go as low as feels safe.")
    else:
        feedback.append("Good squat depth, keep weight in the middle of your feet.")
    if score_torso < GOOD_THRESH:
        feedback.append("Keep your chest more lifted, avoid collapsing forward.")
    return correct, feedback, score


def eval_lunge(landmarks, shape):
    lh = get_xy(landmarks, LH, shape)
    lk = get_xy(landmarks, LK, shape)
    la = get_xy(landmarks, LA, shape)
    knee_angle = calculate_angle(lh, lk, la)
    score_angle = score_range(knee_angle, 70, 130, margin=25)
    knee_foot_x = abs(lk[0] - la[0])
    score_stack = max(0.0, 1.0 - knee_foot_x / (0.15 * shape[1] + 1e-6))
    score = float(np.clip(min(score_angle, score_stack), 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if score_angle < GOOD_THRESH:
        feedback.append("Bend your front knee so it is roughly over your ankle.")
    else:
        feedback.append("Nice lunge position, keep your front knee over your ankle.")
    if score_stack < GOOD_THRESH:
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
    correct = score >= GOOD_THRESH
    if score_level < GOOD_THRESH:
        feedback.append("Keep your hips and shoulders level, avoid tilting to one side.")
    else:
        feedback.append("Nice level hips and shoulders.")
    if score_arm < GOOD_THRESH:
        feedback.append("Reach your arm straight forward from your shoulder, not out to the side.")
    if score_leg < GOOD_THRESH:
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
    score_legs = score_range(hip_knee_angle, 70, 180, margin=25)
    score_arms = score_range(shoulder_angle, 70, 180, margin=30)
    score = float(np.clip(min(score_legs, score_arms), 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if score_legs < 0.7 and hip_knee_angle < 70:
        feedback.append("Bend your knees to about 90 degrees over your hips.")
    elif score_legs < 0.7 and hip_knee_angle > 170:
        feedback.append("Extend your leg fully, then return to 90 degrees.")
    else:
        feedback.append("Good leg position, keep your shins parallel to the floor.")
    if score_arms < GOOD_THRESH:
        feedback.append("Reach your arms toward the ceiling with soft elbows.")
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
    correct = score >= GOOD_THRESH
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
    le = get_xy(landmarks, LE, shape)
    lw = get_xy(landmarks, LW, shape)
    torso_angle = calculate_angle(lk, lh, ls)
    score_torso = score_range(torso_angle, 120, 180, margin=30)
    elbow_angle = calculate_angle(ls, le, lw)
    score_elbow = score_range(elbow_angle, 60, 170, margin=40)
    score = float(np.clip(min(score_torso, score_elbow), 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if score_torso < GOOD_THRESH:
        feedback.append("Hinge from your hips with a flat back, not rounding.")
    else:
        feedback.append("Nice hip hinge. Keep your back flat as you row.")
    if score_elbow < 0.7 and elbow_angle > 150:
        feedback.append("Pull your elbows back, squeezing shoulder blades.")
    elif score_elbow < 0.7 and elbow_angle < 70:
        feedback.append("Lower the weight fully with control.")
    return correct, feedback, score


def eval_bicep_curl(landmarks, shape):
    ls = get_xy(landmarks, LS, shape)
    le = get_xy(landmarks, LE, shape)
    lw = get_xy(landmarks, LW, shape)
    elbow_angle = calculate_angle(ls, le, lw)
    score = score_range(elbow_angle, 40, 150, margin=40)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= GOOD_THRESH
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
    score = score_range(elbow_angle, 70, 170, margin=30)
    score = float(np.clip(score, 0.0, 1.0))
    correct = score >= GOOD_THRESH
    feedback = []
    if elbow_angle < 70:
        feedback.append("Start with elbows bent, hands near shoulders.")
    elif elbow_angle > 170:
        feedback.append("Press fully up, but avoid locking your elbows.")
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
    correct = score >= GOOD_THRESH
    feedback = []
    if score_torso < GOOD_THRESH:
        feedback.append("Hinge from your hips with a long spine, like a see-saw.")
    else:
        feedback.append("Nice hip hinge. Keep your back long and core engaged.")
    if score_leg < GOOD_THRESH:
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
    correct = score >= GOOD_THRESH
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
    "breathing": {"label": "Breathing Coach", "type": "breathing"},
    "pelvic_floor": {"label": "Pelvic Floor", "fn": eval_pelvic_floor},
    "pelvic_tilt": {"label": "Pelvic Tilt", "fn": eval_pelvic_tilt},
    "heel_slide": {"label": "Heel Slide", "fn": eval_heel_slide},
    "glute_bridge": {"label": "Glute Bridge", "fn": eval_glute_bridge},
    "walking": {"label": "Walking", "fn": eval_walking},
    "bodyweight_squat": {"label": "Bodyweight Squat", "fn": eval_squat},
    "stationary_lunge": {"label": "Stationary Lunge", "fn": eval_lunge},
    "bird_dog": {"label": "Bird-Dog", "fn": eval_bird_dog},
    "dead_bug": {"label": "Dead Bug", "fn": eval_dead_bug},
    "modified_plank": {"label": "Modified Plank", "fn": eval_modified_plank},
    "bent_over_row": {"label": "Bent-Over Row", "fn": eval_bent_over_row},
    "bicep_curl": {"label": "Bicep Curl", "fn": eval_bicep_curl},
    "overhead_press": {"label": "Overhead Press", "fn": eval_overhead_press},
    "goblet_squat": {"label": "Goblet Squat", "fn": eval_squat},
    "weighted_lunge": {"label": "Weighted Lunge", "fn": eval_lunge},
    "single_leg_deadlift": {"label": "Single-Leg Deadlift", "fn": eval_single_leg_deadlift},
    "squat_jump": {"label": "Squat Jump", "fn": eval_squat_jump},
    "run_intervals": {"label": "Run/Walk", "fn": eval_run_intervals},
    "hiit": {"label": "HIIT Posture", "fn": eval_hiit},
}


def _resolve_capture():
    backend_flag = None
    system_name = platform.system()
    if system_name == "Darwin":
        backend_flag = cv2.CAP_AVFOUNDATION
    elif system_name == "Windows":
        backend_flag = cv2.CAP_DSHOW
    if backend_flag is not None:
        cap = cv2.VideoCapture(0, backend_flag)
    else:
        cap = cv2.VideoCapture(0)
    return cap


# ============================================================
#  MAIN LOOP
# ============================================================
def main(selected_exercise: str | None = None):
    cap = _resolve_capture()
    if not cap.isOpened():
        print("? Could not open camera")
        return

    last_speech_time = 0.0
    global_score = 0.0
    last_level = None
    session_start = time.time()

    exercise_key = (selected_exercise or CURRENT_EXERCISE) or "glute_bridge"
    cfg = EXERCISE_REGISTRY.get(exercise_key, EXERCISE_REGISTRY["glute_bridge"])
    window_title = cfg["label"]
    evaluator = cfg.get("fn")
    is_breathing = cfg.get("type") == "breathing"
    breathing_coach = BreathingCoach(SESSION_DURATION_SECONDS) if is_breathing else None

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

            if is_breathing and breathing_coach:
                processed = breathing_coach.process_frame(frame)
                cv2.imshow(window_title, processed)
                if (
                    cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1
                    or cv2.waitKey(1) & 0xFF == ord("q")
                    or breathing_coach.session_complete
                ):
                    break
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            status_text = "NO POSE"
            status_color = (128, 128, 128)
            feedback = []
            score = 0.0
            smooth_score = global_score

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                correct, feedback, score = evaluator(landmarks, frame.shape)
                score = float(np.clip(score, 0.0, 1.0))
                global_score = (1 - SMOOTHING_FACTOR) * global_score + SMOOTHING_FACTOR * score
                smooth_score = global_score
                score_pct = int(smooth_score * 100)

                if smooth_score >= MASTERED_THRESH:
                    level = "MASTERED"
                elif smooth_score >= EXCELLENT_THRESH:
                    level = "EXCELLENT"
                elif smooth_score >= GOOD_THRESH:
                    level = "GOOD"
                else:
                    level = "ADJUST"

                status_text = f"{level} ({score_pct}%)"
                g = int(255 * smooth_score)
                r = int(255 * (1.0 - smooth_score))
                line_color = (0, g, r)
                status_color = line_color

                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=line_color, thickness=8, circle_radius=8),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=line_color, thickness=6, circle_radius=4),
                )
                h, w, _ = frame.shape
                for lm in landmarks:
                    x = int(lm.x * w)
                    y = int(lm.y * h)
                    cv2.circle(frame, (x, y), 12, line_color, -1)

                now = time.time()
                if smooth_score < GOOD_THRESH and feedback and now - last_speech_time > SPEECH_INTERVAL:
                    speak(feedback[0])
                    last_speech_time = now
                if level != last_level and smooth_score >= GOOD_THRESH:
                    if level == "GOOD":
                        speak("Good form, keep it up.")
                    elif level == "EXCELLENT":
                        speak("Excellent form.")
                    elif level == "MASTERED":
                        speak("You have mastered this movement.")
                    last_level = level
            else:
                global_score *= (1 - SMOOTHING_FACTOR)
                smooth_score = global_score

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

            elapsed = int(time.time() - session_start)
            cv2.putText(frame, f"Time: {elapsed}s", (frame.shape[1] - 150, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

            bar_h = 20
            bar_y = frame.shape[0] - bar_h - 40
            bar_x1, bar_x2 = 10, frame.shape[1] - 10
            cv2.rectangle(frame, (bar_x1, bar_y), (bar_x2, bar_y + bar_h), (50, 50, 50), -1)
            fill_x = bar_x1 + int((bar_x2 - bar_x1) * smooth_score)
            cv2.rectangle(frame, (bar_x1, bar_y), (fill_x, bar_y + bar_h), status_color, -1)
            cv2.putText(frame, f"Form: {int(smooth_score * 100)}%", (bar_x1 + 5, bar_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            cv2.putText(
                frame,
                "Stop if you feel pain, dizziness, or pelvic pressure.",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_title, frame)
            if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                break
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    if breathing_coach:
        breathing_coach.close()


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
