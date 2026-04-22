import json
from collections import defaultdict
from datetime import datetime
from database import execute_query, execute_one


class VotingEngine:
    """
    Borda Count voting engine.

    Each voter submits preferences = {
        destinations: ["Goa", "Jaipur", "Kerala"],   ← ranked list (index 0 = top choice)
        budget: "medium",
        travel_style: ["beach", "food"],
        duration: 7,
        month: "December",
        ...
    }

    Borda points: for n destinations, rank-0 gets n pts, rank-1 gets n-1 pts, etc.
    The destination with the highest total Borda points wins.
    """

    def calculate_consensus(self, votes_input):
        """
        votes_input can be either:
          - dict  {user_name: {'preferences': {...}}}   ← from app.py get_results
          - list  [row_dict with 'preferences' JSON]    ← from legacy calls
        """
        # Normalise to list of preference dicts
        if isinstance(votes_input, dict):
            prefs_list = [v.get('preferences', {}) for v in votes_input.values()]
        else:
            prefs_list = []
            for row in votes_input:
                p = row.get('preferences', {})
                if isinstance(p, str):
                    try: p = json.loads(p)
                    except: p = {}
                prefs_list.append(p)

        destination_scores = defaultdict(float)
        budget_votes       = defaultdict(int)
        style_votes        = defaultdict(int)
        duration_votes     = []
        month_votes        = defaultdict(int)

        total_voters = len(prefs_list)

        for prefs in prefs_list:
            if isinstance(prefs, str):
                try: prefs = json.loads(prefs)
                except: prefs = {}

            # destinations can be stored under 'destinations' or 'preferences.destinations'
            destinations = prefs.get('destinations', [])
            travel_style = prefs.get('travel_style', prefs.get('activities', []))
            budget       = prefs.get('budget', 'medium')
            duration     = int(prefs.get('duration', 7))
            month        = prefs.get('month', 'December')

            # Ensure lists
            if isinstance(destinations, str):
                try: destinations = json.loads(destinations)
                except: destinations = [destinations] if destinations else []
            if isinstance(travel_style, str):
                try: travel_style = json.loads(travel_style)
                except: travel_style = [travel_style] if travel_style else []

            # ── Borda count ───────────────────────────────────────────────
            n = len(destinations)
            for rank, dest in enumerate(destinations):
                if dest:
                    destination_scores[dest] += (n - rank)

            budget_votes[budget]  += 1
            for style in travel_style:
                if style: style_votes[style] += 1
            duration_votes.append(duration)
            month_votes[month]    += 1

        # Sort destinations by score
        sorted_dests = sorted(destination_scores.items(), key=lambda x: x[1], reverse=True)
        max_score    = max(destination_scores.values()) if destination_scores else 1

        top_destinations = [
            {
                'destination': dest,
                'score':       score,
                'percentage':  round(score / max_score * 100)
            }
            for dest, score in sorted_dests[:5]
        ]

        consensus_budget = max(budget_votes, key=budget_votes.get) if budget_votes else 'medium'
        sorted_styles    = sorted(style_votes.items(), key=lambda x: x[1], reverse=True)
        top_styles       = [s for s, _ in sorted_styles[:3]]
        avg_duration     = round(sum(duration_votes) / len(duration_votes)) if duration_votes else 7
        consensus_month  = max(month_votes, key=month_votes.get) if month_votes else 'December'

        conflicts = self._detect_conflicts(prefs_list, consensus_budget, avg_duration)

        return {
            'top_destinations': top_destinations,
            'winner':           top_destinations[0]['destination'] if top_destinations else None,
            'consensus_budget': consensus_budget,
            'top_styles':       top_styles,
            'avg_duration':     avg_duration,
            'consensus_month':  consensus_month,
            'total_voters':     total_voters,
            'conflicts':        conflicts,
            'score_breakdown':  dict(destination_scores)
        }

    def _detect_conflicts(self, prefs_list, consensus_budget, avg_duration):
        conflicts  = []
        budget_map = {'low': 1, 'medium': 2, 'high': 3, 'luxury': 4}
        cons_level = budget_map.get(consensus_budget, 2)
        for i, prefs in enumerate(prefs_list):
            user_name   = f"Member {i+1}"
            user_budget = prefs.get('budget', 'medium')
            user_level  = budget_map.get(user_budget, 2)
            if abs(user_level - cons_level) >= 2:
                conflicts.append({
                    'type':     'budget',
                    'message':  f'{user_name} prefers {user_budget} vs group consensus {consensus_budget}',
                    'severity': 'high'
                })
            user_dur = int(prefs.get('duration', 7))
            if abs(user_dur - avg_duration) > 3:
                conflicts.append({
                    'type':     'duration',
                    'message':  f'{user_name} wants {user_dur} days vs group avg {avg_duration} days',
                    'severity': 'medium'
                })
        return conflicts


# ── Standalone helper functions (used by legacy code paths) ───────────────

def create_group(group_name, members, user_id=''):
    group_id = f"group_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    execute_query(
        "INSERT INTO groups_table (group_id, name, created_by, created_at) VALUES (%s, %s, %s, %s)",
        (group_id, group_name, user_id or None, datetime.now()), fetch=False
    )
    for member in members:
        execute_query(
            "INSERT INTO members (group_id, name) VALUES (%s, %s)",
            (group_id, member), fetch=False
        )
    return {'success': True, 'group_id': group_id, 'group_name': group_name}


def get_group(group_id):
    group = execute_one("SELECT * FROM groups_table WHERE group_id = %s", (group_id,))
    if not group: return None
    members    = execute_query("SELECT name FROM members WHERE group_id = %s", (group_id,), fetch=True) or []
    vote_count = execute_one("SELECT COUNT(*) AS cnt FROM votes WHERE group_id = %s", (group_id,))
    return {
        'group_id':    group_id,
        'name':        group['name'],
        'members':     [m['name'] for m in members],
        'total_votes': vote_count['cnt'] if vote_count else 0,
        'created_at':  str(group['created_at'])
    }


def get_group_destinations(group_id):
    """Returns all unique destinations submitted in surveys for this group."""
    votes = execute_query(
        "SELECT preferences FROM votes WHERE group_id = %s",
        (group_id,), fetch=True
    ) or []
    customs = execute_query(
        "SELECT DISTINCT destination FROM custom_destinations WHERE group_id = %s",
        (group_id,), fetch=True
    ) or []

    all_dests = set()
    for v in votes:
        prefs = v.get('preferences', {})
        if isinstance(prefs, str):
            try: prefs = json.loads(prefs)
            except: prefs = {}
        for d in prefs.get('destinations', []):
            if d: all_dests.add(d)
    for c in customs:
        all_dests.add(c['destination'])

    return {'destinations': list(all_dests)}


def save_custom_destinations(group_id, user_name, destinations):
    for dest in destinations:
        existing = execute_one(
            "SELECT id FROM custom_destinations WHERE group_id=%s AND destination=%s",
            (group_id, dest)
        )
        if not existing:
            execute_query(
                "INSERT INTO custom_destinations (group_id, user_name, destination) VALUES (%s, %s, %s)",
                (group_id, user_name, dest), fetch=False
            )
    return {'success': True, 'saved': len(destinations)}