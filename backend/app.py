from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os
from datetime import datetime
from collections import defaultdict

from database import init_db, get_connection
from voting import VotingEngine
from recommender import RecommendationEngine
from apis import TravelAPI
from auth import register_user, login_user, get_user, update_preferences, add_group_to_user
from expenses import add_expense, get_expenses, delete_expense, get_expense_stats
from planner import add_task, get_tasks, toggle_task, delete_task, update_task, generate_default_tasks

try:
    from ai_itinerary import generate_ai_itinerary
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

app = Flask(__name__)
CORS(app)

BASE_DIR         = os.path.dirname(__file__)
DATA_DIR         = os.path.join(BASE_DIR, 'data')
FRONTEND_DIR     = os.path.join(BASE_DIR, '..', 'frontend')
ITINERARIES_FILE = os.path.join(DATA_DIR, 'itineraries.json')

os.makedirs(DATA_DIR, exist_ok=True)

voting_engine = VotingEngine()
recommender   = RecommendationEngine()
travel_api    = TravelAPI()

init_db()

def load_json(fp, default):
    if os.path.exists(fp):
        with open(fp) as f: return json.load(f)
    return default

def save_json(fp, data):
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w') as f: json.dump(data, f, indent=2)

# ── Frontend ──────────────────────────────────────────────────────────────
@app.route('/')
def home(): return send_from_directory(FRONTEND_DIR, 'index.html')
@app.route('/login')
def login_page(): return send_from_directory(FRONTEND_DIR, 'login.html')
@app.route('/register')
def register_page(): return send_from_directory(FRONTEND_DIR, 'register.html')
@app.route('/dashboard')
def dashboard_page(): return send_from_directory(FRONTEND_DIR, 'dashboard.html')
@app.route('/vote')
def vote_page(): return send_from_directory(FRONTEND_DIR, 'vote.html')
@app.route('/results')
def results_page(): return send_from_directory(FRONTEND_DIR, 'results.html')
@app.route('/api/status')
def status(): return jsonify({'status': 'PackVote running', 'ai': AI_AVAILABLE})

# ══════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.json
    name     = d.get('name', '').strip()
    dob      = d.get('dob', '')
    email    = d.get('email', '').strip().lower()
    phone    = d.get('phone', '').strip()
    password = d.get('password', '')
    tp       = d.get('travel_preferences', {})
    if not name:                      return jsonify({'success': False, 'error': 'Name required'}), 400
    if not dob:                       return jsonify({'success': False, 'error': 'DOB required'}), 400
    if not email or '@' not in email: return jsonify({'success': False, 'error': 'Valid email required'}), 400
    if not phone or len(phone) < 10:  return jsonify({'success': False, 'error': 'Valid phone required'}), 400
    if not password or len(password) < 6: return jsonify({'success': False, 'error': 'Password 6+ chars'}), 400
    result = register_user(name, dob, email, phone, password, tp)
    return jsonify(result), (201 if result['success'] else 400)

@app.route('/api/auth/login', methods=['POST'])
def login():
    d     = request.json
    email = d.get('email', '').strip().lower()
    pw    = d.get('password', '')
    if not email or not pw: return jsonify({'success': False, 'error': 'Email and password required'}), 400
    result = login_user(email, pw)
    return jsonify(result), (200 if result['success'] else 401)

