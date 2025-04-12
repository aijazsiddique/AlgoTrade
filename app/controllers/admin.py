from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance
from functools import wraps
import json
from SmartApi import SmartConnect
import pyotp
from app.helpers.websocket_helper import websocket_manager
import threading
import time
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

# Global variables for token refresh
token_refresh_thread = None
token_refresh_running = False

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def refresh_angelone_tokens():
    """Background thread to refresh AngelOne tokens periodically"""
    global token_refresh_running
    
    while token_refresh_running:
        try:
            # Get admin user with AngelOne enabled
            admin = User.query.filter_by(
                is_admin=True, 
                angelone_ws_enabled=True
            ).first()
            
            if admin and admin.angelone_refresh_token:
                # Calculate token age
                if not admin.angelone_token_updated_at:
                    # If no update time recorded, assume token is old
                    needs_refresh = True
                else:
                    # Check if token is older than 6 hours
                    token_age = datetime.utcnow() - admin.angelone_token_updated_at
                    needs_refresh = token_age > timedelta(hours=6)
                
                if needs_refresh:
                    print("Refreshing AngelOne tokens...")
                    
                    # Create SmartConnect instance
                    smart_api = SmartConnect(api_key=admin.angelone_api_key)
                    
                    # Refresh token
                    refresh_response = smart_api.generateSessionFromRefreshToken(admin.angelone_refresh_token)
                    
                    if refresh_response['status']:
                        # Update the tokens
                        admin.angelone_jwt_token = refresh_response['data']['jwtToken']
                        admin.angelone_refresh_token = refresh_response['data']['refreshToken']
                        admin.angelone_feed_token = smart_api.getfeedToken()
                        admin.angelone_token_updated_at = datetime.utcnow()
                        db.session.commit()
                        
                        # Reconfigure WebSocket with new tokens
                        if websocket_manager.connected:
                            print("Reconnecting WebSocket with new tokens...")
                            websocket_manager.configure(
                                admin.angelone_jwt_token,
                                admin.angelone_api_key,
                                admin.angelone_client_code,
                                admin.angelone_feed_token
                            )
                            websocket_manager.reconnect()
                        
                        print("AngelOne tokens refreshed successfully")
                    else:
                        print(f"Failed to refresh tokens: {refresh_response.get('message', 'Unknown error')}")
        
        except Exception as e:
            print(f"Error refreshing tokens: {str(e)}")
        
        # Sleep for 1 hour before next check
        time.sleep(3600)

def start_token_refresh_thread():
    """Start the token refresh background thread"""
    global token_refresh_thread, token_refresh_running
    
    if token_refresh_thread is None or not token_refresh_thread.is_alive():
        token_refresh_running = True
        token_refresh_thread = threading.Thread(
            target=refresh_angelone_tokens, 
            name="TokenRefresh",
            daemon=True
        )
        token_refresh_thread.start()
        print("Token refresh thread started")
        return True
    return False

def stop_token_refresh_thread():
    """Stop the token refresh background thread"""
    global token_refresh_running
    token_refresh_running = False
    print("Token refresh thread stopping")
    return True

@admin_bp.route('/admin')
@login_required
@admin_required
def index():
    # Get counts for admin dashboard
    users_count = User.query.count()
    strategies_count = Strategy.query.count()
    active_instances_count = StrategyInstance.query.filter_by(is_active=True).count()
    
    return render_template(
        'admin/index.html',
        title='Admin Dashboard',
        users_count=users_count,
        strategies_count=strategies_count,
        active_instances_count=active_instances_count,
        websocket_status=websocket_manager.connected
    )

@admin_bp.route('/admin/users')
@login_required
@admin_required
def users():
    # Get all users
    all_users = User.query.all()
    
    return render_template(
        'admin/users.html',
        title='User Management',
        users=all_users
    )

