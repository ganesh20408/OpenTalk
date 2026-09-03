# SIH26101: AI Competency & Learning Platform

## Overview
This is a prototype built for the Smart India Hackathon (SIH26101). It is an AI-enabled learning platform designed to identify competency gaps, recommend personalized training via the iGOT Karmayogi ecosystem, and generate interactive quizzes from uploaded learning materials.

## Key Features
* **AI Quiz Generation:** Upload a PDF document and automatically generate targeted multiple-choice questions using Google's Gemini AI.
* **Competency Gap Identification:** Analyzes user answers to pinpoint specific knowledge gaps when questions are answered incorrectly.
* **iGOT Karmayogi Recommendations:** Suggests actionable training modules based on the identified competency gaps.
* **Local Database Tracking:** Uses SQLite to securely track learner progress and record identified skill gaps for administrative review.

## Tech Stack
* **Language:** Python
* **Frontend:** Streamlit
* **AI/LLM:** Google Gemini 3.7 Flash API
* **Database:** SQLite
* **Document Processing:** PyMuPDF

## How to Run the Prototype Locally
1. Ensure Python is installed on your machine.
2. Download or clone this repository.
3. Open your terminal in the project folder and install the required dependencies:
   `pip install -r requirements.txt`
4. Open `app.py` and insert your Gemini API Key in the `API_KEY` variable.
5. Run the application:
   `streamlit run app.py`
