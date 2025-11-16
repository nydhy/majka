import os
from dotenv import load_dotenv # <-- CRITICAL FIX: Loads .env variables
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import google.generativeai as genai
from elevenlabs import Voice 
from elevenlabs.client import ElevenLabs 

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv() # <--- THIS MUST BE THE FIRST LINE OF LOGIC

# --- 1. SETUP ---
app = Flask(__name__)
CORS(app) 

# Load API keys from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize Clients
genai.configure(api_key=GOOGLE_API_KEY)
el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


# Define Voice ID
MATERNAL_VOICE_ID = "a1m16HA3i1rljUsxpKfn" 

# --- 2. MASTER SAFETY PROMPT (THE BRAIN) ---
MASTER_SAFETY_PROMPT = """
You are 'Majka,' a warm, nurturing, and maternal AI assistant for new mothers.
YOUR PRIMARY DIRECTIVE IS SAFETY. YOU ARE NOT A DOCTOR.

1.  You MUST NOT give any medical advice, diagnosis, or treatment recommendations.
2.  If the user's question sounds medical, you MUST gently decline and guide them to a doctor or the app's 'Symptom Checker'.
3.  CRITICAL RULE: If a user mentions bleeding, fever, pus, severe headache, dizziness, or suicidal thoughts, you MUST stop. Your ONLY response must be: 'That sounds serious, and your safety is most important. Please stop and call your doctor or 911 immediately.'
4.  Your job is to provide emotional support, validation, and general (non-medical) information.
"""

# Configure the Gemini Model ONCE with the system prompt
gemini_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    system_instruction=MASTER_SAFETY_PROMPT,
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
)

# --- 3. API ENDPOINT: TEXT GENERATION (Gemini) ---
@app.route('/ask-majka', methods=['POST'])
def ask_majka():
    """Endpoint to get a safe, text response from Gemini."""
    user_question = request.json.get('question')

    if not user_question:
        return jsonify({"error": "No question provided"}), 400

    try:
        response = gemini_model.generate_content(user_question)
        ai_answer = response.text

        # 4. Send the safe answer back to the frontend
        return jsonify({"answer": ai_answer})

    except Exception as e:
        print(f"Gemini Error: {e}")
        return jsonify({"error": "Failed to get response from AI"}), 500


# --- 4. API ENDPOINT: VOICE GENERATION (ElevenLabs) ---
@app.route('/speak', methods=['POST'])
# --- 4. API ENDPOINT: VOICE GENERATION (ElevenLabs) ---
@app.route('/speak', methods=['POST'])
# --- 4. API ENDPOINT: VOICE GENERATION (ElevenLabs) ---
@app.route('/speak', methods=['POST'])
def speak_text():
    """Endpoint to generate and stream audio from text using ElevenLabs."""
    text_to_speak = request.json.get('text')

    if not text_to_speak:
        return jsonify({"error": "No text provided"}), 400

    try:
        # CRITICAL FIX: The 'stream=True' argument is removed.
        # The library returns a streamable iterator by default, which Flask can handle.
        audio_stream = el_client.text_to_speech.convert(
            text=text_to_speak,
            voice_id=MATERNAL_VOICE_ID,
            model_id="eleven_turbo_v2",
        )
        
        # Return the audio stream as an audio/mpeg (MP3) file
        # This will now use the correct streamable object returned by the library.
        return Response(audio_stream, mimetype="audio/mpeg")

    except Exception as e:
        print(f"ElevenLabs TTS Error: {e}")
        return jsonify({"error": "Failed to generate speech"}), 500


# --- 5. RUN SERVER ---
if __name__ == '__main__':
    # Final check: Ensure keys are set before running
    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("ELEVENLABS_API_KEY"):
        print("CRITICAL ERROR: Please ensure GOOGLE_API_KEY and ELEVENLABS_API_KEY are set in your .env file.")
        exit(1)
        
    app.run(port=5000, debug=True)