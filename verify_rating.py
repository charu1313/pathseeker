import unittest
from app import app, db, User, CareerMoment, ExperienceReply, MentorRating

class MentorRatingtest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_pathseeker.db'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, email, password):
        return self.app.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def register(self, name, email, password, role='student'):
        return self.app.post('/register', data=dict(
            name=name,
            email=email,
            password=password,
            role=role
        ), follow_redirects=True)

    def test_rating_flow(self):
        # 1. Register Users
        self.register('Student One', 'student@example.com', 'password', 'student')
        self.app.get('/logout')
        self.register('Mentor One', 'mentor@example.com', 'password', 'mentor')
        self.app.get('/logout')

        # 2. Student posts moment
        self.login('student@example.com', 'password')
        with app.app_context():
            student = User.query.filter_by(email='student@example.com').first()
            self.assertIsNotNone(student)
        
        self.app.post('/post/new', data=dict(
            title='Help me',
            description='I need advice',
            urgency='Normal'
        ), follow_redirects=True)
        
        with app.app_context():
            moment = CareerMoment.query.filter_by(title='Help me').first()
            self.assertIsNotNone(moment)
            moment_id = moment.id

        self.app.get('/logout')

        # 3. Mentor replies
        self.login('mentor@example.com', 'password')
        self.app.post(f'/reply/{moment_id}', data=dict(
            content='My advice',
            decision='Do this',
            mistake='None'
        ), follow_redirects=True)
        
        with app.app_context():
            reply = ExperienceReply.query.filter_by(moment_id=moment_id).first()
            self.assertIsNotNone(reply)
            reply_id = reply.id

        self.app.get('/logout')

        # 4. Student rates reply
        self.login('student@example.com', 'password')
        response = self.app.post(f'/rate_mentor/{reply_id}', data=dict(
            rating='5'
        ), follow_redirects=True)
        
        self.assertIn(b'Thank you for rating the mentor!', response.data)

        # 5. Check Mentor Points
        with app.app_context():
            mentor = User.query.filter_by(email='mentor@example.com').first()
            self.assertEqual(mentor.credit_points, 5)
            
            # Check Rating Record
            rating = MentorRating.query.filter_by(reply_id=reply_id).first()
            self.assertIsNotNone(rating)
            self.assertEqual(rating.rating, 5)

        # 6. Try to rate again (should fail)
        response = self.app.post(f'/rate_mentor/{reply_id}', data=dict(
            rating='1'
        ), follow_redirects=True)
        self.assertIn(b'You have already rated this mentor.', response.data)

        # 7. Check points didn't change
        with app.app_context():
            mentor = User.query.filter_by(email='mentor@example.com').first()
            self.assertEqual(mentor.credit_points, 5)

if __name__ == '__main__':
    unittest.main()
