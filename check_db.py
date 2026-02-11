from app import app
from models import CareerMoment, User

with app.app_context():
    print("--- User Roles ---")
    for u in User.query.all():
        print(f"ID: {u.id}, Name: {u.name}, Role: {u.role}")
        
    print("\n--- Career Moments ---")
    for m in CareerMoment.query.all():
        print(f"ID: {m.id}, Title: {m.title}, Status: '{m.status}', Author ID: {m.author_id}, Author Role: {m.author.role}")
