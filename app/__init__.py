import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from pathlib import Path

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    
    # Ensure instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Configure app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_development_only')
    
    # Configure database with absolute path
    db_path = os.path.join(app.instance_path, 'algotrade.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    
    # Configure login
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Import models to ensure they are known to Flask-Migrate
    from app.models import User, Strategy, StrategyInstance, SymbolMapping
    
    # Register blueprints
    from app.controllers.auth import auth_bp
    from app.controllers.dashboard import dashboard_bp
    from app.controllers.strategy import strategy_bp
    from app.controllers.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(strategy_bp)
    app.register_blueprint(admin_bp)
    
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created or verified.")
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
    
    # Start background tasks
    with app.app_context():
        from app.helpers.logger_helper import logger
        from app.helpers.background_tasks import task_manager
        
        # Log application startup
        logger.log_app_event("STARTUP", "Application initialized")
        
        # Start background tasks with app reference
        task_manager.start_all_tasks(app=app)
    
    return app
