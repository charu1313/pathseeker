from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, CareerMoment, ExperienceReply, MentorRating, Chat, Message
import os
import sys
from difflib import SequenceMatcher
import jwt
import datetime
import google.generativeai as genai

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pathseeker-secret-key'
# Use absolute path for database to avoid ambiguity
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'pathseeker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Token Logic
def generate_confirmation_token(email):
    payload = {
        'sub': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def confirm_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return 'Signature expired. Please register again.'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please register again.'

# Configure Gemini AI
def load_gemini_key():
    # 1. Check environment variable
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    
    # 2. Check local file (api_key.txt)
    try:
        key_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "api_key.txt")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                content = f.read().strip()
                if content and "PASTE_YOUR" not in content:
                    return content
    except Exception as e:
        print(f"Error reading api_key.txt: {e}")
    
    return None

api_key = load_gemini_key()
if api_key:
    genai.configure(api_key=api_key)

# System Instruction for Education-Only Bot
SYSTEM_INSTRUCTION = """
You are a helpful and knowledgeable Career & Education Assistant on the Pathseeker platform. 
Your goal is to help students with questions specifically related to:
1. Higher education and college searches.
2. Career paths and professional development.
3. Skill-building and learning resources.
4. Resume tips and interview preparation.

LIMITATION: You MUST NOT answer questions unrelated to education, careers, or professional growth. 
If a user asks about anything else (e.g., cooking, sports, general entertainment, or casual conversation outside of career/education), 
politely decline and remind them that you are here specifically to assist with their career and education journey.

Be encouraging, professional, and concise.
"""

def get_ai_response(user_input):
    api_key = load_gemini_key()
    if not api_key:
        return "CONFIG_ERROR: It looks like your Gemini API key is missing or not set yet. Please add it to `api_key.txt` in the project folder to start chatting!"
        
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        chat = model.start_chat(history=[])
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nUser Question: {user_input}"
        response = chat.send_message(full_prompt)
        return response.text
    except Exception as e:
        error_msg = str(e)
        print(f"AI Error: {error_msg}")
        if "API_KEY_INVALID" in error_msg or "403" in error_msg:
            return "CONFIG_ERROR: Your API key appears to be invalid. Please check your key in `api_key.txt`."
        return "I'm sorry, I'm having trouble connecting to my brain right now. Please try again later!"

# AI/Helper Logic
def find_similar_moments(current_moment_title, limit=3):
    """Simple offline text similarity to find related past moments."""
    all_moments = CareerMoment.query.filter(CareerMoment.status != 'Open').all() # Prefer resolved ones
    if not all_moments:
        all_moments = CareerMoment.query.all()
        
    scored_moments = []
    for m in all_moments:
        if m.title == current_moment_title: continue # Skip self
        score = SequenceMatcher(None, current_moment_title.lower(), m.title.lower()).ratio()
        if score > 0.3: # Threshold
            scored_moments.append((score, m))
            
    scored_moments.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in scored_moments[:limit]]

@app.route('/')
def index():
    # Show all OPEN moments globally
    query = CareerMoment.query.filter(CareerMoment.status != 'Resolved')
    
    # If the user is a mentor, hide moments they've already replied to
    if current_user.is_authenticated and current_user.role == 'mentor':
        replied_ids = [r.moment_id for r in ExperienceReply.query.filter_by(mentor_id=current_user.id).all()]
        if replied_ids:
            query = query.filter(CareerMoment.id.notin_(replied_ids))
            
    moments = query.order_by(
        CareerMoment.urgency.desc(), 
        CareerMoment.created_at.desc()
    ).all()
    
    return render_template('feed.html', moments=moments)

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_moment():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        background = request.form.get('background')
        urgency = request.form.get('urgency')
        
        moment = CareerMoment(
            author_id=current_user.id,
            title=title,
            description=description,
            background=background,
            urgency=urgency
        )
        db.session.add(moment)
        db.session.commit()
        
        # Check for similar moments immediately
        similar = find_similar_moments(title)
        if similar:
            flash(f'We found {len(similar)} similar past moments that might help while you wait!', 'info')
            
        return redirect(url_for('view_moment', moment_id=moment.id))
    return render_template('create_moment.html')

