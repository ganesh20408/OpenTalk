import streamlit as st
import sqlite3
import json
import fitz  # PyMuPDF
from google import genai
from google.genai import types

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Apex Learn",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# 2. GEMINI AI SETUP
# ============================================================

MODEL_NAME = "gemini-3.7-flash" # Flash model is optimized for speed

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        st.error("Gemini API key is missing or invalid.")
        st.stop()
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Unable to initialize Gemini AI. Error: {e}")
    st.stop()

# ============================================================
# 3. DATABASE SETUP
# ============================================================

try:
    conn = sqlite3.connect("sih_learning_platform.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS learners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            skill_gap TEXT,
            course_recommendation TEXT
        )
    """)
    conn.commit()
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ============================================================
# 4. WEB APP DESIGN
# ============================================================

st.title("SIH26101: AI Competency & Learning Platform")
st.write("Upload a learning document. The AI will rapidly generate a 10-question quiz, identify competency gaps, and suggest courses.")
st.divider()

# ============================================================
# 5. PDF UPLOAD
# ============================================================

uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

# ============================================================
# 6. READ PDF & 7. GENERATE QUIZ
# ============================================================

if uploaded_file is not None:
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"

    # Reset session state on new file upload
    if st.session_state.get("file_id") != file_id:
        st.session_state.file_id = file_id
        st.session_state.quiz_data = None
        st.session_state.submitted = False
        st.session_state.user_answers = {}

    # Generate quiz if it doesn't exist
    if st.session_state.get("quiz_data") is None:

        with st.spinner("Extracting text and generating your quiz... ⚡"):
            try:
                # FAST PDF READING
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")

                # 1. Get the number of pages
                num_pages = len(doc)
                document_text = ""

                # Fast Exit: Only extract enough text to get context (up to 150k chars)
                for page in doc:
                    document_text += page.get_text() + "\n"
                    if len(document_text) > 150000:
                        break

                document_text = document_text.strip()[:150000]

                if not document_text:
                    st.error("No readable text was found in this PDF.")
                    st.stop()

            except Exception as e:
                st.error(f"Unable to read the PDF. Error: {e}")
                st.stop()

            # 2. Determine the target number of questions
            if num_pages > 50:
                target_question_count = min(20, num_pages // 4)
            else:
                target_question_count = 10

            # 3. The Dynamic Prompt
            prompt = f"""
You are an educational assessment assistant.
Read the learning material below.

Create EXACTLY {target_question_count} multiple-choice questions that test understanding of the concepts in the material.
Each question must have exactly four options.
Identify the specific competency gap that the learner should study if they answer incorrectly.

Return ONLY the requested JSON structure.

Learning material:
{document_text}
"""

            # 4. Fallback Loop for Gemini API
            FALLBACK_MODELS = [
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
            ]

            last_error = None
            generation_successful = False

            for model_name in FALLBACK_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "questions": types.Schema(
                                        type=types.Type.ARRAY,
                                        items=types.Schema(
                                            type=types.Type.OBJECT,
                                            properties={
                                                "question": types.Schema(type=types.Type.STRING),
                                                "options": types.Schema(
                                                    type=types.Type.ARRAY,
                                                    items=types.Schema(type=types.Type.STRING)
                                                ),
                                                "answer": types.Schema(type=types.Type.STRING),
                                                "gap_identified": types.Schema(type=types.Type.STRING)
                                            },
                                            required=[
                                                "question",
                                                "options",
                                                "answer",
                                                "gap_identified"
                                            ]
                                        )
                                    )
                                },
                                required=["questions"]
                            )
                        )
                    )

                    # Parse JSON and break loop if successful
                    quiz_payload = json.loads(response.text)
                    st.session_state.quiz_data = quiz_payload["questions"]
                    generation_successful = True
                    break

                except Exception as e:
                    print(f"Model {model_name} failed : {e}")
                    last_error = e
                    continue

            if not generation_successful:
                st.error("All AI models are currently overloaded. Please try again in a few moments.")
                st.error(f"Final Error Details: {last_error}")
                st.stop()

    # ========================================================
    # 8. DISPLAY QUIZ
    # ========================================================

    quiz_data = st.session_state.quiz_data

    # Safety check in case the AI generated slightly more/less
    # We slice it to ensure we only ever show 10 on the frontend
    quiz_data = quiz_data[:10]

    st.divider()
    st.subheader(f"🧠 Knowledge Check ({len(quiz_data)} Questions)")

    # Form prevents constant page reloads
    with st.form("quiz_form"):
        user_selections = {}

        for idx, q in enumerate(quiz_data):
            st.write(f"**Q{idx + 1}: {q['question']}**")
            user_selections[idx] = st.radio(
                "Select an answer:",
                q["options"],
                key=f"quiz_answer_{idx}",
                index=None
            )
            st.write("---")

        submitted = st.form_submit_button("Submit All Answers", type="primary")

        if submitted:
            if None in user_selections.values():
                st.warning(f"Please answer all {len(quiz_data)} questions before submitting.")

            else:
                st.session_state.submitted = True
                st.session_state.user_answers = user_selections

    # ========================================================
    # 9 & 10. SHOW RESULTS & SAVE TO DB
    # ========================================================

    if st.session_state.get("submitted"):
        st.subheader("📊 Results")

        score = 0
        total = len(quiz_data)
        gaps_to_save = []

        for idx, q in enumerate(quiz_data):
            selected = st.session_state.user_answers[idx]
            correct = q["answer"]

            st.write(f"**Q{idx + 1}: {q['question']}**")

            if selected == correct:
                st.success(f"✅ Correct! (You selected: {selected})")
                score += 1
            else:
                st.error(f"❌ Incorrect. (You selected: {selected})")
                st.write(f"**Correct answer:** {correct}")

                gap = q["gap_identified"]
                recommendation = f"Search the iGOT Karmayogi portal for courses related to '{gap}'."

                st.warning(f"🎯 **Competency Gap Identified:** {gap}")
                st.info(f"📚 **Recommended Action:** {recommendation}")

                gaps_to_save.append((gap, recommendation))

            st.write("---")

        st.subheader(f"🏆 Final Score: {score} / {total}")

        # Batch save to database
        if gaps_to_save:
            try:
                c.executemany(
                    """
                    INSERT INTO learners (name, skill_gap, course_recommendation)
                    VALUES (?, ?, ?)
                    """,
                    [("Student", gap, rec) for gap, rec in gaps_to_save]
                )
                conn.commit()
                st.toast(f"{len(gaps_to_save)} competency gaps recorded in the database.")
            except Exception as e:
                st.error(f"Could not save competency gaps: {e}")

# ============================================================
# 11. ADMIN VIEW
# ============================================================

st.divider()
st.subheader("🔐 Admin")

if st.button("Admin: View Competency Gaps Database"):
    try:
        c.execute("""
            SELECT id, name, skill_gap, course_recommendation
            FROM learners
            ORDER BY id DESC
        """)
        data = c.fetchall()

        if data:
            st.write("Saved Competency Gap Records:")
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No competency gaps have been recorded yet.")
    except Exception as e:
        st.error(f"Could not read database: {e}")



