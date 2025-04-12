import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///algotrade.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Import and register blueprints
from app.controllers.auth import auth_bp
from app.controllers.dashboard import dashboard_bp
from app.controllers.strategy import strategy_bp
from app.controllers.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(strategy_bp)
app.register_blueprint(admin_bp)

# Import models to ensure they're registered with SQLAlchemy
from app.models import user, strategy, instance
