# PackVote: An AI-Powered Group Travel Planning App
###Deployed Project URL###
URL: pack-vote.vercel.app
(backend on render: https://packvote-backend-kvea.onrender.com/)


PackVote 🧳

PackVote is an AI-powered group travel planning app. It helps a group of friends propose destinations, vote on where to go, get an AI-generated itinerary, split expenses, and track trip-planning tasks — all in one place.

Features


User registration/login and group creation
Destination voting engine (voting.py)
Rule-based + AI destination recommender (recommender.py)
AI-generated day-by-day itineraries via the Groq API (ai_itinerary.py)
Expense tracking and splitting (expenses.py)
Trip-planning task/checklist manager (planner.py)
Email notifications via Gmail SMTP (email_service.py)
Exploratory notebooks for the voting and recommendation logic (notebooks/)


Tech Stack
Backend Python, Flask, Flask-CORS
Database MySQL (via pymysql)
AIGroq API (LLM-based itinerary generation)
EmailGmail SMTP (App Password)
FrontendStatic HTML, CSS, vanilla JavaScript (no build step)
NotebooksJupyter (prototyping voting/recommendation logic)

1. Clone
clone https://github.com/AnveshaGitHub/PackVote_Complete.git
cd PackVote_Complete/backend

2. Install dependencies
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

3. Set environment variables
Create a .env file inside backend/:
(Groq and Gmail vars are optional — the app runs without them, just without AI itineraries / email notifications.)

4. Run
bashpython app.py

Flask starts on http://localhost:5000 and serves the frontend too, so open that URL in a browser to use the app — no separate frontend step needed.

⚠️ Note
database.py and email_service.py contain hardcoded fallback credentials committed to the repo. Rotate them and always set your own values via .env.