@admin_bp.route('/admin/users/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    # Don't allow toggling own admin status
    if user_id == current_user.id:
        flash("You cannot change your own admin status.", "danger")
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "granted" if user.is_admin else "revoked"
    flash(f"Admin privileges {status} for {user.username}.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route('/admin/strategies')
@login_required
@admin_required
def strategies():
    # Get all strategies
    all_strategies = Strategy.query.all()
    
    return render_template(
        'admin/strategies.html',
        title='Strategy Management',
        strategies=all_strategies
    )

@admin_bp.route('/admin/instances')
@login_required
@admin_required
def instances():
    # Get all strategy instances
    all_instances = StrategyInstance.query.all()
    
    return render_template(
        'admin/instances.html',
        title='Instance Management',
        instances=all_instances
    )

@admin_bp.route('/admin/websocket')
@login_required
@admin_required
def websocket_settings():
    """AngelOne WebSocket management interface"""
    
    # Get admin with AngelOne API configured
    admins_with_angel = User.query.filter(
        User.is_admin == True,
        User.angelone_api_key.isnot(None),
        User.angelone_client_code.isnot(None)
    ).all()
    
    # Get current AngelOne settings
    current_admin = User.query.filter_by(
        is_admin=True, 
        angelone_ws_enabled=True
    ).first()
    
    # Get connection status
    ws_status = websocket_manager.get_connection_status() if websocket_manager.connected else None
    
    # Get subscribed symbols
    subscribed_symbols = []
    if websocket_manager.connected:
        with websocket_manager.data_lock:
            for symbol, info in websocket_manager.subscribed_symbols.items():
                subscribed_symbols.append({
                    'symbol': symbol,
                    'exchange_type': info['exchange_type'],
                    'token': info['token'],
                    'data_points': len(info['data']),
                    'callbacks': len(info['callbacks'])
                })
    
    return render_template(
        'admin/websocket.html',
        title='WebSocket Management',
        websocket_connected=websocket_manager.connected,
        admins_with_angel=admins_with_angel,
        subscribed_symbols=subscribed_symbols,
        current_admin=current_admin,
        ws_status=ws_status,
        now=datetime.utcnow  # Add the now function to the template context
    )

@admin_bp.route('/admin/websocket/connect', methods=['POST'])
@login_required
@admin_required
def websocket_connect():
    """Connect to AngelOne WebSocket"""
    admin_id = request.form.get('admin_id')
    
    if not admin_id:
        flash("Please select an admin user with AngelOne API credentials", "danger")
        return redirect(url_for('admin.websocket_settings'))
    
    admin = User.query.get_or_404(admin_id)
    
    # Check if credentials are configured
    if not all([admin.angelone_api_key, admin.angelone_client_code, 
                admin.angelone_password, admin.angelone_totp_token]):
        flash("AngelOne API credentials are incomplete", "danger")
        return redirect(url_for('admin.websocket_settings'))
    
    try:
        # Create SmartConnect instance
        smart_api = SmartConnect(api_key=admin.angelone_api_key)
        
        # Generate TOTP
        totp = pyotp.TOTP(admin.angelone_totp_token).now()
        
        # Login to AngelOne
        login_response = smart_api.generateSession(
            admin.angelone_client_code,
            admin.angelone_password, 
            totp
        )
        
        if login_response['status']:
            # Store the tokens in the admin's record
            admin.angelone_jwt_token = login_response['data']['jwtToken']
            admin.angelone_refresh_token = login_response['data']['refreshToken']
            admin.angelone_feed_token = smart_api.getfeedToken()
            admin.angelone_ws_configured = True
            admin.angelone_ws_enabled = True
            admin.angelone_token_updated_at = datetime.utcnow()
            
            # Reset other admin users' enabled status
            User.query.filter(User.id != admin.id).update({'angelone_ws_enabled': False})
            
            db.session.commit()
            
            # Configure and connect WebSocket
            websocket_manager.configure(
                admin.angelone_jwt_token,
                admin.angelone_api_key,
                admin.angelone_client_code,
                admin.angelone_feed_token
            )
            
            # Start token refresh thread
            start_token_refresh_thread()
            
            if websocket_manager.connect():
                flash("Successfully connected to AngelOne WebSocket", "success")
            else:
                flash(f"Failed to connect to AngelOne WebSocket: {websocket_manager.last_error}", "danger")
        else:
            flash(f"Failed to login to AngelOne: {login_response.get('message', 'Unknown error')}", "danger")
    
    except Exception as e:
        flash(f"Error connecting to AngelOne WebSocket: {str(e)}", "danger")
    
    return redirect(url_for('admin.websocket_settings'))

@admin_bp.route('/admin/websocket/disconnect', methods=['POST'])
@login_required
@admin_required
def websocket_disconnect():
    """Disconnect from AngelOne WebSocket"""
    
    try:
        # Stop token refresh thread
        stop_token_refresh_thread()
        
        # Close WebSocket connection
        if websocket_manager.close_connection():
            flash("Successfully disconnected from AngelOne WebSocket", "success")
        else:
            flash(f"Error disconnecting WebSocket: {websocket_manager.last_error}", "warning")
            
        # Update admin user status
        admin = User.query.filter_by(angelone_ws_enabled=True).first()
        if admin:
            admin.angelone_ws_enabled = False
            db.session.commit()
    
    except Exception as e:
        flash(f"Error disconnecting from AngelOne WebSocket: {str(e)}", "danger")
    
    return redirect(url_for('admin.websocket_settings'))

@admin_bp.route('/admin/websocket/status', methods=['GET'])
@login_required
@admin_required
def websocket_status():
    """Get WebSocket status for AJAX updates"""
    
    status = websocket_manager.get_connection_status()
    
    if status['last_data_time']:
        status['last_data_time'] = status['last_data_time'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify({
        'connected': status['connected'],
        'reconnect_attempts': status['reconnect_attempts'],
        'last_error': status['last_error'],
        'error_count': status['error_count'],
        'last_data_time': status['last_data_time'],
        'subscribed_symbols_count': status['subscribed_symbols_count']
    })

@admin_bp.route('/admin/angelone/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_angelone(user_id):
    """Manage AngelOne API settings for a user"""
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Only admins can have AngelOne credentials
        if not user.is_admin:
            flash("Only admin users can have AngelOne API credentials", "danger")
            return redirect(url_for('admin.users'))
        
        # Update AngelOne credentials
        user.angelone_api_key = request.form.get('angelone_api_key')
        user.angelone_client_code = request.form.get('angelone_client_code')
        user.angelone_password = request.form.get('angelone_password')
        user.angelone_totp_token = request.form.get('angelone_totp_token')
        
        db.session.commit()
        
        flash("AngelOne API credentials updated successfully", "success")
        return redirect(url_for('admin.users'))
    
    return render_template(
        'admin/angelone_settings.html',
        title='AngelOne API Settings',
        user=user
    )