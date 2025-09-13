import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# Check for the API key in the environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# This is our rule-based system for the guided quiz.
# The keys are question IDs, and the values contain the question text
# and the next question ID based on the 'yes' or 'no' answer.
questions = {
    'start': {
        'question': 'Are they conscious and responsive?',
        'yes': 'q1_a',
        'no': 'q1_b',
    },
    'q1_a': {
        'question': 'Are they breathing?',
        'yes': 'q2_a',
        'no': 'diag_unconscious_not_breathing',
    },
    'q1_b': {
        'question': 'Do they have a pulse?',
        'yes': 'diag_unconscious_breathing',
        'no': 'diag_unconscious_no_pulse',
    },
    'q2_a': {
        'question': 'Is there any severe bleeding?',
        'yes': 'diag_bleeding',
        'no': 'q3_a',
    },
    'q3_a': {
        'question': 'Are they clutching their chest or experiencing severe chest pain?',
        'yes': 'diag_heart_attack',
        'no': 'q4_a',
    },
    'q4_a': {
        'question': 'Are they exhibiting facial drooping, arm weakness, or slurred speech?',
        'yes': 'diag_stroke',
        'no': 'q5_a',
    },
    'q5_a': {
        'question': 'Are they experiencing a sudden, uncontrollable shaking of their body?',
        'yes': 'diag_seizure',
        'no': 'q6_a',
    },
    'q6_a': {
        'question': 'Do they have a known history of severe allergies or are they having trouble breathing with swelling?',
        'yes': 'diag_allergic_reaction',
        'no': 'diag_general_ok',
    },
}

# This dictionary holds the final diagnoses based on the path taken.
diagnoses = {
    'diag_unconscious_not_breathing': 'Possible Cardiac Arrest. Start CPR immediately and call for an AED. You should have already called for emergency services.',
    'diag_unconscious_breathing': 'Possible Unconscious but Breathing. Place them in the recovery position and monitor their breathing. You should have already called for emergency services.',
    'diag_unconscious_no_pulse': 'Possible Cardiac Arrest. Start CPR immediately. You should have already called for emergency services.',
    'diag_bleeding': 'Possible Severe Bleeding. Apply direct pressure to the wound with a clean cloth. Elevate the injured area if possible. You should have already called for emergency services.',
    'diag_heart_attack': 'Possible Heart Attack. Keep the person calm and seated. Loosen any tight clothing. You should have already called for emergency services.',
    'diag_stroke': 'Possible Stroke. Remember the FAST acronym (Face, Arm, Speech, Time). Do not give them anything to eat or drink. You should have already called for emergency services.',
    'diag_seizure': 'Possible Seizure. Protect the person from injury by moving objects away. Do not restrain them. You should have already called for emergency services.',
    'diag_allergic_reaction': 'Possible Anaphylactic Shock. If they have an epinephrine auto-injector, assist them in using it. You should have already called for emergency services.',
    'diag_general_ok': 'The person may be fine or have a less critical condition. However, if symptoms persist or worsen, please seek professional medical help immediately.',
}

def call_ai_for_symptom_check(symptoms):
    """
    Uses the Gemini API to analyze symptoms and suggest a starting question ID.
    """
    url = f"https://generativelaanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    # We define the possible diagnosis categories we want the AI to match to.
    diagnosis_categories = {
        "Cardiac Arrest": "diag_unconscious_not_breathing",
        "Breathing Emergency": "diag_unconscious_breathing",
        "Severe Bleeding": "diag_bleeding",
        "Heart Attack": "diag_heart_attack",
        "Stroke": "diag_stroke",
        "Seizure": "diag_seizure",
        "Allergic Reaction": "diag_allergic_reaction",
    }
    
    # We create a JSON schema that forces the AI to pick from our predefined categories.
    prompt = f"Analyze the following medical symptoms and determine the most likely immediate emergency from this list: {list(diagnosis_categories.keys())}. Respond with only the name of the emergency. If none apply, respond 'No Match'.\n\nSymptoms: {symptoms}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        ai_match = result['candidates'][0]['content']['parts'][0]['text'].strip()

        if ai_match in diagnosis_categories:
            # We map the AI's diagnosis to the corresponding question ID.
            if ai_match == "Cardiac Arrest":
                return "q1_a"
            elif ai_match == "Breathing Emergency":
                return "q1_b"
            elif ai_match == "Severe Bleeding":
                return "q2_a"
            elif ai_match == "Heart Attack":
                return "q3_a"
            elif ai_match == "Stroke":
                return "q4_a"
            elif ai_match == "Seizure":
                return "q5_a"
            elif ai_match == "Allergic Reaction":
                return "q6_a"
        
        return "start" # Default fallback
    except Exception as e:
        print(f"Error calling AI: {e}")
        return "start" # Default fallback on error


@app.route('/')
def index():
    return send_from_directory('.', 'index.htm')


@app.route('/api/symptom_check', methods=['POST'])
def symptom_check():
    """
    Endpoint for the AI-powered symptom check.
    """
    data = request.json
    symptoms = data.get('symptoms')
    
    if not symptoms:
        return jsonify({"status": "error", "message": "No symptoms provided."})

    # Call the AI function to get the suggested starting question ID
    next_question_id = call_ai_for_symptom_check(symptoms)

    # Return the first question for the guided quiz based on the AI's suggestion
    first_question = questions.get(next_question_id, questions['start'])
    return jsonify({
        "status": "question",
        "next_q_id": next_question_id,
        "question": first_question['question']
    })


@app.route('/api/answer', methods=['POST'])
def answer():
    """
    Endpoint for the guided quiz logic.
    """
    data = request.json
    current_q_id = data.get('current_q_id')
    answer = data.get('answer')

    # This is the corrected line:
    if answer == 'initial':
        # This is the entry point for the guided quiz, so we start at the beginning.
        next_q_id = 'start'
    else:
        # Get the next question ID based on the user's answer
        next_q_id = questions[current_q_id][answer]

    if next_q_id.startswith('diag_'):
        # If the next ID is a diagnosis, we return the diagnosis text.
        return jsonify({
            "status": "diagnosis",
            "diagnosis": diagnoses[next_q_id]
        })
    else:
        # Otherwise, we return the next question.
        next_question = questions[next_q_id]
        return jsonify({
            "status": "question",
            "next_q_id": next_q_id,
            "question": next_question['question']
        })
if __name__ == '__main__':
    app.run(debug=True)

