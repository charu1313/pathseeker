from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            # Check if column already exists
            db.session.execute(text("SELECT education FROM user LIMIT 1"))
            print("Column 'education' already exists.")
        except Exception:
            print("Adding 'education' column to 'user' table...")
            db.session.execute(text("ALTER TABLE user ADD COLUMN education VARCHAR(100)"))
            db.session.commit()
            print("Column added successfully.")

if __name__ == "__main__":
    migrate()
