import pymysql
import os

DB_CONFIG = {
    'host':     os.environ.get('MYSQLHOST',     'interchange.proxy.rlwy.net'),
    'port':     int(os.environ.get('MYSQLPORT', 33572)),
    'user':     os.environ.get('MYSQLUSER',     'root'),
    'password': os.environ.get('MYSQLPASSWORD', 'REiwchuHZrPHemrkXWVHGxYJoYcUCBDE'),
    'database': os.environ.get('MYSQLDATABASE', 'railway'),
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 30,
    'charset': 'utf8mb4'
}

def get_connection():
    return pymysql.connect(**DB_CONFIG)

def execute_query(query, params=(), fetch=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
            else:
                conn.commit()
                result = None
        return result
    finally:
        conn.close()

def execute_one(query, params=()):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            result = cur.fetchone()
        return result
    finally:
        conn.close()

def _safe_alter(cur, sql, msg_ok, msg_skip):
    try:
        cur.execute(sql)
        print(f"✅ {msg_ok}")
    except Exception:
        print(f"ℹ️  {msg_skip}")

def init_db():
    conn = get_connection()
    with conn.cursor() as cur:

        # ── Core tables ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS groups_table (
                group_id    VARCHAR(50)  PRIMARY KEY,
                name        VARCHAR(150) NOT NULL,
                created_by  VARCHAR(50),
                voting_open BOOLEAN DEFAULT FALSE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id        INT AUTO_INCREMENT PRIMARY KEY,
                group_id  VARCHAR(50)  NOT NULL,
                user_id   VARCHAR(50),
                name      VARCHAR(100) NOT NULL,
                email     VARCHAR(100),
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS destinations (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                group_id   VARCHAR(50) NOT NULL,
                name       VARCHAR(150) NOT NULL,
                added_by   VARCHAR(100),
                up_votes   INT DEFAULT 0,
                down_votes INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── VOTES table — preferences JSON stores everything ─────────────
        # This is the canonical schema used by app.py routes.
        # preferences JSON contains: destinations[], budget, travel_style[],
        # duration, month, accommodation, food_pref, raw_votes{}
        cur.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                group_id     VARCHAR(50)  NOT NULL,
                user_id      VARCHAR(50)  DEFAULT NULL,
                user_name    VARCHAR(100) NOT NULL,
                preferences  JSON,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_group_user (group_id, user_name)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS itineraries (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                group_id    VARCHAR(50) NOT NULL,
                destination VARCHAR(150),
                duration    INT,
                itinerary   JSON,
                ai_powered  BOOLEAN DEFAULT FALSE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id   VARCHAR(50)   PRIMARY KEY,
                group_id     VARCHAR(50)   NOT NULL,
                paid_by      VARCHAR(100)  NOT NULL,
                amount       DECIMAL(12,2) NOT NULL,
                description  VARCHAR(200)  NOT NULL,
                category     VARCHAR(30)   DEFAULT 'other',
                split_among  JSON,
                splits       JSON,
                split_type   VARCHAR(20)   DEFAULT 'equal',
                expense_date DATE,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id      VARCHAR(50)  PRIMARY KEY,
                group_id     VARCHAR(50)  NOT NULL,
                title        VARCHAR(200) NOT NULL,
                description  TEXT,
                category     VARCHAR(30)  DEFAULT 'other',
                assigned_to  VARCHAR(100) DEFAULT 'Unassigned',
                priority     VARCHAR(20)  DEFAULT 'medium',
                due_date     DATE,
                completed    BOOLEAN DEFAULT FALSE,
                completed_at DATETIME,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── User tables ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    VARCHAR(50) PRIMARY KEY,
                name       VARCHAR(100),
                email      VARCHAR(100) UNIQUE,
                phone      VARCHAR(20)  UNIQUE,
                dob        DATE,
                password   VARCHAR(255),
                token      VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id       VARCHAR(50) PRIMARY KEY,
                budget        VARCHAR(20),
                trip_duration INT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_travel_styles (
                id      INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50),
                style   VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_fav_destinations (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                user_id     VARCHAR(50),
                destination VARCHAR(100),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # ── Custom destinations (from survey) ────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS custom_destinations (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                group_id    VARCHAR(50),
                user_name   VARCHAR(100),
                destination VARCHAR(150),
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Safe ALTER statements (add missing columns) ──────────────────
        _safe_alter(cur,
            "ALTER TABLE groups_table ADD COLUMN voting_open BOOLEAN DEFAULT FALSE",
            "voting_open column added", "voting_open already exists")

        # KEY FIX: Add `preferences` JSON column — missing on old DB instances
        _safe_alter(cur,
            "ALTER TABLE votes ADD COLUMN preferences JSON",
            "preferences column added to votes ✅", "preferences already exists")

        _safe_alter(cur,
            "ALTER TABLE votes ADD COLUMN user_id VARCHAR(50) DEFAULT NULL",
            "user_id added to votes", "user_id already exists in votes")

        _safe_alter(cur,
            "ALTER TABLE members ADD COLUMN user_id VARCHAR(50)",
            "user_id added to members", "user_id already exists in members")

        _safe_alter(cur,
            "ALTER TABLE members ADD COLUMN email VARCHAR(100)",
            "email added to members", "email already exists in members")

    conn.commit()
    conn.close()
    print("✅ DB tables ready")

if __name__ == '__main__':
    init_db()