@app.route('/api/auth/user/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    user = get_user(user_id)
    if not user: return jsonify({'error': 'User not found'}), 404
    return jsonify(user)

@app.route('/api/auth/user/<user_id>/groups', methods=['GET'])
def get_user_groups(user_id):
    user = get_user(user_id)
    if not user: return jsonify({'groups': []}), 404
    user_name = user.get('name', '')
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT g.group_id, g.name as group_name, g.created_at
                FROM groups_table g
                LEFT JOIN members m ON g.group_id = m.group_id
                WHERE g.created_by = %s OR m.user_id = %s OR m.name = %s
                ORDER BY g.created_at DESC
            """, (user_id, user_id, user_name))
            rows = cur.fetchall()
        conn.close()
        return jsonify({'groups': [
            {'group_id': r['group_id'], 'group_name': r['group_name'], 'created_at': str(r['created_at'])}
            for r in rows
        ]})
    except Exception as e:
        return jsonify({'groups': [], 'error': str(e)}), 500

@app.route('/api/auth/preferences/<user_id>', methods=['PUT'])
def update_user_preferences(user_id):
    d = request.json
    return jsonify(update_preferences(user_id, d.get('travel_preferences', {})))

# ══════════════════════════════════════════════════════════════════════════
# GROUPS
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/group/create', methods=['POST'])
def create_group():
    d          = request.json
    group_name = d.get('group_name', 'My Travel Group')
    members    = d.get('members', [])
    user_id    = d.get('user_id', '')
    group_id   = f"group_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO groups_table (group_id, name, created_by) VALUES (%s, %s, %s)",
                (group_id, group_name, user_id or None)
            )
            for member in members:
                cur.execute(
                    "INSERT INTO members (group_id, name, user_id) VALUES (%s, %s, %s)",
                    (group_id, member, user_id or None)
                )
        conn.commit()
        conn.close()
        if user_id: add_group_to_user(user_id, group_id, group_name)
        return jsonify({'success': True, 'group_id': group_id, 'group_name': group_name})
    except Exception as e:
        print(f"create_group error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/group/join', methods=['POST'])
def join_group():
    d        = request.json
    group_id = d.get('group_id', '').strip()
    member   = d.get('member_name', '').strip()
    user_id  = d.get('user_id', '')
    email    = d.get('email', '')
    if not group_id or not member:
        return jsonify({'success': False, 'error': 'Group ID and name required'}), 400
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM groups_table WHERE group_id = %s", (group_id,))
            group = cur.fetchone()
            if not group: return jsonify({'success': False, 'error': 'Group not found'}), 404
            cur.execute("SELECT id FROM members WHERE group_id = %s AND name = %s", (group_id, member))
            if cur.fetchone(): return jsonify({'success': False, 'error': 'Already a member'}), 400
            cur.execute(
                "INSERT INTO members (group_id, name, user_id, email) VALUES (%s, %s, %s, %s)",
                (group_id, member, user_id or None, email)
            )
        conn.commit()
        conn.close()
        if user_id: add_group_to_user(user_id, group_id, group['name'])
        return jsonify({'success': True, 'group_id': group_id, 'group_name': group['name'],
                        'message': f'Welcome to {group["name"]}!'})
    except Exception as e:
        print(f"join_group error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/group/<group_id>', methods=['GET'])
def get_group(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM groups_table WHERE group_id = %s", (group_id,))
            group = cur.fetchone()
            if not group: return jsonify({'error': 'Group not found'}), 404
            cur.execute("SELECT name, user_id, email FROM members WHERE group_id = %s", (group_id,))
            members_rows = cur.fetchall()
            cur.execute("SELECT DISTINCT user_name FROM votes WHERE group_id = %s", (group_id,))
            voters = [r['user_name'] for r in cur.fetchall()]
            cur.execute("SELECT * FROM destinations WHERE group_id = %s ORDER BY created_at ASC", (group_id,))
            destinations = cur.fetchall()
        conn.close()
        members = [r['name'] for r in members_rows]
        return jsonify({
            'group_id':    group_id,
            'name':        group['name'],
            'created_by':  group.get('created_by', ''),
            'voting_open': bool(group.get('voting_open', False)),
            'members':     members,
            'destinations': destinations,
            'voters':      voters,
            'total_votes': len(voters),
            'created_at':  str(group['created_at'])
        })
    except Exception as e:
        print(f"get_group error: {e}")
        return jsonify({'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════
# DESTINATIONS
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/group/<group_id>/destinations', methods=['GET'])
def get_destinations(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM destinations WHERE group_id = %s ORDER BY created_at ASC", (group_id,))
            rows = cur.fetchall()
        conn.close()
        return jsonify({'destinations': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/group/<group_id>/destinations/add', methods=['POST'])
def add_destination(group_id):
    d        = request.json
    name     = d.get('name', '').strip()
    added_by = d.get('added_by', '')
    if not name: return jsonify({'success': False, 'error': 'Name required'}), 400
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM destinations WHERE group_id = %s AND LOWER(name) = LOWER(%s)",
                (group_id, name)
            )
            if cur.fetchone(): return jsonify({'success': False, 'error': 'Already added'}), 400
            cur.execute(
                "INSERT INTO destinations (group_id, name, added_by) VALUES (%s, %s, %s)",
                (group_id, name, added_by)
            )
            cur.execute("SELECT * FROM destinations WHERE group_id = %s ORDER BY created_at ASC", (group_id,))
            destinations = cur.fetchall()
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'destinations': destinations})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/group/<group_id>/destinations/remove', methods=['POST'])
def remove_destination(group_id):
    name = request.json.get('name', '').strip()
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM destinations WHERE group_id = %s AND name = %s", (group_id, name))
            cur.execute("SELECT * FROM destinations WHERE group_id = %s ORDER BY created_at ASC", (group_id,))
            destinations = cur.fetchall()
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'destinations': destinations})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/group/<group_id>/open-voting', methods=['POST'])
def open_voting(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE groups_table SET voting_open = TRUE WHERE group_id = %s", (group_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Voting opened!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════
# VOTES — FIXED submit route
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/vote/submit', methods=['POST'])
def submit_vote():
    """
    Single canonical vote submission endpoint.
    Accepts preferences JSON containing everything:
      destinations[]  — ranked list from survey/vote UI
      budget          — budget level string
      travel_style[]  — style tags from survey
      duration        — int days
      month           — travel month string
      accommodation   — accom preference
      food_pref       — food preference
      raw_votes{}     — {dest: 'up'|'down'} from vote page
    """
    d          = request.json or {}
    group_id   = d.get('group_id', '').strip()
    user_name  = d.get('user_name', '').strip()
    user_id    = d.get('user_id', '') or None   # ← may be absent, that's fine
    preferences = d.get('preferences', {})

    if not group_id:   return jsonify({'error': 'group_id required'}), 400
    if not user_name:  return jsonify({'error': 'user_name required'}), 400

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Verify group exists
            cur.execute("SELECT group_id FROM groups_table WHERE group_id = %s", (group_id,))
            if not cur.fetchone():
                conn.close()
                return jsonify({'error': 'Group not found'}), 404

            # Auto-add user as member if not already present
            cur.execute(
                "SELECT id FROM members WHERE group_id = %s AND name = %s",
                (group_id, user_name)
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO members (group_id, name, user_id) VALUES (%s, %s, %s)",
                    (group_id, user_name, user_id)
                )

            # Upsert vote — ON DUPLICATE KEY UPDATE handles re-votes cleanly
            # NOTE: we store user_id ONLY in the preferences blob too so results
            # page can always retrieve it without relying on the column existing.
            prefs_json = json.dumps(preferences)

            cur.execute("""
                INSERT INTO votes (group_id, user_id, user_name, preferences, submitted_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    preferences  = VALUES(preferences),
                    submitted_at = VALUES(submitted_at)
            """, (group_id, user_id, user_name, prefs_json, datetime.now()))

            # Check if all members have voted
            cur.execute("SELECT COUNT(*) AS cnt FROM members WHERE group_id = %s", (group_id,))
            total_members = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(DISTINCT user_name) AS cnt FROM votes WHERE group_id = %s", (group_id,))
            total_votes = cur.fetchone()['cnt']
            all_voted = (total_votes >= total_members and total_members > 0)

        conn.commit()
        conn.close()
        return jsonify({
            'success':   True,
            'message':   f'Vote recorded for {user_name}',
            'all_voted': all_voted
        })
    except Exception as e:
        print(f"submit_vote ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/vote/status/<group_id>', methods=['GET'])
def vote_status(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM members WHERE group_id = %s", (group_id,))
            all_members = [r['name'] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT user_name FROM votes WHERE group_id = %s", (group_id,))
            voted = [r['user_name'] for r in cur.fetchall()]
        conn.close()
        pending = [m for m in all_members if m not in voted]
        return jsonify({
            'total_members': len(all_members),
            'voted_count':   len(voted),
            'all_voted':     len(pending) == 0 and len(all_members) > 0,
            'voted_names':   voted,
            'pending_names': pending
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vote/results/<group_id>', methods=['GET'])
def get_results(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM groups_table WHERE group_id = %s", (group_id,))
            group = cur.fetchone()
            if not group: return jsonify({'error': 'Group not found'}), 404

            cur.execute("SELECT COUNT(*) AS cnt FROM members WHERE group_id = %s", (group_id,))
            total_members = cur.fetchone()['cnt']

            cur.execute("SELECT user_name, preferences FROM votes WHERE group_id = %s", (group_id,))
            rows = cur.fetchall()
        conn.close()

        voted_count = len(rows)
        if voted_count == 0:
            return jsonify({'error': 'No votes yet'}), 400

        # Gate: show results only after all members voted
        if voted_count < total_members:
            return jsonify({
                'error':          'not_all_voted',
                'message':        f'Waiting for {total_members - voted_count} more member(s) to vote',
                'voted_count':    voted_count,
                'total_members':  total_members
            }), 202

        # Parse preferences and build vote objects for the engine
        votes = {}
        for row in rows:
            prefs = row['preferences']
            if isinstance(prefs, str):
                prefs = json.loads(prefs)
            votes[row['user_name']] = {'preferences': prefs}

        consensus       = voting_engine.calculate_consensus(votes)
        recommendations = recommender.get_recommendations(consensus)

        # Tie detection
        tie_result = _detect_tie(consensus)
        if tie_result['is_tie']:
            tie_result['survey_winner'] = _resolve_tie_by_survey(
                tie_result['tied_destinations'], votes
            )

        return jsonify({
            'group_id':       group_id,
            'group_name':     group['name'],
            'total_votes':    voted_count,
            'total_members':  total_members,
            'consensus':      consensus,
            'recommendations': recommendations,
            'tie':            tie_result
        })
    except Exception as e:
        print(f"get_results ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ── Survey-to-destination pipeline ────────────────────────────────────────
@app.route('/api/vote/custom-destinations', methods=['POST'])
def save_custom_destinations():
    """
    When a user submits the survey, any destinations they picked that aren't
    in the preset list are saved here. The creator's vote.html then loads
    these custom destinations alongside preset ones.
    """
    d          = request.json or {}
    group_id   = d.get('group_id', '')
    user_name  = d.get('user_name', '')
    dests      = d.get('destinations', [])
    if not group_id or not dests:
        return jsonify({'success': False, 'error': 'group_id and destinations required'}), 400
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            for dest in dests:
                cur.execute(
                    "SELECT id FROM custom_destinations WHERE group_id=%s AND destination=%s",
                    (group_id, dest)
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO custom_destinations (group_id, user_name, destination) VALUES (%s, %s, %s)",
                        (group_id, user_name, dest)
                    )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'saved': len(dests)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _detect_tie(consensus):
    top = consensus.get('top_destinations', [])
    if len(top) < 2: return {'is_tie': False}
    top_score = top[0]['score']
    tied = [d for d in top if d['score'] == top_score]
    if len(tied) > 1:
        return {
            'is_tie': True,
            'tied_destinations': [d['destination'] for d in tied],
            'tied_score': top_score,
            'survey_winner': None
        }
    return {'is_tie': False}

def _resolve_tie_by_survey(tied_destinations, votes):
    style_counts  = defaultdict(int)
    budget_counts = defaultdict(int)
    month_counts  = defaultdict(int)
    for user, vote_data in votes.items():
        prefs = vote_data.get('preferences', {})
        for s in prefs.get('travel_style', []): style_counts[s] += 1
        budget_counts[prefs.get('budget', 'medium')] += 1
        month_counts[prefs.get('month', 'December')]  += 1
    top_styles  = sorted(style_counts, key=style_counts.get, reverse=True)[:3]
    top_budget  = max(budget_counts, key=budget_counts.get) if budget_counts else 'medium'
    top_month   = max(month_counts,  key=month_counts.get)  if month_counts  else 'December'
    budget_map  = {'low': 1, 'medium': 2, 'high': 3, 'luxury': 4}
    dest_scores = []
    for dest_name in tied_destinations:
        info  = recommender.DESTINATIONS.get(dest_name, {})
        score = 0
        matched = [s for s in top_styles if s in info.get('tags', [])]
        score += (len(matched) / max(len(top_styles), 1)) * 40
        dest_budget = budget_map.get(info.get('budget_level', 'medium'), 2)
        user_budget = budget_map.get(top_budget, 2)
        score += max(0, 30 - abs(dest_budget - user_budget) * 10)
        if top_month in info.get('best_months', []): score += 20
        if info.get('avg_cost_per_day', 0) > 0:      score += 10
        parts = []
        if matched: parts.append(f"matches {', '.join(matched)} interests")
        if top_month in info.get('best_months', []): parts.append(f"{top_month} is ideal")
        if info.get('budget_level') == top_budget:   parts.append(f"fits {top_budget} budget")
        reason = (f"{dest_name} " + ' and '.join(parts)) if parts else f"{dest_name} best matches survey"
        dest_scores.append({'destination': dest_name, 'score': round(score, 1), 'reason': reason})
    dest_scores.sort(key=lambda x: x['score'], reverse=True)
    return {
        'winner':       dest_scores[0]['destination'] if dest_scores else tied_destinations[0],
        'reason':       dest_scores[0]['reason']      if dest_scores else 'Best match by survey',
        'group_styles': top_styles,
        'group_budget': top_budget,
        'group_month':  top_month,
        'all_scores':   dest_scores
    }

# ══════════════════════════════════════════════════════════════════════════
# WEATHER
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/weather/<destination>', methods=['GET'])
def get_weather(destination):
    return jsonify(travel_api.get_weather(destination))

# ══════════════════════════════════════════════════════════════════════════
# ITINERARY
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/itinerary/generate', methods=['POST'])
def generate_itinerary():
    d            = request.json
    destination  = d.get('destination')
    duration     = d.get('duration', 7)
    budget       = d.get('budget', 'medium')
    travel_style = d.get('travel_style', ['culture'])
    month        = d.get('month', 'December')
    weather      = travel_api.get_weather(destination)
    places       = travel_api.get_places(destination, travel_style)
    cost_estimate = travel_api.estimate_cost(destination, duration, budget)
    itinerary = {
        'destination':    destination,
        'duration':       duration,
        'budget':         budget,
        'month':          month,
        'weather':        weather,
        'estimated_cost': cost_estimate,
        'days':           _build_day_plan(places, duration),
        'generated_at':   datetime.now().isoformat()
    }
    return jsonify({'success': True, 'itinerary': itinerary})

@app.route('/api/itinerary/ai-generate', methods=['POST'])
def ai_generate_itinerary():
    if not AI_AVAILABLE: return jsonify({'error': 'AI not available — add GROQ_API_KEY'}), 503
    d           = request.json
    destination = d.get('destination', '')
    if not destination: return jsonify({'error': 'Destination required'}), 400
    try:
        itinerary = generate_ai_itinerary(
            destination   = destination,
            duration      = d.get('duration', 5),
            budget        = d.get('budget', 'medium'),
            travel_styles = d.get('travel_style', ['culture']),
            month         = d.get('month', 'December'),
            group_size    = d.get('group_size', 4),
            food_pref     = d.get('food_pref', 'both'),
            group_type    = d.get('group_type', 'friends')
        )
        return jsonify({'success': True, 'itinerary': itinerary})
    except Exception as e:
        print(f"ai_generate error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/itinerary/group/<group_id>', methods=['GET'])
def get_group_itinerary(group_id):
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT itinerary, ai_powered, created_at FROM itineraries WHERE group_id = %s ORDER BY created_at DESC LIMIT 1",
                (group_id,)
            )
            row = cur.fetchone()
        conn.close()
        if not row: return jsonify({'error': 'No itinerary yet'}), 404
        itin = row['itinerary']
        if isinstance(itin, str): itin = json.loads(itin)
        return jsonify({'success': True, 'itinerary': itin, 'ai_powered': row['ai_powered'],
                        'created_at': str(row['created_at'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _build_day_plan(places, duration):
    days        = []
    place_index = 0
    all_places  = places.get('attractions', []) + places.get('restaurants', [])
    themes = ['Arrival & Exploration', 'Main Attractions', 'Culture & Heritage',
              'Adventure Day', 'Food & Markets', 'Leisure & Local Life', 'Departure Day']
    for day_num in range(1, duration + 1):
        day_places = []
        for _ in range(3):
            if place_index < len(all_places):
                day_places.append(all_places[place_index])
                place_index += 1
        days.append({
            'day':        day_num,
            'title':      f'Day {day_num} — {themes[(day_num - 1) % len(themes)]}',
            'activities': day_places
        })
    return days

# ══════════════════════════════════════════════════════════════════════════
# DEEP LINKS
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/deeplinks', methods=['POST'])
def get_deeplinks():
    d           = request.json
    destination = d.get('destination', '')
    if not destination: return jsonify({'error': 'Destination required'}), 400
    try:
        links = travel_api.get_deeplinks(destination, d.get('duration', 7), d.get('budget', 'medium'))
        return jsonify({'success': True, 'links': links, 'destination': destination})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/expenses/<group_id>', methods=['GET'])
def get_group_expenses(group_id): return jsonify(get_expenses(group_id))

@app.route('/api/expenses/add', methods=['POST'])
def add_group_expense():
    d = request.json
    if not all([d.get('group_id'), d.get('paid_by'), d.get('amount'),
                d.get('description'), d.get('split_among')]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    return jsonify(add_expense(
        d['group_id'], d['paid_by'], d['amount'], d['description'],
        d.get('category', 'other'), d['split_among'], d.get('split_type', 'equal')
    ))

@app.route('/api/expenses/delete/<group_id>/<expense_id>', methods=['DELETE'])
def delete_group_expense(group_id, expense_id):
    return jsonify(delete_expense(group_id, expense_id))

@app.route('/api/expenses/stats/<group_id>', methods=['GET'])
def expense_stats(group_id): return jsonify(get_expense_stats(group_id))

# ══════════════════════════════════════════════════════════════════════════
# PLANNER
# ══════════════════════════════════════════════════════════════════════════
@app.route('/api/planner/<group_id>', methods=['GET'])
def get_group_tasks(group_id): return jsonify(get_tasks(group_id))

@app.route('/api/planner/add', methods=['POST'])
def add_group_task():
    d        = request.json
    group_id = d.get('group_id')
    title    = d.get('title', '').strip()
    if not group_id or not title:
        return jsonify({'success': False, 'error': 'Group ID and title required'}), 400
    return jsonify(add_task(
        group_id    = group_id,
        title       = title,
        description = d.get('description', ''),
        category    = d.get('category', 'other'),
        assigned_to = d.get('assigned_to', 'Unassigned'),
        priority    = d.get('priority', 'medium'),
        due_date    = d.get('due_date', '')
    ))

@app.route('/api/planner/toggle/<group_id>/<task_id>', methods=['PUT'])
def toggle_group_task(group_id, task_id): return jsonify(toggle_task(group_id, task_id))

@app.route('/api/planner/delete/<group_id>/<task_id>', methods=['DELETE'])
def delete_group_task(group_id, task_id): return jsonify(delete_task(group_id, task_id))

@app.route('/api/planner/generate', methods=['POST'])
def generate_tasks():
    d        = request.json
    group_id = d.get('group_id')
    if not group_id: return jsonify({'success': False, 'error': 'Group ID required'}), 400
    return jsonify(generate_default_tasks(
        group_id, d.get('destination', 'your destination'),
        d.get('duration', 7), d.get('members', [])
    ))

if __name__ == '__main__':
    print("🌍 PackVote starting...")
    print("📍 http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
