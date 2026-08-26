import streamlit as st
import sqlite3
import json
import PyPDF2
import google.generativeai as genai

# ==========================================
# 1. SETUP AI AND DATABASE
# ==========================================
# TODO: Paste your Gemini API key inside the quotes below
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)

# Connect to our local database (creates a file in your folder automatically)
conn = sqlite3.connect('sih_learning_platform.db')
c = conn.cursor()
# Create a table to track users and their gaps
c.execute('CREATE TABLE IF NOT EXISTS learners (name TEXT, skill_gap TEXT, course_recommendation TEXT)')
conn.commit()

# ==========================================
# 2. WEB APP DESIGN (Streamlit)
# ==========================================
st.title("SIH26101: AI Competency & Learning Platform")
st.write("Upload a learning document. The AI will generate a quiz, identify gaps, and suggest iGOT Karmayogi courses.")

# ==========================================
# 3. UPLOAD AND READ PDF
# ==========================================
uploaded_file = st.file_uploader("Upload a PDF document", type=['pdf'])

if uploaded_file is not None:
    st.info("Reading document...")
    # Extract text from the uploaded PDF
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    document_text = ""
    for page in pdf_reader.pages:
        document_text += page.extract_text()
    
    st.success("Document read successfully! Generating quiz...")

# ==========================================
# 4. AI GENERATES QUIZ FROM TEXT
# ==========================================
    # We give instructions to the AI on how to read the text and format the output
    prompt = f"""
    Read the following text and create 1 multiple-choice question to test the reader's understanding.
    Also, identify the 'competency gap' (the topic they need to study) if they get it wrong.
    Output ONLY valid JSON in this exact format, with no extra text or markdown formatting:
    {{
        "question": "Question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "Option A",
        "gap_identified": "Topic Name"
    }}
    
    Text to analyze: {document_text[:3000]} 
    """
    
    # Send the prompt to the Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    
    # Process the AI's response
    try:
        # Clean up the response in case the AI added extra formatting
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        quiz_data = json.loads(clean_text) # Convert JSON into a Python dictionary
        
        # Display the Quiz on the website
        st.subheader("Knowledge Check")
        st.write(f"**{quiz_data['question']}**")
        
        user_answer = st.radio("Select an answer:", quiz_data['options'])
        
        if st.button("Submit Answer"):
            if user_answer == quiz_data['answer']:
                st.success("Correct! Great job understanding the material.")
            else:
                st.error(f"Incorrect. The correct answer was: {quiz_data['answer']}")
                
                # Identify Gap & Recommend iGOT Course
                gap = quiz_data['gap_identified']
                st.warning(f"**Competency Gap Identified:** {gap}")
                st.info(f"**Recommended Action:** Search the iGOT Karmayogi portal for courses on '{gap}'.")
                
                # Save the identified gap to our SQLite Database
                c.execute("INSERT INTO learners VALUES (?, ?, ?)", ("Student", gap, f"iGOT course on {gap}"))
                conn.commit()
                st.toast("Competency gap recorded in the database.")
                
    except Exception as e:
        st.error("AI couldn't generate a valid quiz from this document. Try a document with more plain text.")
        st.write("Error details:", e)

# ==========================================
# 5. ADMIN VIEW (See the database)
# ==========================================
st.divider()
if st.button("Admin: View Competency Gaps Database"):
    c.execute("SELECT * FROM learners")
    data = c.fetchall()
    st.write("Saved Data (Name | Skill Gap | Recommendation):")
    st.write(data)
