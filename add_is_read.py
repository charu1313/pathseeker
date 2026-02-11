from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            # Check if column already exists
            db.session.execute(text("SELECT is_read FROM message LIMIT 1"))
            print("Column 'is_read' already exists.")
        except Exception:
            print("Adding 'is_read' column to 'message' table...")
            # SQLite doesn't support sophisticated migrations easily, but simple ADD COLUMN works
            db.session.execute(text("ALTER TABLE message ADD COLUMN is_read BOOLEAN DEFAULT 0"))
            db.session.commit()
            print("Column added successfully.")

if __name__ == "__main__":
    migrate()
