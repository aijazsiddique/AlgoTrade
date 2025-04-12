from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.helpers.websocket_helper import websocket_manager, initialize_angelone_websocket
from app.helpers.openalgo_helper import get_angelone_client
import logging
import pyotp
import json
from datetime import datetime

# Blueprint configuration
websocket_blueprint = Blueprint('websocket', __name__)
logger = logging.getLogger('app')

@websocket_blueprint.route('/websocket/dashboard')
@login_required
def websocket_dashboard():
    """WebSocket dashboard - central page for managing WebSocket connections"""
    # Only allow admin users
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('dashboard.index'))
        
    # Get WebSocket status
    status = websocket_manager.get_connection_status()
    
    return render_template('websocket/dashboard.html', 
                           user=current_user, 
                           ws_status=websocket_manager.get_connection_status(),
                           active_page='websocket_dashboard',
                           status=status,
                           continue_iteration=websocket_manager.continue_iteration)

@websocket_blueprint.route('/websocket/initialize', methods=['POST'])
@login_required
def initialize_websocket():
    """Initialize the WebSocket with current credentials"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        # Initialize websocket using current user credentials
        result = initialize_angelone_websocket(current_user)
        
        # Update database if needed
        if result['success'] and not current_user.angelone_ws_configured:
            current_user.angelone_ws_configured = True
            current_user.angelone_ws_enabled = True
            db.session.commit()
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error initializing WebSocket: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/status')
@login_required
def websocket_status():
    """Get current WebSocket connection status"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        status = websocket_manager.get_connection_status()
        
        # Add connection details
        status['configured'] = current_user.angelone_ws_configured
        status['enabled'] = current_user.angelone_ws_enabled
        
        # Add token update time
        if current_user.angelone_token_updated_at:
            status['token_updated_at'] = current_user.angelone_token_updated_at.strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/refresh-token', methods=['POST'])
