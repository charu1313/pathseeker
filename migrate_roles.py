import sqlite3
import os

db_path = 'instance/pathseeker.db'

def migrate_roles():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Migrating 'mentee' roles to 'student'...")
    cursor.execute("UPDATE user SET role = 'student' WHERE role = 'mentee'")
    conn.commit()
    print(f"{cursor.rowcount} roles updated.")

    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_roles()
