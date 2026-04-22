import hashlib
import uuid
from datetime import datetime
from database import get_connection, execute_one

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(name, dob, email, phone, password, travel_preferences={}):
    existing_email = execute_one("SELECT user_id FROM users WHERE email = %s", (email,))
    if existing_email:
        return {'success': False, 'error': 'Email already registered'}

    existing_phone = execute_one("SELECT user_id FROM users WHERE phone = %s", (phone,))
    if existing_phone:
        return {'success': False, 'error': 'Phone number already registered'}

    user_id = str(uuid.uuid4())[:8]
    token   = str(uuid.uuid4())

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, name, email, phone, dob, password, token)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, name, email, phone, dob, hash_password(password), token))

            budget        = travel_preferences.get('budget', 'medium')
            trip_duration = travel_preferences.get('trip_duration', 7)
            cur.execute("""
                INSERT INTO user_preferences (user_id, budget, trip_duration)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE budget=VALUES(budget), trip_duration=VALUES(trip_duration)
            """, (user_id, budget, trip_duration))

            for style in travel_preferences.get('travel_styles', []):
                cur.execute("INSERT INTO user_travel_styles (user_id, style) VALUES (%s, %s)", (user_id, style))

            for dest in travel_preferences.get('fav_destinations', []):
                cur.execute("INSERT INTO user_fav_destinations (user_id, destination) VALUES (%s, %s)", (user_id, dest))

        conn.commit()
    finally:
        conn.close()

    return {
        'success': True, 'user_id': user_id, 'name': name,
        'dob': dob, 'email': email, 'phone': phone, 'token': token,
        'travel_preferences': {
            'budget': travel_preferences.get('budget', 'medium'),
            'trip_duration': travel_preferences.get('trip_duration', 7),
            'travel_styles': travel_preferences.get('travel_styles', []),
            'fav_destinations': travel_preferences.get('fav_destinations', [])
        }
    }

def login_user(email, password):
    user = execute_one(
        "SELECT * FROM users WHERE email = %s AND password = %s",
        (email, hash_password(password))
    )
    if not user:
        return {'success': False, 'error': 'Invalid email or password'}

    new_token = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET token=%s WHERE user_id=%s", (new_token, user['user_id']))
            cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user['user_id'],))
            prefs = cur.fetchone()
            cur.execute("SELECT style FROM user_travel_styles WHERE user_id=%s", (user['user_id'],))
            styles = cur.fetchall() or []
            cur.execute("SELECT destination FROM user_fav_destinations WHERE user_id=%s", (user['user_id'],))
            dests = cur.fetchall() or []
            # Get groups via members table
            cur.execute("""
                SELECT g.group_id, g.name as group_name, g.created_at as joined_at
                FROM members m
                JOIN groups_table g ON g.group_id = m.group_id
                WHERE m.name = %s OR m.user_id = %s
                ORDER BY g.created_at DESC
            """, (user['name'], user['user_id']))
            groups = cur.fetchall() or []
        conn.commit()
    finally:
        conn.close()

    return {
        'success': True,
        'user_id': user['user_id'],
        'name':    user['name'],
        'dob':     user['dob'],
        'email':   user['email'],
        'phone':   user['phone'],
        'token':   new_token,
        'groups':  [{'group_id': g['group_id'], 'group_name': g['group_name'], 'joined_at': str(g['joined_at'])} for g in groups],
        'travel_preferences': {
            'budget':           prefs['budget']        if prefs else 'medium',
            'trip_duration':    prefs['trip_duration'] if prefs else 7,
            'travel_styles':    [s['style']       for s in styles],
            'fav_destinations': [d['destination'] for d in dests]
        }
    }

def get_user(user_id):
    user = execute_one("SELECT * FROM users WHERE user_id=%s", (user_id,))
    if not user:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
            prefs = cur.fetchone()
            cur.execute("SELECT style FROM user_travel_styles WHERE user_id=%s", (user_id,))
            styles = cur.fetchall() or []
            cur.execute("SELECT destination FROM user_fav_destinations WHERE user_id=%s", (user_id,))
            dests = cur.fetchall() or []
            cur.execute("""
                SELECT g.group_id, g.name as group_name, g.created_at as joined_at
                FROM members m
                JOIN groups_table g ON g.group_id = m.group_id
                WHERE m.name = %s OR m.user_id = %s
                ORDER BY g.created_at DESC
            """, (user['name'], user_id))
            groups = cur.fetchall() or []
    finally:
        conn.close()

    return {
        'user_id': user_id,
        'name':    user['name'],
        'dob':     user['dob'],
        'email':   user['email'],
        'phone':   user['phone'],
        'groups':  [{'group_id': g['group_id'], 'group_name': g['group_name'], 'joined_at': str(g['joined_at'])} for g in groups],
        'travel_preferences': {
            'budget':           prefs['budget']        if prefs else 'medium',
            'trip_duration':    prefs['trip_duration'] if prefs else 7,
            'travel_styles':    [s['style']       for s in styles],
            'fav_destinations': [d['destination'] for d in dests]
        }
    }

def update_preferences(user_id, travel_preferences):
    user = execute_one("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
    if not user:
        return {'success': False, 'error': 'User not found'}
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_preferences (user_id, budget, trip_duration)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE budget=VALUES(budget), trip_duration=VALUES(trip_duration)
            """, (user_id, travel_preferences.get('budget','medium'), travel_preferences.get('trip_duration',7)))
            cur.execute("DELETE FROM user_travel_styles WHERE user_id=%s", (user_id,))
            for style in travel_preferences.get('travel_styles', []):
                cur.execute("INSERT INTO user_travel_styles (user_id,style) VALUES(%s,%s)", (user_id, style))
            cur.execute("DELETE FROM user_fav_destinations WHERE user_id=%s", (user_id,))
            for dest in travel_preferences.get('fav_destinations', []):
                cur.execute("INSERT INTO user_fav_destinations (user_id,destination) VALUES(%s,%s)", (user_id, dest))
        conn.commit()
    finally:
        conn.close()
    return {'success': True}

def add_group_to_user(user_id, group_id, group_name):
    pass  # handled via members table