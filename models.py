from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student') # 'student' or 'mentor'
    credit_points = db.Column(db.Integer, default=0)
    skills = db.Column(db.String(500), nullable=True)  # Comma-separated skills for mentors
    bio = db.Column(db.Text, nullable=True)  # Mentor bio/description
    education = db.Column(db.String(100), nullable=True) # Undergraduate, Graduate, etc.
    is_verified = db.Column(db.Boolean, default=False)

    @property
    def average_rating(self):
        ratings = MentorRating.query.filter_by(mentor_id=self.id).all()
        if not ratings:
            return 0
        return round(sum(r.rating for r in ratings) / len(ratings), 1)

class CareerMoment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    background = db.Column(db.Text, nullable=True)
    urgency = db.Column(db.String(20), default='Normal') # 'Normal' or 'Urgent'
    status = db.Column(db.String(20), default='Open') # 'Open', 'Resolved'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='moments')
    replies = db.relationship('ExperienceReply', backref='moment', lazy=True, cascade='all, delete-orphan')

class ExperienceReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moment_id = db.Column(db.Integer, db.ForeignKey('career_moment.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    decision_made = db.Column(db.Text, nullable=False) # "What decision I made"
    content = db.Column(db.Text, nullable=False) # "The Story/Outcome"
    mistake_warning = db.Column(db.Text, nullable=True) # "One mistake/warning"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    mentor = db.relationship('User', backref='replies')
    ratings = db.relationship('MentorRating', backref='reply', lazy=True, cascade='all, delete-orphan')

class MentorRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reply_id = db.Column(db.Integer, db.ForeignKey('experience_reply.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with explicit foreign_keys to avoid ambiguity
    student = db.relationship('User', foreign_keys=[student_id], backref='student_chats')
    mentor = db.relationship('User', foreign_keys=[mentor_id], backref='mentor_chats')
    messages = db.relationship('Message', backref='chat', lazy=True, cascade='all, delete-orphan')
    
    # Ensure unique chat per student-mentor pair
    __table_args__ = (db.UniqueConstraint('student_id', 'mentor_id', name='unique_student_mentor_chat'),)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', backref='sent_messages')

# Add helper method to Chat after Message is defined
def get_chat_unread_count(chat, user_id):
    return Message.query.filter_by(chat_id=chat.id, is_read=False).filter(Message.sender_id != user_id).count()

Chat.get_unread_count = get_chat_unread_count
