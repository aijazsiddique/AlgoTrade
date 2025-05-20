import pytest
from flask import url_for, session
from flask_login import current_user, FlaskLoginClient
from app import create_app, db
from app.models.user import User

@pytest.fixture
def app_instance():
    # Create a Flask app instance for testing
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler form posts in tests
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use in-memory DB for tests
        "SERVER_NAME": "localhost.localdomain", # Required for url_for outside of request context
        "SECRET_KEY": "test-secret-key" # Explicitly set a secret key for testing sessions
    })
    # Set the test client class that understands Flask-Login
    app.test_client_class = FlaskLoginClient 
    return app

@pytest.fixture
def client(app_instance):
    with app_instance.app_context():
        db.create_all() # Create database tables
        # Create a test user
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # The test client will be configured to use this user
        # when app_instance.test_client(user=user) is called
        # The user=user parameter in test_client() automatically logs in the user.
        yield app_instance.test_client(user=user) 
        
        db.session.remove()
        db.drop_all()


def test_profile_update_no_logout(client):
    # client is already logged in as 'testuser' due to app.test_client(user=user) in the fixture
    
    # Initial profile URL
    with client.application.app_context(): 
        profile_url = url_for('auth.profile')
    
    # Verify logged in state initially by accessing profile page
    response = client.get(profile_url)
    assert response.status_code == 200
    assert b'Profile' in response.data # Check for some content from the profile page
    assert b'testuser' in response.data # Check if current username is shown

    # Data for profile update
    new_username = "updateduser"
    new_api_key = "new_openalgo_key_123"
    original_email = 'test@example.com' # Assuming this is the user's email
    
    update_data = {
        'username': new_username,
        'email': original_email, 
        'openalgo_api_key': new_api_key,
        'openalgo_host_url': 'http://newhost.com',
        'password': '', # Assuming password change is optional
        'confirm_password': ''
    }
    
    # Make the POST request to update profile
    with client.application.app_context():
        response = client.post(profile_url, data=update_data, follow_redirects=True)
    
    assert response.status_code == 200 
    assert b'Your profile has been updated!' in response.data 
    assert bytes(new_username, 'utf-8') in response.data # Check for new username on page

    # Verify still logged in by accessing an authenticated route again
    response = client.get(profile_url) # Get profile page again
    assert response.status_code == 200
    assert b'Profile' in response.data 
    assert bytes(new_username, 'utf-8') in response.data # Ensure new username is still there

    # Verify data in database
    # Need an app_context to query the database
    with client.application.app_context():
        user_in_db = User.query.filter_by(email=original_email).first()
        assert user_in_db is not None
        assert user_in_db.username == new_username
        assert user_in_db.openalgo_api_key == new_api_key
        assert user_in_db.openalgo_host_url == 'http://newhost.com'

```