@app.route('/post/<int:moment_id>')
@login_required
def view_moment(moment_id):
    moment = CareerMoment.query.get_or_404(moment_id)
    
    # Permission Check: 
    # Mentors can view everything. 
    # Students can only view their own moments.
    if current_user.role != 'mentor' and moment.author_id != current_user.id:
        flash('You do not have permission to view this moment.', 'danger')
        return redirect(url_for('index'))
    
    
    # Identify which replies the current user (if author) has already rated
    rated_reply_ids = []
    if current_user.is_authenticated and moment.author_id == current_user.id:
        # Filter ratings for this moment's replies to be more efficient if needed, 
        # but simple query is fine for MVP
        ratings = MentorRating.query.filter_by(student_id=current_user.id).all()
        rated_reply_ids = [r.reply_id for r in ratings]

    similar_moments = find_similar_moments(moment.title)
    return render_template('post_detail.html', moment=moment, similar_moments=similar_moments, rated_reply_ids=rated_reply_ids)

@app.route('/reply/<int:moment_id>', methods=['POST'])
@login_required
def reply_moment(moment_id):
    content = request.form.get('content')
    decision = request.form.get('decision')
    mistake = request.form.get('mistake')
    
    reply = ExperienceReply(
        moment_id=moment_id,
        mentor_id=current_user.id,
        decision_made=decision,
        content=content,
        mistake_warning=mistake
    )
    db.session.add(reply)
    db.session.commit()
    flash('Thank you for sharing your lived experience.')
    return redirect(url_for('view_moment', moment_id=moment_id))

@app.route('/resolve/<int:moment_id>')
@login_required
def resolve_moment(moment_id):
    moment = CareerMoment.query.get_or_404(moment_id)
    if moment.author_id == current_user.id:
        moment.status = 'Resolved'
        db.session.commit()
        flash('Moment marked as resolved. Hope you found clarity!')
    return redirect(url_for('view_moment', moment_id=moment_id))

@app.route('/rate_mentor/<int:reply_id>', methods=['POST'])
@login_required
def rate_mentor(reply_id):
    reply = ExperienceReply.query.get_or_404(reply_id)
    moment = CareerMoment.query.get(reply.moment_id)

    # Security: Only the author of the moment can rate the reply
    if not moment or moment.author_id != current_user.id:
        flash('You are not authorized to rate this reply.', 'danger')
        return redirect(url_for('view_moment', moment_id=moment.id if moment else 0))

    # Check if already rated
    existing_rating = MentorRating.query.filter_by(
        student_id=current_user.id, 
        reply_id=reply_id
    ).first()

    if existing_rating:
        flash('You have already rated this mentor.', 'warning')
        return redirect(url_for('view_moment', moment_id=moment.id))

    rating_value = request.form.get('rating')
    try:
        rating_value = int(rating_value)
    except (ValueError, TypeError):
        flash('Invalid rating.', 'danger')
        return redirect(url_for('view_moment', moment_id=moment.id))
    
    if rating_value < 1 or rating_value > 5:
        flash('Invalid rating.', 'danger')
        return redirect(url_for('view_moment', moment_id=moment.id))

    # Create Rating
    rating = MentorRating(
        student_id=current_user.id,
        mentor_id=reply.mentor_id,
        reply_id=reply_id,
        rating=rating_value
    )
    db.session.add(rating)

    # Update Mentor's Credit Points
    mentor = User.query.get(reply.mentor_id)
    mentor.credit_points += rating_value
    db.session.commit()

    flash('Thank you for rating the mentor!', 'success')
    return redirect(url_for('view_moment', moment_id=moment.id))

