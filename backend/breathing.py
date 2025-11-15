import cv2
# Import the class from your other file
from breathing_coach import BreathingCoach 

def run_breathing_session(minutes):
    """
    This function is called by the UI. It initializes the webcam 
    and the coach, and runs the main loop.
    """
    
    # 1. Convert minutes to seconds
    session_duration_sec = minutes * 60

    print(f"--- Starting {minutes} minute session. Press 'q' to quit. ---")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return # Exit the function
        
    # 2. "Plug in" the coach with the chosen duration
    coach = BreathingCoach(session_duration_sec=session_duration_sec)

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                continue

            # 3. Process the frame with the component
            processed_frame = coach.process_frame(frame)
            
            # 4. Display the result
            cv2.imshow('Majka - Postpartum Breathing Guide', processed_frame)

            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
    finally:
        # 5. Clean up
        coach.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"--- Session complete. ---")

# --- This is the "UI" logic ---
# Your teammate's UI would have 4 buttons.
# When a button is clicked, it would call one of these.

def on_2_min_button_click():
    run_breathing_session(minutes=2)

def on_5_min_button_click():
    run_breathing_session(minutes=5)

def on_10_min_button_click():
    run_breathing_session(minutes=10)

def on_15_min_button_click():
    run_breathing_session(minutes=15)

# --- This block runs when you execute this file ---
if __name__ == "__main__":
    
    # --- CHOOSE YOUR TEST ---
    # This simulates the user clicking a button.
    # To test a different time, just comment/uncomment the lines.
    
    on_2_min_button_click()
    
    # --- Or, uncomment one of these to test: ---
    # on_5_min_button_click()
    # on_10_min_button_click()
    # on_15_min_button_click()