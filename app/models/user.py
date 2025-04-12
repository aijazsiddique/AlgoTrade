from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager, bcrypt

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    openalgo_api_key = db.Column(db.String(100), nullable=True)
    openalgo_host_url = db.Column(db.String(255), nullable=True, default="http://127.0.0.1:5000")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    strategies = db.relationship('Strategy', backref='author', lazy=True)
    
    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
