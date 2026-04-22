"""
migrate_votes.py — Run this ONCE to fix the votes table schema.

The old schema had separate columns: destinations, budget, travel_style, duration, month
The new schema stores everything in a single `preferences` JSON column.

This script:
1. Adds the `preferences` JSON column if missing
2. Migrates all existing rows into the new column
3. Keeps the old columns intact (safe, non-destructive)

Run: python migrate_votes.py
"""

import json
import pymysql
import os

DB_CONFIG = {
    'host':        os.environ.get('MYSQLHOST',     'interchange.proxy.rlwy.net'),
    'port':        int(os.environ.get('MYSQLPORT', 33572)),
    'user':        os.environ.get('MYSQLUSER',     'root'),
    'password':    os.environ.get('MYSQLPASSWORD', 'REiwchuHZrPHemrkXWVHGxYJoYcUCBDE'),
    'database':    os.environ.get('MYSQLDATABASE', 'railway'),
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 30,
    'charset': 'utf8mb4'
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

def run():
    conn = get_conn()
    try:
        with conn.cursor() as cur:

            # ── 1. Show current votes table columns ───────────────────────
            cur.execute("DESCRIBE votes")
            cols = {row['Field']: row for row in cur.fetchall()}
            print("Current votes columns:", list(cols.keys()))

            # ── 2. Add `preferences` JSON column if missing ───────────────
            if 'preferences' not in cols:
                print("Adding `preferences` JSON column...")
                cur.execute("ALTER TABLE votes ADD COLUMN preferences JSON")
                conn.commit()
                print("✅ Column added.")
            else:
                print("ℹ️  `preferences` column already exists.")

            # ── 3. Add `user_id` column if missing ────────────────────────
            if 'user_id' not in cols:
                print("Adding `user_id` column...")
                cur.execute("ALTER TABLE votes ADD COLUMN user_id VARCHAR(50) DEFAULT NULL")
                conn.commit()
                print("✅ user_id column added.")
            else:
                print("ℹ️  `user_id` column already exists.")

            # ── 4. Migrate old rows → preferences JSON ────────────────────
            # Fetch all rows that have NULL preferences but have old-style columns
            old_cols = [c for c in ['destinations', 'budget', 'travel_style', 'duration', 'month'] if c in cols]
            print(f"Old-style columns found: {old_cols}")

            if old_cols:
                cur.execute("SELECT * FROM votes WHERE preferences IS NULL")
                old_rows = cur.fetchall()
                print(f"Rows needing migration: {len(old_rows)}")

                migrated = 0
                for row in old_rows:
                    # Parse destinations
                    dests = row.get('destinations', '[]') or '[]'
                    if isinstance(dests, str):
                        try:    dests = json.loads(dests)
                        except: dests = [dests] if dests else []

                    # Parse travel_style
                    styles = row.get('travel_style', '[]') or '[]'
                    if isinstance(styles, str):
                        try:    styles = json.loads(styles)
                        except: styles = [styles] if styles else []

                    prefs = {
                        'destinations':  dests,
                        'budget':        row.get('budget', 'medium') or 'medium',
                        'travel_style':  styles,
                        'duration':      int(row.get('duration', 7) or 7),
                        'month':         row.get('month', 'December') or 'December',
                        'accommodation': 'hotel',
                        'food_pref':     'both',
                        'raw_votes':     {}
                    }

                    cur.execute(
                        "UPDATE votes SET preferences = %s WHERE id = %s",
                        (json.dumps(prefs), row['id'])
                    )
                    migrated += 1

                conn.commit()
                print(f"✅ Migrated {migrated} rows to preferences JSON.")
            else:
                print("ℹ️  No old-style columns to migrate from.")

            # ── 5. Fix UNIQUE KEY if it's on wrong columns ────────────────
            # The new code needs UNIQUE(group_id, user_name)
            cur.execute("SHOW INDEX FROM votes WHERE Key_name != 'PRIMARY'")
            indexes = cur.fetchall()
            print("Current indexes:", [(i['Key_name'], i['Column_name']) for i in indexes])

            # Check if the unique key already exists on (group_id, user_name)
            uq_exists = any(
                i['Key_name'] == 'uq_group_user'
                for i in indexes
            )
            if not uq_exists:
                # Drop any old unique keys first
                unique_keys = set(i['Key_name'] for i in indexes if i['Non_unique'] == 0 and i['Key_name'] != 'PRIMARY')
                for key in unique_keys:
                    try:
                        print(f"Dropping old unique key: {key}")
                        cur.execute(f"ALTER TABLE votes DROP INDEX `{key}`")
                    except Exception as e:
                        print(f"  Could not drop {key}: {e}")

                try:
                    print("Adding UNIQUE KEY uq_group_user(group_id, user_name)...")
                    cur.execute("ALTER TABLE votes ADD UNIQUE KEY uq_group_user (group_id, user_name)")
                    conn.commit()
                    print("✅ Unique key added.")
                except Exception as e:
                    print(f"  Could not add unique key (may already exist): {e}")
            else:
                print("ℹ️  uq_group_user unique key already exists.")

            # ── 6. Also ensure custom_destinations table exists ───────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_destinations (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    group_id    VARCHAR(50),
                    user_name   VARCHAR(100),
                    destination VARCHAR(150),
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("✅ custom_destinations table OK.")

            # ── 7. Final check ────────────────────────────────────────────
            cur.execute("DESCRIBE votes")
            final_cols = [row['Field'] for row in cur.fetchall()]
            print("\n✅ Final votes table columns:", final_cols)
            print("\n🎉 Migration complete! You can now restart app.py")

    finally:
        conn.close()

if __name__ == '__main__':
    run()