import streamlit as st
import sqlite3
import json
import PyPDF2
import google.generativeai as genai
import time

# ==========================================
# 1. SETUP AI AND DATABASE
# ==========================================
st.set_page_config(page_title="SIH26101 AI Platform", layout="centered")

# Retrieve API key from Streamlit secrets
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error("API Key not found! Please add GEMINI_API_KEY in your Streamlit App Secrets.")
    st.stop()

# Helper function to generate content with automatic fallbacks and retries
def generate_quiz_with_fallback(prompt):
    # Ranked list of models to try if one is busy
    fallback_models = [
        'gemini-3.7-flash', 
        'gemini-3.5-flash', 
        'gemini-2.5-flash', 
        'gemini-1.5-flash'
    ]
    
    last_error = None
    
    # Try each model in the list
    for model_name in fallback_models:
        try:
            model = genai.GenerativeModel(model_name)
            # Try 2 times per model before giving up
            for attempt in range(2):
                try:
                    response = model.generate_content(prompt)
                    return response.text # Success! Return the text.
                except Exception as e:
                    last_error = str(e)
                    if "503" in last_error or "overloaded" in last_error.lower():
                        time.sleep(2) # Wait 2 seconds before retrying if server is busy
                        continue
                    else:
                        break # Break loop if it's not a 503 error
        except Exception:
            continue # Try the next model in the list
            
    raise Exception(f"All models failed or are overloaded. Last error: {last_error}")

# Connect to our local database
conn = sqlite3.connect('sih_learning_platform.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS learners (name TEXT, skill_gap TEXT, course_recommendation TEXT)')
conn.commit()

# ==========================================
# 2. WEB APP DESIGN
# ==========================================
st.title("SIH26101: AI Competency & Learning Platform")
st.write("Upload a learning document. The AI will generate a quiz, identify gaps, and suggest iGOT Karmayogi courses.")

# ==========================================
# 3. UPLOAD AND READ PDF
# ==========================================
uploaded_file = st.file_uploader("Step 1: Upload a PDF document", type=['pdf'])

if uploaded_file is not None:
    with st.spinner("Reading document..."):
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            document_text = ""
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    document_text += text + "\n"
        except Exception as e:
            st.error(f"Could not read PDF: {e}")
            document_text = ""

    if len(document_text.strip()) < 50:
        st.warning("The uploaded PDF does not contain enough readable text.")
    else:
        st.success(f"Document read successfully! Extracted approximately {len(document_text)} characters.")

        # ==========================================
        # 4. AI GENERATES QUIZ FROM TEXT
        # ==========================================
        prompt = f"""
        Read the following text and create 1 multiple-choice question with 4 options to test the reader's understanding.
        Also, identify the competency gap (skill or topic name) if they answer incorrectly.
        Output ONLY valid JSON in this exact structure without any extra markdown formatting or backticks:
        {{
            "question": "Sample question?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "Option A",
            "gap_identified": "Topic Name"
        }}

        Text to analyze:
        {document_text[:3000]}
        """

        try:
            with st.spinner("Gemini is generating your knowledge-check question..."):
                # Call our new smart fallback function
                raw_response = generate_quiz_with_fallback(prompt)

                clean_text = raw_response.replace('```json', '').replace('```', '').strip()
                quiz_data = json.loads(clean_text)

            # Display Quiz
            st.subheader("Step 2: Knowledge Check")
            st.write(f"**{quiz_data['question']}**")

            user_answer = st.radio("Select an answer:", quiz_data['options'], key="quiz_choice")

            if st.button("Submit Answer"):
                if user_answer == quiz_data['answer']:
                    st.success("Correct! Great job understanding the material.")
                else:
                    st.error(f"Incorrect. The correct answer was: {quiz_data['answer']}")
                    gap = quiz_data['gap_identified']
                    st.warning(f"**Competency Gap Identified:** {gap}")
                    st.info(f"**Recommended Action:** Search the iGOT Karmayogi portal for courses on '{gap}'.")

                    # Save to database
                    c.execute("INSERT INTO learners VALUES (?, ?, ?)", ("Learner", gap, f"iGOT course on {gap}"))
                    conn.commit()
                    st.toast("Competency gap recorded in the database.")

        except Exception as e:
            st.error("Gemini could not generate the quiz due to high server demand.")
            st.write("Error details:", e)
            st.info("Tip: Try uploading again in a few minutes once Google's servers cool down.")

# ==========================================
# 5. ADMIN VIEW
# ==========================================
st.divider()
if st.button("Admin: View Competency Gaps Database"):
    c.execute("SELECT * FROM learners")
    data = c.fetchall()
    st.write("Saved Data (Name | Skill Gap | Recommendation):")
    st.write(data)

