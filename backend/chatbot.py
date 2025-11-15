import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. SETUP: Load Environment Variables and Configure AI ---
# This loads the GOOGLE_API_KEY from your local .env file
load_dotenv() 

app = Flask(__name__)
# This is crucial for your frontend teammate (on a different port) to call your API
CORS(app) 

# Configure API key using the variable loaded from .env
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# --- 2. THE MASTER SAFETY PROMPT ---
# This ensures the AI is safe, nurturing, and blocks medical advice.
MASTER_SAFETY_PROMPT = """
You are 'Majka,' a warm, nurturing, and maternal AI assistant for new mothers.
YOUR PRIMARY DIRECTIVE IS SAFETY. YOU ARE NOT A DOCTOR.

1.  You MUST NOT give any medical advice, diagnosis, or treatment recommendations.
2.  If the user's question sounds medical, you MUST gently decline and guide them to a doctor or the app's 'Symptom Checker'.
3.  CRITICAL RULE: If a user mentions bleeding, fever, pus, severe headache, dizziness, or suicidal thoughts, you MUST stop. Your ONLY response must be: 'That sounds serious, and your safety is most important. Please stop and call your doctor or 911 immediately.'
4.  Your job is to provide emotional support, validation, and general (non-medical) information.
"""

# --- 3. CONFIGURE THE GEMINI MODEL ---
# We set up the model ONCE with its safety rules and system prompt.
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", # Using the fast, modern model
    system_instruction=MASTER_SAFETY_PROMPT,
    safety_settings={
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
        'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
        # This backs up our prompt rule to block dangerous medical inquiries.
        'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_MEDIUM_AND_ABOVE' 
    }
)

# --- 4. THE API ENDPOINT ---
@app.route('/ask-majka', methods=['POST'])
def ask_majka():
    # Get the user's question from the frontend (via JSON)
    user_question = request.json.get('question')

    if not user_question:
        return jsonify({"error": "No question provided"}), 400

    try:
        # We send only the user's question, as the Master Prompt is already loaded in the model config.
        response = model.generate_content(user_question)

        ai_answer = response.text

        # Send the safe answer back to the frontend
        return jsonify({"answer": ai_answer})

    except Exception as e:
        print(f"Error: {e}")
        # If Gemini's own safety filter blocks the prompt, send a clean error back.
        if "response.prompt_feedback" in str(e):
             return jsonify({"answer": "I'm sorry, I cannot answer that question. Please check with your doctor."})
        return jsonify({"error": "Failed to get response"}), 500

# --- 5. RUN THE SERVER ---
if __name__ == '__main__':
    app.run(port=5000, debug=True)