import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class Logger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.getcwd(), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Configure root logger
        logging.basicConfig(level=logging.INFO,
                           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create and configure different loggers
        self.websocket_logger = self._setup_logger('websocket', os.path.join(logs_dir, 'websocket.log'))
        self.strategy_logger = self._setup_logger('strategy', os.path.join(logs_dir, 'strategy.log'))
        self.signal_logger = self._setup_logger('signal', os.path.join(logs_dir, 'signal.log'))
        self.trade_logger = self._setup_logger('trade', os.path.join(logs_dir, 'trade.log'))
        self.app_logger = self._setup_logger('app', os.path.join(logs_dir, 'app.log'))
        
        self.initialized = True
    
    def _setup_logger(self, name, log_file, level=logging.INFO):
        """Set up a logger with file and console handlers"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Create file handler with rotation (10MB max size, 5 backup files)
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger if they don't exist already
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    def log_websocket_event(self, event_type, details=None, level='info'):
        """Log WebSocket events"""
        message = f"WebSocket {event_type}"
        if details:
            message += f": {details}"
        
        log_method = getattr(self.websocket_logger, level.lower())
        log_method(message)
    
    def log_strategy_event(self, strategy_name, instance_name, event_type, details=None, level='info'):
        """Log strategy events"""
        message = f"Strategy '{strategy_name}' (Instance: {instance_name}) - {event_type}"
        if details:
            message += f": {details}"
        
        log_method = getattr(self.strategy_logger, level.lower())
        log_method(message)
    
    def log_signal(self, strategy_name, instance_name, symbol, signal_type, details=None):
        """Log trade signals"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"SIGNAL: {signal_type} - Strategy: {strategy_name}, Instance: {instance_name}, Symbol: {symbol}, Time: {timestamp}"
        if details:
            message += f", Details: {details}"
        
        self.signal_logger.info(message)
    
    def log_trade(self, webhook_id, symbol, action, position_size, response=None):
        """Log trade execution"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"TRADE: Action: {action}, Symbol: {symbol}, Size: {position_size}, Time: {timestamp}, Webhook: {webhook_id}"
        if response:
            message += f", Response: {response}"
        
        self.trade_logger.info(message)
    
    def log_app_event(self, event_type, details=None, level='info'):
        """Log general application events"""
        message = f"APP {event_type}"
        if details:
            message += f": {details}"
        
        log_method = getattr(self.app_logger, level.lower())
        log_method(message)

# Create the singleton logger instance
logger = Logger()