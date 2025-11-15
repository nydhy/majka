import cv2
import mediapipe as mp
import time

# --- Initialization ---

# Initialize MediaPipe Pose solution
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5)

# Initialize MediaPipe Drawing utilities
mp_drawing = mp.solutions.drawing_utils

# --- Breathing State Variables ---
breath_state = "Welcome"  # "Welcome", "Inhale", "Exhale"
shrug_warning = False     # Flag for shoulder shrug warning
shoulder_y_prev = 0
breath_count = 0

# --- Tuning & Thresholds ---
# How much the shoulder has to move to trigger a state change.
MOVEMENT_THRESHOLD = 0.005
# **NEW**: A threshold for detecting a "shrug" (excessive shoulder breathing)
SHRUG_THRESHOLD = 0.015  # 3x the movement threshold. This may need tuning.

last_state_change_time = time.time()
COOLDOWN_SECONDS = 1.0  # Prevents flickering

# --- Webcam Setup ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Starting webcam feed for Majka. Press 'q' to quit.")

# --- Main Loop ---
try:
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            continue

        # 1. Flip and get dimensions
        frame = cv2.flip(frame, 1)
        frame_h, frame_w, _ = frame.shape

        # 2. Convert to RGB and process
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)

        # Reset warning flag each frame
        shrug_warning = False

        # 4. Draw pose and check breathing
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
            )

            landmarks = results.pose_landmarks.landmark
            left_shoulder_y = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y
            right_shoulder_y = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
            shoulder_y_current = (left_shoulder_y + right_shoulder_y) / 2

            current_time = time.time()
            
            if shoulder_y_prev == 0:
                shoulder_y_prev = shoulder_y_current

            # (y decreases as you go up)
            movement = shoulder_y_prev - shoulder_y_current
            
            if current_time - last_state_change_time > COOLDOWN_SECONDS:
                
                # **NEW: Check for shrugs FIRST**
                # This overrides the "inhale" if movement is too large
                if movement > SHRUG_THRESHOLD:
                    shrug_warning = True
                    breath_state = "Welcome" # Reset state
                    last_state_change_time = current_time
                
                # Check for inhale (shoulders moved slightly UP)
                elif movement > MOVEMENT_THRESHOLD:
                    if breath_state != "Inhale":
                        breath_state = "Inhale"
                        last_state_change_time = current_time
                
                # Check for exhale (shoulders moved slightly DOWN)
                elif movement < -MOVEMENT_THRESHOLD:
                    if breath_state != "Exhale":
                        breath_state = "Exhale"
                        # Count a full cycle on the exhale
                        breath_count += 1
                        last_state_change_time = current_time

            shoulder_y_prev = shoulder_y_current
            
        else:
            # If no person is detected, reset
            breath_state = "Welcome"
            shoulder_y_prev = 0

        # 5. Display Feedback UI on the frame
        # --- Draw a semi-transparent background for text ---
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame_w, 90), (60, 60, 60), -1)
        alpha = 0.7  # Transparency
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # --- Display text ---
        text_color = (255, 255, 255) # Default: White
        
        # **NEW: Gentle, postpartum-specific text**
        if shrug_warning:
            feedback_text = "Gently relax your shoulders..."
            text_color = (150, 150, 255) # Calming Lilac
        elif breath_state == "Inhale":
            feedback_text = "Inhale: Let your belly & ribs expand."
            text_color = (230, 255, 230) # Soft Mint Green
        elif breath_state == "Exhale":
            feedback_text = "Exhale: Gently 'zip up' your core."
            text_color = (255, 230, 255) # Soft Lilac
        else:
            feedback_text = "Welcome to Majka. Breathe when you're ready."

        cv2.putText(frame, feedback_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 2, cv2.LINE_AA)
        
        # Changed "Breaths" to "Cycles" - less pressure
        cv2.putText(frame, f"Cycles: {breath_count}", (frame_w - 180, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

        # 6. Display the resulting frame
        cv2.imshow('Majka - Postpartum Breathing Guide', frame)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

finally:
    # --- Cleanup ---
    print("Cleaning up...")
    pose.close()
    cap.release()
    cv2.destroyAllWindows()