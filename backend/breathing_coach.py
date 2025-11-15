import cv2
import mediapipe as mp
import time
import numpy as np # We'll use numpy to safely average the breaths

class BreathingCoach:
    """
    A self-contained, time-based breathing coach component.
    
    This version implements a "Calibrate and Guide" model.
    1. CALIBRATE: Listens to the user's natural rhythm.
    2. GUIDE: Uses the user's own rhythm to create a steady pacer.
    
    TIMER FIX: The session timer now starts *after* calibration.
    """
    
    def __init__(self, session_duration_sec=120):
        # 1. Initialize MediaPipe
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils

        # 2. Main App State
        self.app_state = "CALIBRATING" # CALIBRATING, GUIDING, COMPLETE
        self.breath_state = "Welcome"  # Welcome, Inhale, Exhale
        self.shrug_warning = False
        
        # 3. Time-based Goal
        self.session_duration_sec = session_duration_sec
        self.session_start_time = None # <-- FIX: Timer doesn't start yet
        self.session_complete = False

        # 4. Calibration State
        self.calibration_cycles_goal = 3
        self.calibration_breaths = [] # Stores (inhale_duration, exhale_duration)
        self.inhale_start_time = None
        self.exhale_start_time = None
        self.last_calib_state = "Exhale"

        # 5. Guiding (Pacer) State
        self.inhale_duration = 4.0  # Default, will be overwritten
        self.exhale_duration = 6.0  # Default, will be overwritten
        self.cycle_duration = 10.0
        self.pacer_start_time = None

        # 6. AI Feedback / Movement
        self.shoulder_y_prev = 0
        self.MOVEMENT_THRESHOLD = 0.005
        self.SHRUG_THRESHOLD = 0.015
        
        print(f"BreathingCoach (Calibrate/Guide) initialized for {session_duration_sec // 60} min.")

    def _run_calibration_logic(self, movement, current_time):
        """
        Uses reactive (movement-based) logic to measure the user's breath.
        Receives 'movement' from the main process_frame method.
        """
        
        # --- Detect State Change ---
        if movement > self.MOVEMENT_THRESHOLD:
            self.breath_state = "Inhale"
        elif movement < -self.MOVEMENT_THRESHOLD:
            self.breath_state = "Exhale"
        
        # --- Record Timings ---
        if self.breath_state == "Inhale" and self.last_calib_state == "Exhale":
            if self.exhale_start_time and self.inhale_start_time:
                inhale_dur = self.exhale_start_time - self.inhale_start_time
                exhale_dur = current_time - self.exhale_start_time
                self.calibration_breaths.append((inhale_dur, exhale_dur))
                print(f"Calib cycle {len(self.calibration_breaths)}: Inhale {inhale_dur:.2f}s, Exhale {exhale_dur:.2f}s")
            
            self.inhale_start_time = current_time
            self.last_calib_state = "Inhale"
        
        elif self.breath_state == "Exhale" and self.last_calib_state == "Inhale":
            self.exhale_start_time = current_time
            self.last_calib_state = "Exhale"
        
        # --- Check for Completion ---
        if len(self.calibration_breaths) >= self.calibration_cycles_goal:
            self._calculate_pacer()
            self.app_state = "GUIDING"

    def _calculate_pacer(self):
        """Averages the calibrated breaths to set the pacer."""
        if not self.calibration_breaths:
            print("No calibration data, using defaults.")
        else:
            inhales = [b[0] for b in self.calibration_breaths]
            exhales = [b[1] for b in self.calibration_breaths]
            
            self.inhale_duration = np.clip(np.mean(inhales), 2.0, 10.0)
            self.exhale_duration = np.clip(np.mean(exhales), 2.0, 10.0)
        
        self.cycle_duration = self.inhale_duration + self.exhale_duration
        
        print(f"Calibration complete. New pace: Inhale {self.inhale_duration:.2f}s, Exhale {self.exhale_duration:.2f}s")
        
        # --- FIX: START TIMERS NOW ---
        print("Calibration complete. Starting session timer.")
        self.session_start_time = time.time()
        self.pacer_start_time = time.time()
        # ----------------------------

    def _run_guiding_logic(self, current_time):
        """
        Uses the personalized pacer to guide the user.
        """
        if not self.pacer_start_time:
            self.pacer_start_time = current_time
            
        elapsed_since_start = current_time - self.pacer_start_time
        time_in_cycle = elapsed_since_start % self.cycle_duration
        
        if time_in_cycle < self.inhale_duration:
            self.breath_state = "Inhale"
        else:
            self.breath_state = "Exhale"

    def _check_shrugs(self, movement):
        """
        A dedicated check for shoulder shrugs, which sets a warning.
        """
        if movement > self.SHRUG_THRESHOLD:
            self.shrug_warning = True

    def process_frame(self, frame):
        """
        The main public method. Takes a frame, routes to the
        correct logic, and returns an annotated frame.
        """
        self.shrug_warning = False # Reset warning each frame
        current_time = time.time()
        movement = 0 

        # 1. Flip, convert, process
        frame = cv2.flip(frame, 1)
        frame_h, frame_w, _ = frame.shape
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)

        # 2. Check for global session completion
        # --- FIX: Only check if timer has actually started ---
        if self.session_start_time and not self.session_complete:
            elapsed_time = current_time - self.session_start_time
            if elapsed_time > self.session_duration_sec:
                self.session_complete = True
                self.app_state = "COMPLETE"
        # ----------------------------------------------------

        # 3. Main Logic Router
        if results.pose_landmarks and not self.session_complete:
            landmarks = results.pose_landmarks.landmark
            shoulder_y_current = (landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y +
                                  landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y) / 2
            
            if self.shoulder_y_prev == 0:
                self.shoulder_y_prev = shoulder_y_current
            
            movement = self.shoulder_y_prev - shoulder_y_current
            
            self._check_shrugs(movement)
            
            if self.app_state == "CALIBRATING":
                self._run_calibration_logic(movement, current_time)
            elif self.app_state == "GUIDING":
                self._run_guiding_logic(current_time)
            
            self.shoulder_y_prev = shoulder_y_current
            
        elif not results.pose_landmarks:
            # If user leaves, reset
            self.app_state = "CALIBRATING"
            self.breath_state = "Welcome"
            self.calibration_breaths = []
            self.inhale_start_time = None
            self.exhale_start_time = None
            self.pacer_start_time = None
            self.session_start_time = None # Reset session timer
            self.shoulder_y_prev = 0 
        
        # 4. Draw the UI
        frame = self._draw_ui(frame, frame_h, frame_w)
        return frame

    def _draw_ui(self, frame, frame_h, frame_w):
        """A private helper method to draw the UI elements."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame_w, 90), (60, 60, 60), -1)
        alpha = 0.7
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        text_color = (255, 255, 255)
        
        # --- Set text based on app state ---
        if self.app_state == "COMPLETE":
            feedback_text = "Great job! Session complete."
            text_color = (170, 255, 170)
        elif self.shrug_warning:
            feedback_text = "Gently relax your shoulders..."
            text_color = (150, 150, 255)
        elif self.app_state == "CALIBRATING":
            calib_count = len(self.calibration_breaths)
            feedback_text = f"Breathe normally... (Calibrating {calib_count+1}/{self.calibration_cycles_goal})"
            text_color = (255, 255, 180) # Light Yellow
        elif self.app_state == "GUIDING":
            if self.breath_state == "Inhale":
                feedback_text = "Inhale..."
                text_color = (230, 255, 230) # Soft Mint
            else:
                feedback_text = "Exhale..."
                text_color = (255, 230, 255) # Soft Lilac
        else: # Welcome state
            feedback_text = "Welcome to Majka. Please find a relaxed position."

        cv2.putText(frame, feedback_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 2, cv2.LINE_AA)
        
        # --- FIX: Smart Timer UI ---
        if self.app_state == "COMPLETE":
            timer_text = "Time: Complete!"
        elif self.app_state == "GUIDING":
            # Show live countdown
            remaining_sec = int(self.session_duration_sec - (time.time() - self.session_start_time))
            if remaining_sec < 0: remaining_sec = 0
            minutes = remaining_sec // 60
            seconds = remaining_sec % 60
            timer_text = f"Time: {minutes:02d}:{seconds:02d}"
        else:
            # Show the target time (not counting down)
            minutes = self.session_duration_sec // 60
            seconds = self.session_duration_sec % 60
            timer_text = f"Time: {minutes:02d}:{seconds:02d}"
        # -------------------------

        cv2.putText(frame, timer_text, (frame_w - 180, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame

    def close(self):
        """Cleans up the MediaPipe pose component."""
        self.pose.close()
        print("BreathingCoach component cleaned up.")