# Auth Routes (Reused/Adapted)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student') 
        education = request.form.get('education', 'Undergraduate') # Default to Undergraduate
        skills = request.form.get('skills', '').strip() if role == 'mentor' else None
        bio = request.form.get('bio', '').strip() if role == 'mentor' else None
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # AUTO-VERIFY FOR ROBUST MVP
        user = User(
            name=name, 
            email=email, 
            password=generate_password_hash(password, method='pbkdf2:sha256'), 
            role=role, 
            education=education,
            skills=skills,
            bio=bio,
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Welcome to Pathseeker! You are now logged in.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

# Legacy verification routes removed for clarity/stability

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
    return render_template('login.html')

# ROLE-BASED DASHBOARD ROUTING
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'mentor':
        return redirect(url_for('mentor_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    # Show authored moments
    authored = CareerMoment.query.filter_by(author_id=current_user.id).all()
    
    # Show moments where I (student) replied (uncommon but possible if students reply to each other)
    replied_ids = [r.moment_id for r in ExperienceReply.query.filter_by(mentor_id=current_user.id).all()]
    interacted = CareerMoment.query.filter(CareerMoment.id.in_(replied_ids)).all() if replied_ids else []
    
    # Merge and deduplicate
    moment_ids = set([m.id for m in authored] + [m.id for m in interacted])
    my_moments = CareerMoment.query.filter(CareerMoment.id.in_(moment_ids)).order_by(CareerMoment.created_at.desc()).all() if moment_ids else []
    
    return render_template('student_dashboard.html', my_moments=my_moments)

@app.route('/mentor/dashboard')
@login_required
def mentor_dashboard():
    # Show ONLY moments this mentor has already replied to
    replied_ids = [r.moment_id for r in ExperienceReply.query.filter_by(mentor_id=current_user.id).all()]
    past_contributions = CareerMoment.query.filter(CareerMoment.id.in_(replied_ids)).order_by(CareerMoment.created_at.desc()).all() if replied_ids else []
    
    return render_template('mentor_dashboard.html', past_contributions=past_contributions)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# SEARCH & MENTOR DISCOVERY
@app.route('/search')
@login_required
def search():
    name_query = request.args.get('name_q', '')
    domain_query = request.args.get('domain_q', '').lower()
    
    mentors = []
    has_searched = bool(name_query or domain_query)
    
    if has_searched:
        # Start with all mentors
        all_mentors = User.query.filter_by(role='mentor').all()
        
        for mentor in all_mentors:
            match = True
            
            # Name Search: CASE SENSITIVE
            if name_query and name_query not in mentor.name:
                match = False
                
            # Domain Search: CASE INSENSITIVE
            if match and domain_query:
                if not mentor.skills or domain_query not in mentor.skills.lower():
                    match = False
            
            if match:
                mentors.append(mentor)
    
    return render_template('search.html', mentors=mentors, name_query=name_query, domain_query=domain_query, has_searched=has_searched)

@app.route('/mentor/<int:mentor_id>')
@login_required
def mentor_profile(mentor_id):
    mentor = User.query.get_or_404(mentor_id)
    if mentor.role != 'mentor':
        flash('This user is not a mentor.', 'danger')
        return redirect(url_for('search'))
    return render_template('mentor_profile.html', mentor=mentor)

# CHAT SYSTEM
@app.route('/chat/start/<int:mentor_id>', methods=['POST'])
@login_required
def start_chat(mentor_id):
    if current_user.role != 'student':
        flash('Only students can start chats with mentors.', 'danger')
        return redirect(url_for('index'))
    
    mentor = User.query.get_or_404(mentor_id)
    if mentor.role != 'mentor':
        flash('You can only chat with mentors.', 'danger')
        return redirect(url_for('search'))
    
    # Check if chat already exists
    existing_chat = Chat.query.filter_by(student_id=current_user.id, mentor_id=mentor_id).first()
    if existing_chat:
        return redirect(url_for('view_chat', chat_id=existing_chat.id))
    
    # Create new chat
    new_chat = Chat(student_id=current_user.id, mentor_id=mentor_id)
    db.session.add(new_chat)
    db.session.commit()
    
    flash(f'Chat started with {mentor.name}!', 'success')
    return redirect(url_for('view_chat', chat_id=new_chat.id))

@app.route('/chat/<int:chat_id>')
@login_required
def view_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Security: Only participants can view
    if current_user.id != chat.student_id and current_user.id != chat.mentor_id:
        flash('You do not have permission to view this chat.', 'danger')
        return redirect(url_for('index'))
    
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.created_at.asc()).all()
    
    # Determine the other participant
    other_user = chat.mentor if current_user.id == chat.student_id else chat.student

    # Mark messages from other user as read
    unread_messages = Message.query.filter_by(chat_id=chat_id, sender_id=other_user.id, is_read=False).all()
    if unread_messages:
        for msg in unread_messages:
            msg.is_read = True
        db.session.commit()
    
    return render_template('chat.html', chat=chat, messages=messages, other_user=other_user)

@app.route('/chat/<int:chat_id>/send', methods=['POST'])
@login_required
def send_message(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Security: Only participants can send
    if current_user.id != chat.student_id and current_user.id != chat.mentor_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    content = request.form.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    message = Message(chat_id=chat_id, sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'sender_name': current_user.name,
            'content': message.content,
            'created_at': message.created_at.strftime('%I:%M %p')
        }
    })

@app.route('/chat/<int:chat_id>/messages')
@login_required
def get_messages(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    
    # Security: Only participants can view
    if current_user.id != chat.student_id and current_user.id != chat.mentor_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.created_at.asc()).all()
    
    # Mark messages from other user as read
    other_id = chat.mentor_id if current_user.id == chat.student_id else chat.student_id
    unread = Message.query.filter_by(chat_id=chat_id, sender_id=other_id, is_read=False).all()
    if unread:
        for msg in unread:
            msg.is_read = True
        db.session.commit()
    
    return jsonify({
        'messages': [{
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.name,
            'content': msg.content,
            'created_at': msg.created_at.strftime('%I:%M %p'),
            'is_mine': msg.sender_id == current_user.id
        } for msg in messages]
    })

@app.route('/my-chats')
@login_required
def my_chats():
    if current_user.role == 'student':
        chats = Chat.query.filter_by(student_id=current_user.id).all()
    else:
        chats = Chat.query.filter_by(mentor_id=current_user.id).all()
    
    return render_template('my_chats.html', chats=chats)

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        new_email = request.form.get('email')
        
        # Check if email is being changed and if it's unique
        if new_email and new_email != current_user.email:
            if User.query.filter_by(email=new_email).first():
                flash('This email is already registered with another account.', 'danger')
                return render_template('edit_profile.html')
            current_user.email = new_email

        current_user.name = request.form.get('name')
        current_user.education = request.form.get('education')
        
        if current_user.role == 'mentor':
            current_user.skills = request.form.get('skills')
            current_user.bio = request.form.get('bio')
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('edit_profile.html')
    
@app.route('/notifications/check')
@login_required
def check_notifications():
    # Only notify for messages NOT sent by current user and NOT read
    # We join with Chat to ensure user is a participant
    unread_messages = Message.query.join(Chat, Message.chat_id == Chat.id).filter(
        (Chat.student_id == current_user.id) | (Chat.mentor_id == current_user.id),
        Message.sender_id != current_user.id,
        Message.is_read == False
    ).order_by(Message.created_at.desc()).all()
    
    return jsonify({
        'unread_count': len(unread_messages),
        'notifications': [{
            'id': msg.id,
            'sender_name': msg.sender.name,
            'content': msg.content[:50] + ('...' if len(msg.content) > 50 else ''),
            'chat_id': msg.chat_id,
            'created_at': msg.created_at.strftime('%I:%M %p')
        } for msg in unread_messages[:5]] # Only return last 5 for popup
    })

@app.route('/chat/<int:chat_id>/delete', methods=['POST'])
@login_required
def delete_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    # Ensure current user is part of the chat
    if current_user.id not in [chat.student_id, chat.mentor_id]:
        flash('You do not have permission to delete this chat.', 'danger')
        return redirect(url_for('my_chats'))
    
    db.session.delete(chat)
    db.session.commit()
    flash('Chat deleted successfully.', 'success')
    return redirect(url_for('my_chats'))

@app.route('/moment/<int:moment_id>/delete', methods=['POST'])
@login_required
def delete_moment(moment_id):
    moment = CareerMoment.query.get_or_404(moment_id)
    # Ensure current user is the author
    if moment.author_id != current_user.id:
        flash('You do not have permission to delete this moment.', 'danger')
        return redirect(url_for('dashboard'))
    
    db.session.delete(moment)
    db.session.commit()
    flash('Career moment deleted successfully.', 'success')
    return redirect(url_for('dashboard'))


with app.app_context():
    db.create_all()


# AI Chat Endpoint
@app.route('/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    data = request.get_json()
    user_message = data.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    ai_response = get_ai_response(user_message)
    return jsonify({'response': ai_response})

@app.route('/chat/<int:chat_id>/video_room')
@login_required
def get_video_room(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if current_user.id not in [chat.student_id, chat.mentor_id]:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Generate a unique room name based on chat ID and a static prefix
    # In a real app, you'd use a more complex hash
    room_name = f"Pathseeker_Room_{chat_id}_" + datetime.datetime.now().strftime("%Y%m%d")
    return jsonify({'room_name': room_name})

if __name__ == '__main__':
    # Using host 0.0.0.0 to allow access from other devices on the same network
    app.run(host='0.0.0.0', port=5050, debug=True)