@login_required
def refresh_token():
    """Refresh AngelOne tokens and update WebSocket connection"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        # Create AngelOne client
        smart_api = None
        
        try:
            # Check if we need to use TOTP 
            totp_token = None
            if current_user.angelone_totp_token:
                totp = pyotp.TOTP(current_user.angelone_totp_token)
                totp_token = totp.now()
            
            # Initialize Smart API Connect
            smart_api = get_angelone_client(current_user)
            
            # Generate session
            data = {}
            
            if totp_token:
                data = smart_api.generateSession(
                    client_code=current_user.angelone_client_code,
                    password=current_user.angelone_password,
                    totp=totp_token
                )
            else:
                data = smart_api.generateSession(
                    client_code=current_user.angelone_client_code,
                    password=current_user.angelone_password
                )
                
            # Check session response
            if not data or 'data' not in data or not data['data']:
                return jsonify({'success': False, 'message': f'Failed to authenticate: {json.dumps(data)}'})
                
            # Extract tokens
            tokens = data['data']
            
            # Update user tokens in database
            current_user.angelone_jwt_token = tokens.get('jwtToken', '')
            current_user.angelone_refresh_token = tokens.get('refreshToken', '')
            current_user.angelone_feed_token = tokens.get('feedToken', '')
            current_user.angelone_token_updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Reinitialize websocket if it was connected
            result = {'token_update': 'success'}
            if current_user.angelone_ws_enabled:
                ws_result = initialize_angelone_websocket(current_user)
                result['websocket'] = ws_result
            
            return jsonify({
                'success': True, 
                'message': 'Tokens refreshed successfully',
                'result': result
            })
            
        except Exception as auth_err:
            return jsonify({'success': False, 'message': f'Authentication error: {str(auth_err)}'})
            
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/close', methods=['POST'])
@login_required
def close_websocket():
    """Close the WebSocket connection"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        # Close connection
        result = websocket_manager.close_connection()
        
        # Update database
        current_user.angelone_ws_enabled = False
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'WebSocket connection closed',
            'result': result
        })
    except Exception as e:
        logger.error(f"Error closing WebSocket: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/subscribe', methods=['POST'])
@login_required
def subscribe():
    """Subscribe to a symbol"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        data = request.get_json()
        
        if not data or 'symbol' not in data or 'exchange_type' not in data or 'token' not in data:
            return jsonify({'success': False, 'message': 'Missing required parameters'})
            
        symbol = data['symbol']
        exchange_type = data['exchange_type']
        token = data['token']
        mode = data.get('mode', 2)  # Default to Quote mode
        
        # Register symbol
        websocket_manager.register_symbol(symbol, exchange_type, token)
        
        # Subscribe with specified mode
        result = websocket_manager.subscribe_mode(symbol, mode)
        
        if result:
            return jsonify({
                'success': True, 
                'message': f'Subscribed to {symbol} successfully',
                'mode': mode
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'Failed to subscribe to {symbol}: {websocket_manager.last_error}'
            })
            
    except Exception as e:
        logger.error(f"Error subscribing to symbol: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Unsubscribe from a symbol"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        data = request.get_json()
        
        if not data or 'symbol' not in data:
            return jsonify({'success': False, 'message': 'Missing symbol parameter'})
            
        symbol = data['symbol']
        
        # Unsubscribe
        result = websocket_manager.unsubscribe(symbol)
        
        if result:
            return jsonify({
                'success': True, 
                'message': f'Unsubscribed from {symbol} successfully'
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'Failed to unsubscribe from {symbol}: {websocket_manager.last_error}'
            })
            
    except Exception as e:
        logger.error(f"Error unsubscribing from symbol: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/active-symbols')
@login_required
def active_symbols():
    """Get list of active symbol subscriptions"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        active = []
        
        # Get all subscribed symbols
        for symbol, info in websocket_manager.subscribed_symbols.items():
            active.append({
                'symbol': symbol,
                'exchange_type': info['exchange_type'],
                'token': info['token'],
                'mode': info.get('mode', 2),
                'data_points': len(info['data'])
            })
            
        return jsonify({
            'success': True,
            'symbols': active,
            'count': len(active)
        })
            
    except Exception as e:
        logger.error(f"Error getting active symbols: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/symbol-data')
@login_required
def symbol_data():
    """Get OHLC data for a symbol"""
    # Only allow admin users
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'})
        
    try:
        symbol = request.args.get('symbol')
        limit = int(request.args.get('limit', 100))
        
        if not symbol:
            return jsonify({'success': False, 'message': 'Missing symbol parameter'})
            
        if not websocket_manager.is_symbol_subscribed(symbol):
            return jsonify({'success': False, 'message': f'Symbol {symbol} is not subscribed'})
            
        # Get data as dataframe
        df = websocket_manager.get_data_as_dataframe(symbol, limit)
        
        if df.empty:
            return jsonify({
                'success': True,
                'message': f'No data available for {symbol}',
                'data': []
            })
            
        # Convert to list of dictionaries for JSON response
        data = []
        for index, row in df.reset_index().iterrows():
            data.append({
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']) if 'volume' in row else 0
            })
            
        return jsonify({
            'success': True,
            'symbol': symbol,
            'data': data,
            'count': len(data)
        })
            
    except Exception as e:
        logger.error(f"Error getting symbol data: {str(e)}")
        return jsonify({'success': False, 'message': f"Error: {str(e)}"})

@websocket_blueprint.route('/websocket/toggle-iteration', methods=['POST'])
@login_required
def toggle_iteration():
    """Toggle the WebSocket iteration state"""
    try:
        # Get the current state
        current_state = websocket_manager.continue_iteration
        
        # Toggle the state
        websocket_manager.continue_iteration = not current_state
        
        # Log the state change
        new_state = "enabled" if websocket_manager.continue_iteration else "disabled"
        logger.log_websocket_event("ITERATION", f"WebSocket iteration {new_state} by {current_user.username}")
        
        return jsonify({
            "success": True,
            "message": f"WebSocket iteration {new_state}",
            "continue_iteration": websocket_manager.continue_iteration
        })
    except Exception as e:
        logger.log_websocket_event("ITERATION_ERROR", f"Error toggling WebSocket iteration: {str(e)}", level="error")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500