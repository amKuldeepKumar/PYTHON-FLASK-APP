import sqlite3

db_path = r"instance\app.db"

columns_to_add = [
    ("is_published", "ALTER TABLE speaking_topics ADD COLUMN is_published BOOLEAN DEFAULT 1"),
    ("access_type", "ALTER TABLE speaking_topics ADD COLUMN access_type TEXT DEFAULT 'free'"),
    ("price", "ALTER TABLE speaking_topics ADD COLUMN price REAL DEFAULT 0"),
    ("discount_price", "ALTER TABLE speaking_topics ADD COLUMN discount_price REAL"),
    ("currency", "ALTER TABLE speaking_topics ADD COLUMN currency TEXT DEFAULT 'INR'"),
    ("coupon_enabled", "ALTER TABLE speaking_topics ADD COLUMN coupon_enabled BOOLEAN DEFAULT 0"),
    ("coupon_code", "ALTER TABLE speaking_topics ADD COLUMN coupon_code TEXT"),
    ("coupon_discount_type", "ALTER TABLE speaking_topics ADD COLUMN coupon_discount_type TEXT"),
    ("coupon_discount_value", "ALTER TABLE speaking_topics ADD COLUMN coupon_discount_value REAL"),
    ("coupon_valid_from", "ALTER TABLE speaking_topics ADD COLUMN coupon_valid_from TEXT"),
    ("coupon_valid_until", "ALTER TABLE speaking_topics ADD COLUMN coupon_valid_until TEXT"),
]

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(speaking_topics)")
existing_columns = {row[1] for row in cur.fetchall()}

for column_name, sql in columns_to_add:
    if column_name not in existing_columns:
        print(f"Adding column: {column_name}")
        cur.execute(sql)
    else:
        print(f"Already exists: {column_name}")

conn.commit()

cur.execute("PRAGMA table_info(speaking_topics)")
print("\nFinal speaking_topics columns:")
for row in cur.fetchall():
    print(f"- {row[1]} ({row[2]})")

conn.close()
print("\nDone.")