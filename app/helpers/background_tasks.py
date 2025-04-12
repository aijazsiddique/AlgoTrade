import threading
import time
import traceback
from datetime import datetime, timedelta
from SmartApi import SmartConnect
import pyotp
from app import db
from app.models.user import User
from app.helpers.websocket_helper import websocket_manager
from app.helpers.logger_helper import logger
from flask import current_app
from sqlalchemy.exc import OperationalError, SQLAlchemyError

class BackgroundTaskManager:
    """
    Manager for background tasks such as token refresh and WebSocket monitoring
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackgroundTaskManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        self.tasks = {}
        self.running = False
        self.app = None
        self.initialized = True
        # Track database errors to avoid excessive retries
        self.db_error_count = 0
        self.last_db_error = None
        self.db_retry_interval = 300  # 5 minutes between retries after multiple failures
        
    def start_all_tasks(self, app=None):
        """Start all registered background tasks"""
        if self.running:
            return False
        
        # Store Flask app reference    
        self.app = app or current_app._get_current_object()
        
        self.running = True
        
        # Start token refresh task
        self.start_task('token_refresh', self._token_refresh_task, interval_seconds=3600)
        
        # Start WebSocket monitor task
        self.start_task('websocket_monitor', self._websocket_monitor_task, interval_seconds=60)
        
        logger.log_app_event("BACKGROUND_TASKS", "Started all background tasks")
        return True
        
    def stop_all_tasks(self):
        """Stop all running background tasks"""
        if not self.running:
            return False
            
        for task_name in list(self.tasks.keys()):
            self.stop_task(task_name)
            
        self.running = False
        logger.log_app_event("BACKGROUND_TASKS", "Stopped all background tasks")
        return True
        
    def start_task(self, task_name, task_function, interval_seconds=60, *args, **kwargs):
        """Start a background task"""
        if task_name in self.tasks and self.tasks[task_name]['running']:
            return False
            
        # Create control event for stopping the task
        stop_event = threading.Event()
        
        # Create thread object with app context
        thread = threading.Thread(
            target=self._task_runner,
            args=(stop_event, task_function, interval_seconds, self.app) + args,
            kwargs=kwargs,
            name=f"BgTask-{task_name}",
            daemon=True
        )
        
        # Store task info
        self.tasks[task_name] = {
            'thread': thread,
            'stop_event': stop_event,
            'interval': interval_seconds,
            'running': True,
            'started_at': datetime.utcnow()
        }
        
        # Start thread
        thread.start()
        
        logger.log_app_event("TASK_START", f"Started background task: {task_name}")
        return True
        
    def stop_task(self, task_name):
        """Stop a running background task"""
        if task_name not in self.tasks or not self.tasks[task_name]['running']:
            return False
            
        # Signal thread to stop
        self.tasks[task_name]['stop_event'].set()
        
        # Wait for thread to terminate (with timeout)
        self.tasks[task_name]['thread'].join(timeout=5)
        
        # Update status
        self.tasks[task_name]['running'] = False
        
        logger.log_app_event("TASK_STOP", f"Stopped background task: {task_name}")
        return True
        
    def _task_runner(self, stop_event, task_function, interval_seconds, app, *args, **kwargs):
        """Generic task runner that handles the interval and stopping"""
        # Create application context for this thread
        with app.app_context():
            while not stop_event.is_set():
                try:
                    # Run the task function within app context
                    task_function(*args, **kwargs)
                except Exception as e:
                    logger.log_app_event("TASK_ERROR", f"Error in background task: {str(e)}", "error")
                    logger.log_app_event("TASK_ERROR", traceback.format_exc(), "error")
                
                # Sleep until next run or until stopped
                # Using small sleep intervals to check stop_event more frequently
                for _ in range(interval_seconds):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
    
    def _should_retry_db_operation(self):
        """Determine if we should retry a database operation after failures"""
        now = datetime.utcnow()
        
        # If this is the first error, or if sufficient time has passed since multiple errors
        if self.db_error_count == 0 or not self.last_db_error:
            return True
            
        # After multiple errors, only retry after the retry interval
        if self.db_error_count > 3:
            time_since_error = (now - self.last_db_error).total_seconds()
            return time_since_error > self.db_retry_interval
            
        return True
                
    def _token_refresh_task(self):
        """Task to refresh AngelOne tokens periodically"""
        if not self._should_retry_db_operation():
            return
            
        try:
            # Get admin user with AngelOne enabled
            admin = User.query.filter_by(
                is_admin=True, 
                angelone_ws_enabled=True
            ).first()
            
            # Reset error counter on success
            self.db_error_count = 0
            self.last_db_error = None
            
            if not admin or not admin.angelone_refresh_token:
                logger.log_app_event("TOKEN_REFRESH", "No active admin with AngelOne tokens", "warning")
                return
                
            # Calculate token age
            if not admin.angelone_token_updated_at:
                # If no update time recorded, assume token is old
                needs_refresh = True
                token_age_seconds = 0
            else:
                # Check if token is older than 6 hours
                token_age = datetime.utcnow() - admin.angelone_token_updated_at
                token_age_seconds = token_age.total_seconds()
                needs_refresh = token_age > timedelta(hours=6)
            
            if needs_refresh:
                logger.log_app_event("TOKEN_REFRESH", f"Refreshing AngelOne tokens (age: {token_age_seconds/3600:.1f} hours)")
                
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
                        logger.log_app_event("TOKEN_REFRESH", "Reconnecting WebSocket with new tokens")
                        websocket_manager.configure(
                            admin.angelone_jwt_token,
                            admin.angelone_api_key,
                            admin.angelone_client_code,
                            admin.angelone_feed_token
                        )
                        websocket_manager.reconnect()
                    
                    logger.log_app_event("TOKEN_REFRESH", "AngelOne tokens refreshed successfully")
                else:
                    logger.log_app_event(
                        "TOKEN_REFRESH_ERROR", 
                        f"Failed to refresh tokens: {refresh_response.get('message', 'Unknown error')}",
                        "error"
                    )
            else:
                # Log that tokens are still valid
                hours_remaining = 6 - (token_age_seconds / 3600)
                logger.log_app_event(
                    "TOKEN_REFRESH", 
                    f"Tokens still valid. Next refresh in ~{hours_remaining:.1f} hours"
                )
        
        except (OperationalError, SQLAlchemyError) as e:
            # Track database errors
            self.db_error_count += 1
            self.last_db_error = datetime.utcnow()
            logger.log_app_event("TOKEN_REFRESH_ERROR", f"Database error: {str(e)}", "error")
            
            # Only log detailed traceback on first few errors to avoid log spam
            if self.db_error_count <= 3:
                logger.log_app_event("TOKEN_REFRESH_ERROR", traceback.format_exc(), "error")
            
        except Exception as e:
            logger.log_app_event("TOKEN_REFRESH_ERROR", f"Error refreshing tokens: {str(e)}", "error")
            logger.log_app_event("TOKEN_REFRESH_ERROR", traceback.format_exc(), "error")
    
    def _websocket_monitor_task(self):
        """Task to monitor WebSocket health and reconnect if needed"""
        if not self._should_retry_db_operation():
            return
            
        try:
            # Only run if WebSocket is supposed to be connected
            admin = User.query.filter_by(angelone_ws_enabled=True).first()
            
            # Reset error counter on success
            self.db_error_count = 0
            self.last_db_error = None
            
            if not admin:
                return
                
            # Check WebSocket status
            status = websocket_manager.get_connection_status()
            
            # If not connected, try to reconnect
            if not status['connected']:
                logger.log_app_event("WEBSOCKET_MONITOR", "WebSocket disconnected, attempting to reconnect")
                
                # Configure and connect WebSocket
                websocket_manager.configure(
                    admin.angelone_jwt_token,
                    admin.angelone_api_key,
                    admin.angelone_client_code,
                    admin.angelone_feed_token
                )
                
                websocket_manager.connect()
            else:
                # Check time since last data
                if status['last_data_time']:
                    time_since_data = (datetime.utcnow() - status['last_data_time']).total_seconds()
                    if time_since_data > 300:  # 5 minutes
                        logger.log_app_event(
                            "WEBSOCKET_MONITOR", 
                            f"No data received for {time_since_data/60:.1f} minutes, forcing reconnect"
                        )
                        websocket_manager.reconnect()
                    else:
                        logger.log_app_event(
                            "WEBSOCKET_MONITOR", 
                            f"WebSocket healthy: {status['subscribed_symbols_count']} symbols, last data {time_since_data:.1f} seconds ago"
                        )
                        
        except (OperationalError, SQLAlchemyError) as e:
            # Track database errors
            self.db_error_count += 1
            self.last_db_error = datetime.utcnow()
            logger.log_app_event("WEBSOCKET_MONITOR_ERROR", f"Database error: {str(e)}", "error")
            
            # Only log detailed traceback on first few errors to avoid log spam
            if self.db_error_count <= 3:
                logger.log_app_event("WEBSOCKET_MONITOR_ERROR", traceback.format_exc(), "error")
            
        except Exception as e:
            logger.log_app_event("WEBSOCKET_MONITOR_ERROR", f"Error monitoring WebSocket: {str(e)}", "error")
            logger.log_app_event("WEBSOCKET_MONITOR_ERROR", traceback.format_exc(), "error")

# Singleton instance
task_manager = BackgroundTaskManager()