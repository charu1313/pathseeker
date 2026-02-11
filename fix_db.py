import sqlite3
import os

db_path = 'instance/pathseeker.db'

def fix_database():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking 'user' table columns...")
    cursor.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'skills' not in columns:
        print("Adding 'skills' column to 'user' table...")
        cursor.execute("ALTER TABLE user ADD COLUMN skills TEXT")
    else:
        print("'skills' column already exists.")

    if 'bio' not in columns:
        print("Adding 'bio' column to 'user' table...")
        cursor.execute("ALTER TABLE user ADD COLUMN bio TEXT")
    else:
        print("'bio' column already exists.")

    print("Checking for 'chat' and 'message' tables...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat'")
    if not cursor.fetchone():
        print("Creating 'chat' table...")
        cursor.execute("""
            CREATE TABLE chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                mentor_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES user(id),
                FOREIGN KEY(mentor_id) REFERENCES user(id),
                UNIQUE(student_id, mentor_id)
            )
        """)
    else:
        print("'chat' table already exists.")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message'")
    if not cursor.fetchone():
        print("Creating 'message' table...")
        cursor.execute("""
            CREATE TABLE message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_id) REFERENCES chat(id),
                FOREIGN KEY(sender_id) REFERENCES user(id)
            )
        """)
    else:
        print("'message' table already exists.")

    conn.commit()
    conn.close()
    print("Database fix complete!")

if __name__ == "__main__":
    fix_database()
