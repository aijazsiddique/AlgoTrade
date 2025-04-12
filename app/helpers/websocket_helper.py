from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import threading
import json
import time
import pandas as pd
from datetime import datetime
import queue
import traceback
import logging
from app.helpers.logger_helper import logger

# Configure WebSocket logger
ws_logger = logging.getLogger("websocket")
ws_logger.setLevel(logging.INFO)

class AngelOneWebSocketManager:
    """
    Singleton WebSocket client manager for AngelOne to manage all WebSocket connections
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AngelOneWebSocketManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        self.auth_token = None
        self.api_key = None
        self.client_code = None
        self.feed_token = None
        self.ws = None
        self.connected = False
        self.subscribed_symbols = {}  # symbol -> {exchange_type, token, callbacks: [], data: []}
        self.symbol_token_map = {}  # symbol -> {exchange_type, token}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.data_buffer_max_size = 1000  # Max number of ticks to store per symbol
        self.data_lock = threading.Lock()  # For thread-safe operations
        self.update_queue = queue.Queue()  # Queue for processing WebSocket updates
        self.last_error = None
        self.error_count = 0
        self.last_data_time = None
        self.health_check_interval = 30  # Seconds between health checks
        self.health_check_running = False
        self.continue_iteration = True  # Flag to control if the WebSocket should continue iterating
        self.initialized = True
        
        # Log initialization
        logger.log_websocket_event("INIT", "WebSocket manager initialized")
        
    def configure(self, auth_token, api_key, client_code, feed_token):
        """Configure the WebSocket with authentication details"""
        # Reset error state
        self.last_error = None
        self.error_count = 0
        
        try:
            logger.log_websocket_event("CONFIG", f"Configuring WebSocket for client: {client_code}")
            self.auth_token = auth_token
            self.api_key = api_key
            self.client_code = client_code
            self.feed_token = feed_token
            
            # Close existing connection if any
            if self.connected:
                self.close_connection()
                
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("CONFIG_ERROR", str(e), level="error")
            return False
        
    def connect(self):
        """Connect to AngelOne WebSocket"""
        if not all([self.auth_token, self.api_key, self.client_code, self.feed_token]):
            logger.log_websocket_event("CONNECT_ERROR", "WebSocket not configured. Call configure() first.", level="error")
            self.last_error = "WebSocket not properly configured. Missing credentials."
            return False
            
        try:
            logger.log_websocket_event("CONNECT", "Initializing WebSocket connection...")
            
            # Initialize the SmartWebSocketV2 client with proper parameters
            self.ws = SmartWebSocketV2(
                self.auth_token, 
                self.api_key, 
                self.client_code,
                self.feed_token
            )
            
            # Set up callbacks
            # Make sure to use lambda functions to ensure 'self' context is preserved
            self.ws.on_open = lambda wsapp: self._on_open(wsapp)
            self.ws.on_data = lambda wsapp, message: self._on_data(wsapp, message)
            self.ws.on_error = lambda wsapp, error: self._on_error(wsapp, error)
            self.ws.on_close = lambda wsapp, close_status_code=None, close_msg=None: self._on_close(wsapp, close_status_code, close_msg)
            
            # Start WebSocket connection in a separate thread
            logger.log_websocket_event("CONNECT", "Starting WebSocket connection thread...")
            self.ws_thread = threading.Thread(target=self.ws.connect, name="WebSocketConnection")
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Start tick processor thread
            logger.log_websocket_event("CONNECT", "Starting tick processing thread...")
            self.processor_thread = threading.Thread(target=self._process_update_queue, name="TickProcessor")
            self.processor_thread.daemon = True
            self.processor_thread.start()
            
            # Start health check thread
            if not self.health_check_running:
                logger.log_websocket_event("CONNECT", "Starting health check thread...")
                self.health_check_running = True
                self.health_check_thread = threading.Thread(target=self._health_check, name="HealthCheck")
                self.health_check_thread.daemon = True
                self.health_check_thread.start()
            
            # Wait for connection to establish
            timeout = 10
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                self.last_error = "WebSocket connection timed out"
                logger.log_websocket_event("CONNECT_TIMEOUT", "Connection timed out", level="error")
                return False
                
            logger.log_websocket_event("CONNECTED", "WebSocket connection established successfully")
            return self.connected
            
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("CONNECT_ERROR", f"WebSocket connection error: {e}", level="error")
            logger.log_websocket_event("CONNECT_ERROR", traceback.format_exc(), level="error")
            return False
    
    def _health_check(self):
        """Periodically check WebSocket health and send heartbeats"""
        logger.log_websocket_event("HEALTH_CHECK", "Health check thread started")
        
        while self.health_check_running:
            try:
                # Send heartbeat if connected
                if self.connected and self.ws:
                    logger.log_websocket_event("HEARTBEAT", "Sending ping")
                    self.ws.send("ping")
                
                # Check if connected
                if not self.connected:
                    logger.log_websocket_event("HEALTH_CHECK", "WebSocket not connected, attempting to reconnect...", level="warning")
                    self.reconnect()
                
                # Check for data freshness (if we have subscribed symbols)
                elif self.subscribed_symbols and self.last_data_time:
                    time_since_data = (datetime.now() - self.last_data_time).total_seconds()
                    if time_since_data > 60:  # No data for 60 seconds
                        logger.log_websocket_event("HEALTH_CHECK", f"No data received for {time_since_data:.1f} seconds, reconnecting...", level="warning")
                        self.reconnect()
                        
                # Check error count
                if self.error_count > 10:
                    logger.log_websocket_event("HEALTH_CHECK", "Too many errors, reconnecting...", level="warning")
                    self.error_count = 0
                    self.reconnect()
            except Exception as e:
                logger.log_websocket_event("HEALTH_CHECK_ERROR", f"Error in health check: {str(e)}", level="error")
            
            # Sleep before next check - 30 seconds as specified in documentation
            time.sleep(30)
    
    def reconnect(self):
        """Attempt to reconnect to the WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.log_websocket_event("RECONNECT_FAILED", f"Maximum reconnect attempts ({self.max_reconnect_attempts}) reached", level="error")
            return False
            
        self.reconnect_attempts += 1
        logger.log_websocket_event("RECONNECT", f"Attempting to reconnect (Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        try:
            # Close existing connection if any
            if self.ws:
                try:
                    self.ws.close_connection()
                except:
                    pass
                
            # Reset connection status
            self.connected = False
            
            # Wait before reconnecting
            time.sleep(2)
            
            # Try to connect again
            return self.connect()
            
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("RECONNECT_ERROR", f"Error during reconnect: {str(e)}", level="error")
            return False
    
    def _on_open(self, wsapp):
        """Called when WebSocket connection is opened"""
        logger.log_websocket_event("OPEN", "WebSocket connection established")
        self.connected = True
        self.reconnect_attempts = 0
        self.last_data_time = datetime.now()
        
        # Re-subscribe to symbols
        if self.subscribed_symbols:
            # Group tokens by exchange type for efficient subscription
            exchange_tokens = {}
            for symbol_info in self.subscribed_symbols.values():
                exchange_type = symbol_info['exchange_type']
                token = symbol_info['token']
                
                if exchange_type not in exchange_tokens:
                    exchange_tokens[exchange_type] = []
                    
                exchange_tokens[exchange_type].append(token)
            
            # Create token_list structure for AngelOne API
            token_list = [
                {
                    "exchangeType": int(exchange_type),
                    "tokens": tokens
                }
                for exchange_type, tokens in exchange_tokens.items()
            ]
            
            # Subscribe to all tokens
            if token_list:
                correlation_id = "reconnect_" + str(int(time.time()))
                try:
                    self.ws.subscribe(correlation_id, 1, token_list)  # Mode 1 = OHLC quotes
                    logger.log_websocket_event("RESUBSCRIBE", f"Resubscribed to {sum(len(tokens) for _, tokens in exchange_tokens.items())} tokens")
                except Exception as e:
                    logger.log_websocket_event("RESUBSCRIBE_ERROR", f"Error resubscribing to tokens: {str(e)}", level="error")
    
    def _on_data(self, wsapp, message):
        """Called when a message is received from WebSocket"""
        # Update last data time
        self.last_data_time = datetime.now()
        
        # Check for pong response to heartbeat
        if message == "pong":
            logger.log_websocket_event("HEARTBEAT", "Received pong response")
            return
        
        # Handle binary data
        if isinstance(message, bytes):
            # Put the binary update in the queue for processing
            self.update_queue.put(message)
        else:
            # Handle JSON response (error messages, etc.)
            try:
                if isinstance(message, dict):
                    # Already a dict object
                    json_message = message
                else:
                    # Try to parse as JSON
                    json_message = json.loads(message)
                    
                if "errorCode" in json_message:
                    logger.log_websocket_event("ERROR", f"Received error: {json_message}", level="error")
                    
                self.update_queue.put(json_message)
            except Exception as e:
                logger.log_websocket_event("DATA_ERROR", f"Unrecognized message format: {message if isinstance(message, str) else str(message)[:100]}", level="error")
    
    def _process_update_queue(self):
        """Process WebSocket updates from the queue"""
        logger.log_websocket_event("PROCESS", "Tick processor thread started")
        
        while self.continue_iteration:
            try:
                # Block until an item is available
                message = self.update_queue.get(timeout=1)
                
                # Process message based on type
                if isinstance(message, bytes):
                    # Process binary data
                    tick_data = self._process_binary_tick(message)
                    if tick_data:
                        # Only process if we successfully parsed the binary data
                        self._handle_parsed_tick(tick_data)
                elif isinstance(message, dict):
                    # Process JSON data
                    self._process_tick(message)
                elif isinstance(message, list):
                    # Process list of ticks
                    for tick in message:
                        self._process_tick(tick)
                
                # Mark task as done
                self.update_queue.task_done()
                
            except queue.Empty:
                # No items in queue, just continue
                continue
            except Exception as e:
                self.error_count += 1
                logger.log_websocket_event("PROCESS_ERROR", f"Error processing tick: {str(e)}", level="error")
                logger.log_websocket_event("PROCESS_ERROR", traceback.format_exc(), level="error")
                
            # Brief sleep to prevent high CPU usage
            time.sleep(0.001)
    
    def _process_tick(self, tick):
        """Process a single tick update"""
        try:
            # Find the token
            token = str(tick.get('tk', ''))
            exchange_type = str(tick.get('e', ''))
            
            if not token or not exchange_type:
                logger.log_websocket_event("TICK_ERROR", f"Received tick without token or exchange: {tick}", level="warning")
                return
            
            # Find which symbol this belongs to
            symbol = None
            for sym, info in self.symbol_token_map.items():
                if info['token'] == token and str(info['exchange_type']) == exchange_type:
                    symbol = sym
                    break
            
            if not symbol:
                logger.log_websocket_event("TICK_WARNING", f"Received tick for unknown symbol: exchange={exchange_type}, token={token}", level="debug")
                return
                
            if symbol not in self.subscribed_symbols:
                logger.log_websocket_event("TICK_WARNING", f"Received tick for unsubscribed symbol: {symbol}", level="debug")
                return
            
            with self.data_lock:
                # Format the data
                timestamp = datetime.fromtimestamp(int(tick.get('ft', time.time())))
                
                # Check for required tick fields
                if 'o' not in tick or 'h' not in tick or 'l' not in tick or 'c' not in tick:
                    logger.log_websocket_event("TICK_ERROR", f"Incomplete tick data for {symbol}: {tick}", level="warning")
                    return
                
                formatted_tick = {
                    'timestamp': timestamp,
                    'open': float(tick.get('o', 0)),
                    'high': float(tick.get('h', 0)),
                    'low': float(tick.get('l', 0)), 
                    'close': float(tick.get('c', 0)),
                    'volume': int(tick.get('v', 0))
                }
                
                # Add to data buffer (limiting size)
                self.subscribed_symbols[symbol]['data'].append(formatted_tick)
                if len(self.subscribed_symbols[symbol]['data']) > self.data_buffer_max_size:
                    self.subscribed_symbols[symbol]['data'] = self.subscribed_symbols[symbol]['data'][-self.data_buffer_max_size:]
                
                # Notify callbacks
                for callback in self.subscribed_symbols[symbol]['callbacks']:
                    try:
                        callback(formatted_tick, symbol)
                    except Exception as callback_err:
                        logger.log_websocket_event("CALLBACK_ERROR", f"Callback error for {symbol}: {str(callback_err)}", level="error")
                
        except Exception as e:
            self.error_count += 1
            logger.log_websocket_event("TICK_PROCESS_ERROR", f"Error processing tick data: {str(e)}", level="error")
            logger.log_websocket_event("TICK_PROCESS_ERROR", traceback.format_exc(), level="error")
    
    def _process_binary_tick(self, binary_data):
        """Process binary data according to the Angel One specification"""
        try:
            # Check if we have enough data for at least the LTP mode
            if len(binary_data) < 51:
                logger.log_websocket_event("BINARY_ERROR", f"Binary data too short: {len(binary_data)} bytes", level="error")
                return None
                
            # Parse common fields (first part of message)
            mode = binary_data[0]  # Subscription mode
            exchange_type = binary_data[1]  # Exchange type
            
            # Extract token (null-terminated string)
            token_end = 2
            while token_end < 27 and binary_data[token_end] != 0:
                token_end += 1
            token = binary_data[2:token_end].decode('utf-8')
            
            # Find which symbol this belongs to
            symbol = None
            for sym, info in self.symbol_token_map.items():
                if info['token'] == token and str(info['exchange_type']) == str(exchange_type):
                    symbol = sym
                    break
            
            if not symbol:
                logger.log_websocket_event("BINARY_WARNING", f"Received tick for unknown symbol: exchange={exchange_type}, token={token}", level="debug")
                return None
            
            # Process based on mode
            result = {
                'symbol': symbol,
                'exchange_type': exchange_type,
                'token': token,
                'mode': mode,
                'timestamp': datetime.now()  # Default timestamp until we extract from binary
            }
            
            # Extract fields based on mode
            if mode == 1:  # LTP mode
                if len(binary_data) >= 46:
                    # Parse LTP mode fields (Section-1)
                    result['last_price'] = int.from_bytes(binary_data[43:51], byteorder='little') / 100
                    
                    # Update timestamp if available (from exchange)
                    timestamp_bytes = binary_data[27:35]
                    if any(timestamp_bytes):  # Check if timestamp is not all zeros
                        try:
                            timestamp_int = int.from_bytes(timestamp_bytes, byteorder='little')
                            result['timestamp'] = datetime.fromtimestamp(timestamp_int)
                        except Exception as e:
                            logger.log_websocket_event("TIMESTAMP_ERROR", f"Error parsing timestamp: {str(e)}", level="debug")
                    
                    return result
                    
            elif mode == 2:  # Quote mode (Section-1 + Section-2)
                if len(binary_data) >= 187:
                    # Parse quote mode fields
                    result['last_price'] = int.from_bytes(binary_data[43:51], byteorder='little') / 100
                    result['last_traded_quantity'] = int.from_bytes(binary_data[51:59], byteorder='little')
                    result['average_traded_price'] = int.from_bytes(binary_data[59:67], byteorder='little') / 100
                    result['volume_traded'] = int.from_bytes(binary_data[67:75], byteorder='little')
                    result['total_buy_quantity'] = int.from_bytes(binary_data[75:83], byteorder='little')
                    result['total_sell_quantity'] = int.from_bytes(binary_data[83:91], byteorder='little')
                    result['open_price'] = int.from_bytes(binary_data[91:99], byteorder='little') / 100
                    result['high_price'] = int.from_bytes(binary_data[99:107], byteorder='little') / 100
                    result['low_price'] = int.from_bytes(binary_data[107:115], byteorder='little') / 100
                    result['close_price'] = int.from_bytes(binary_data[115:123], byteorder='little') / 100
                    result['yearly_high'] = int.from_bytes(binary_data[123:131], byteorder='little') / 100
                    result['yearly_low'] = int.from_bytes(binary_data[131:139], byteorder='little') / 100
                    
                    # Parse best 5 bid/ask
                    # Bids
                    result['best_bid_price'] = int.from_bytes(binary_data[139:147], byteorder='little') / 100
                    result['best_bid_quantity'] = int.from_bytes(binary_data[147:155], byteorder='little')
                    # More fields can be parsed for full bid-ask ladder
                    
                    # Update timestamp
                    timestamp_bytes = binary_data[27:35]
                    if any(timestamp_bytes):
                        try:
                            timestamp_int = int.from_bytes(timestamp_bytes, byteorder='little')
                            result['timestamp'] = datetime.fromtimestamp(timestamp_int)
                        except Exception as e:
                            logger.log_websocket_event("TIMESTAMP_ERROR", f"Error parsing timestamp: {str(e)}", level="debug")
                    
                    return result
                    
            elif mode == 3:  # Snap quote mode (Section-1 + Section-2 + parts of Section-3)
                # Similar parsing for snap quote mode
                # Includes more fields from Section 3 like circuit limits, etc.
                if len(binary_data) >= 243:
                    # Parse basic fields first (similar to mode 2)
                    result['last_price'] = int.from_bytes(binary_data[43:51], byteorder='little') / 100
                    result['last_traded_quantity'] = int.from_bytes(binary_data[51:59], byteorder='little')
                    result['average_traded_price'] = int.from_bytes(binary_data[59:67], byteorder='little') / 100
                    result['volume_traded'] = int.from_bytes(binary_data[67:75], byteorder='little')
                    result['total_buy_quantity'] = int.from_bytes(binary_data[75:83], byteorder='little')
                    result['total_sell_quantity'] = int.from_bytes(binary_data[83:91], byteorder='little')
                    result['open_price'] = int.from_bytes(binary_data[91:99], byteorder='little') / 100
                    result['high_price'] = int.from_bytes(binary_data[99:107], byteorder='little') / 100
                    result['low_price'] = int.from_bytes(binary_data[107:115], byteorder='little') / 100
                    result['close_price'] = int.from_bytes(binary_data[115:123], byteorder='little') / 100
                    
                    # Additional snap quote fields from Section 3
                    result['upper_circuit'] = int.from_bytes(binary_data[187:195], byteorder='little') / 100
                    result['lower_circuit'] = int.from_bytes(binary_data[195:203], byteorder='little') / 100
                    
                    # Update timestamp
                    timestamp_bytes = binary_data[27:35]
                    if any(timestamp_bytes):
                        try:
                            timestamp_int = int.from_bytes(timestamp_bytes, byteorder='little')
                            result['timestamp'] = datetime.fromtimestamp(timestamp_int)
                        except Exception as e:
                            logger.log_websocket_event("TIMESTAMP_ERROR", f"Error parsing timestamp: {str(e)}", level="debug")
                    
                    return result
                    
            elif mode == 4:  # Full quote with depth (full data)
                # Parse full quote with market depth
                # This includes all sections from the binary specification
                # Fields would be similar to mode 3 but with full market depth data
                logger.log_websocket_event("BINARY_INFO", f"Full quote mode received for {symbol}", level="debug")
                # Full implementation would be too long for this example but follows same pattern
                return None
            
            logger.log_websocket_event("BINARY_WARNING", f"Unsupported mode {mode} for {symbol}", level="warning")
            return None
                
        except Exception as e:
            self.error_count += 1
            logger.log_websocket_event("BINARY_PROCESS_ERROR", f"Error processing binary data: {str(e)}", level="error")
            logger.log_websocket_event("BINARY_PROCESS_ERROR", traceback.format_exc(), level="error")
            return None
    
    def _handle_parsed_tick(self, tick_data):
        """Handle a parsed tick from binary data"""
        try:
            symbol = tick_data.get('symbol')
            
            if not symbol or symbol not in self.subscribed_symbols:
                logger.log_websocket_event("TICK_WARNING", f"Received parsed tick for unsubscribed symbol: {symbol}", level="debug")
                return
            
            with self.data_lock:
                # Format for our standard tick format
                timestamp = tick_data.get('timestamp', datetime.now())
                
                # Convert binary mode data to our standard format
                mode = tick_data.get('mode')
                formatted_tick = {
                    'timestamp': timestamp
                }
                
                # Fill in the OHLCV data based on mode
                if mode == 1:  # LTP mode
                    # In LTP mode, we only have the last price, so use it for all OHLC fields
                    ltp = tick_data.get('last_price', 0)
                    formatted_tick.update({
                        'open': ltp,
                        'high': ltp,
                        'low': ltp,
                        'close': ltp,
                        'volume': 0  # No volume info in LTP mode
                    })
                elif mode in (2, 3, 4):  # Quote modes with more data
                    # For these modes we have full OHLCV data
                    formatted_tick.update({
                        'open': tick_data.get('open_price', 0),
                        'high': tick_data.get('high_price', 0),
                        'low': tick_data.get('low_price', 0),
                        'close': tick_data.get('last_price', 0),
                        'volume': tick_data.get('volume_traded', 0)
                    })
                
                # Add to data buffer (limiting size)
                self.subscribed_symbols[symbol]['data'].append(formatted_tick)
                if len(self.subscribed_symbols[symbol]['data']) > self.data_buffer_max_size:
                    self.subscribed_symbols[symbol]['data'] = self.subscribed_symbols[symbol]['data'][-self.data_buffer_max_size:]
                
                # Notify callbacks
                for callback in self.subscribed_symbols[symbol]['callbacks']:
                    try:
                        callback(formatted_tick, symbol)
                    except Exception as callback_err:
                        logger.log_websocket_event("CALLBACK_ERROR", f"Callback error for {symbol}: {str(callback_err)}", level="error")
        
        except Exception as e:
            self.error_count += 1
            logger.log_websocket_event("PARSED_TICK_ERROR", f"Error handling parsed tick: {str(e)}", level="error")
            logger.log_websocket_event("PARSED_TICK_ERROR", traceback.format_exc(), level="error")
    
    def _on_error(self, wsapp, error):
        """Called when WebSocket error occurs"""
        self.error_count += 1
        self.last_error = str(error)
        logger.log_websocket_event("ERROR", f"WebSocket error: {str(error)}", level="error")
    
    def _on_close(self, wsapp, close_status_code=None, close_msg=None):
        """Called when WebSocket connection closes"""
        logger.log_websocket_event("CLOSE", f"WebSocket connection closed: {close_msg} (Code: {close_status_code})")
        self.connected = False
        
        # Try to reconnect
        if self.reconnect_attempts < self.max_reconnect_attempts:
            logger.log_websocket_event("CLOSE", f"Attempting to reconnect (Attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
            self.reconnect()
    
    def register_symbol(self, symbol, exchange_type, token):
        """Register a symbol's token mapping"""
        try:
            # Validate inputs
            if not symbol or not exchange_type or not token:
                logger.log_websocket_event("REGISTER_ERROR", "Invalid symbol registration parameters", level="error")
                return False
                
            self.symbol_token_map[symbol] = {
                'exchange_type': exchange_type,
                'token': token
            }
            logger.log_websocket_event("REGISTER", f"Registered symbol mapping: {symbol} -> {exchange_type}:{token}")
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("REGISTER_ERROR", f"Error registering symbol {symbol}: {str(e)}", level="error")
            return False
    
    def subscribe(self, symbol, callback=None):
        """Subscribe to market data for a symbol"""
        try:
            if not self.connected:
                logger.log_websocket_event("SUBSCRIBE_ERROR", f"Cannot subscribe to {symbol}: WebSocket not connected", level="warning")
                return False
                
            if symbol not in self.symbol_token_map:
                logger.log_websocket_event("SUBSCRIBE_ERROR", f"Symbol {symbol} not registered. Call register_symbol() first.", level="error")
                return False
                
            exchange_type = self.symbol_token_map[symbol]['exchange_type']
            token = self.symbol_token_map[symbol]['token']
            
            with self.data_lock:
                if symbol in self.subscribed_symbols:
                    # Already subscribed, just add callback
                    if callback and callback not in self.subscribed_symbols[symbol]['callbacks']:
                        self.subscribed_symbols[symbol]['callbacks'].append(callback)
                    logger.log_websocket_event("SUBSCRIBE", f"Added callback for already subscribed symbol: {symbol}")
                    return True
                    
                # Create new subscription
                self.subscribed_symbols[symbol] = {
                    'exchange_type': exchange_type,
                    'token': token,
                    'callbacks': [callback] if callback else [],
                    'data': []
                }
                
            # Subscribe to the token - format specifically for Angel One API
            token_list = [
                {
                    "exchangeType": int(exchange_type),
                    "tokens": [token]
                }
            ]
            
            # Create a unique correlation ID for this subscription
            correlation_id = f"subscribe_{symbol}_{int(time.time())}"
            
            try:
                # Mode 2 for Quote mode (includes OHLC data)
                self.ws.subscribe(correlation_id, 2, token_list)  
                logger.log_websocket_event("SUBSCRIBE", f"Subscribed to symbol: {symbol} ({exchange_type}:{token}) in mode 2")
                return True
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                logger.log_websocket_event("SUBSCRIBE_ERROR", f"Error subscribing to {symbol}: {str(e)}", level="error")
                with self.data_lock:
                    if symbol in self.subscribed_symbols:
                        del self.subscribed_symbols[symbol]
                return False
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.log_websocket_event("SUBSCRIBE_ERROR", f"Error in subscribe for {symbol}: {str(e)}", level="error")
            logger.log_websocket_event("SUBSCRIBE_ERROR", traceback.format_exc(), level="error")
            return False
    
    def subscribe_index(self, symbol, exchange_type, token, callback=None):
        """
        Subscribe to an index - indices require special handling in Angel One API
        
        Args:
            symbol (str): Symbol or name of the index
            exchange_type (int): Exchange type ID (1=NSE, 2=BSE, etc.)
            token (str): Index token from Angel One
            callback (callable): Optional callback function to call on data updates
        """
        try:
            if not self.connected:
                logger.log_websocket_event("SUBSCRIBE_INDEX_ERROR", f"Cannot subscribe to index {symbol}: WebSocket not connected", level="warning")
                return False
            
            # Register the symbol first if not done already
            if symbol not in self.symbol_token_map:
                self.register_symbol(symbol, exchange_type, token)
            
            # Set up the index-specific subscription format
            token_list = [
                {
                    "exchangeType": int(exchange_type),
                    "tokens": [token]
                }
            ]
            
            # Create subscription entry with buffer
            with self.data_lock:
                self.subscribed_symbols[symbol] = {
                    'exchange_type': exchange_type,
                    'token': token,
                    'callbacks': [callback] if callback else [],
                    'data': [],
                    'is_index': True  # Flag to mark this as an index
                }
            
            # Create correlation ID
            correlation_id = f"subscribe_index_{symbol}_{int(time.time())}"
            
            try:
                # Use mode 1 (LTP) for indices since that's usually what's needed 
                self.ws.subscribe(correlation_id, 1, token_list)
                logger.log_websocket_event("SUBSCRIBE_INDEX", f"Subscribed to index: {symbol} ({exchange_type}:{token}) in mode 1")
                return True
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                logger.log_websocket_event("SUBSCRIBE_INDEX_ERROR", f"Error subscribing to index {symbol}: {str(e)}", level="error")
                with self.data_lock:
                    if symbol in self.subscribed_symbols:
                        del self.subscribed_symbols[symbol]
                return False
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.log_websocket_event("SUBSCRIBE_INDEX_ERROR", f"Error in subscribe_index for {symbol}: {str(e)}", level="error")
            logger.log_websocket_event("SUBSCRIBE_INDEX_ERROR", traceback.format_exc(), level="error")
            return False
    
    def subscribe_mode(self, symbol, mode=2, callback=None):
        """
        Subscribe to market data for a symbol with a specific mode
        
        Args:
            symbol (str): Symbol to subscribe to
            mode (int): Subscription mode: 1=LTP, 2=Quote Mode, 3=Snap Quote, 4=Full mode
            callback (callable): Optional callback function to call on data updates
        """
        try:
            if not self.connected:
                logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", f"Cannot subscribe to {symbol}: WebSocket not connected", level="warning")
                return False
                
            if symbol not in self.symbol_token_map:
                logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", f"Symbol {symbol} not registered. Call register_symbol() first.", level="error")
                return False
                
            exchange_type = self.symbol_token_map[symbol]['exchange_type']
            token = self.symbol_token_map[symbol]['token']
            
            # Validate mode - Angel One only supports modes 1-4
            if mode not in [1, 2, 3, 4]:
                logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", f"Invalid mode {mode} for {symbol}. Use 1, 2, 3, or 4.", level="error")
                return False
                
            with self.data_lock:
                # Create or update subscription
                if symbol in self.subscribed_symbols:
                    # Already subscribed, update mode and add callback if needed
                    self.subscribed_symbols[symbol]['mode'] = mode
                    if callback and callback not in self.subscribed_symbols[symbol]['callbacks']:
                        self.subscribed_symbols[symbol]['callbacks'].append(callback)
                else:
                    # Create new subscription
                    self.subscribed_symbols[symbol] = {
                        'exchange_type': exchange_type,
                        'token': token,
                        'mode': mode,
                        'callbacks': [callback] if callback else [],
                        'data': []
                    }
                    
            # Subscribe to the token with the specified mode
            token_list = [
                {
                    "exchangeType": int(exchange_type),
                    "tokens": [token]
                }
            ]
            
            # Create a unique correlation ID for this subscription
            correlation_id = f"subscribe_{symbol}_mode{mode}_{int(time.time())}"
            
            try:
                self.ws.subscribe(correlation_id, mode, token_list)  
                logger.log_websocket_event("SUBSCRIBE_MODE", f"Subscribed to symbol: {symbol} ({exchange_type}:{token}) in mode {mode}")
                return True
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", f"Error subscribing to {symbol} in mode {mode}: {str(e)}", level="error")
                return False
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", f"Error in subscribe_mode for {symbol}: {str(e)}", level="error")
            logger.log_websocket_event("SUBSCRIBE_MODE_ERROR", traceback.format_exc(), level="error")
            return False
    
    def batch_subscribe(self, symbols, mode=2, callback=None):
        """
        Subscribe to multiple symbols at once for better performance
        
        Args:
            symbols (list): List of symbols to subscribe to
            mode (int): Subscription mode: 1=LTP, 2=Quote Mode, 3=Snap Quote, 4=Full mode
            callback (callable): Optional callback function for all symbols
        
        Returns:
            dict: Dictionary with subscription results for each symbol
        """
        try:
            if not self.connected:
                logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", "Cannot subscribe: WebSocket not connected", level="warning")
                return {symbol: False for symbol in symbols}
            
            # Validate mode
            if mode not in [1, 2, 3, 4]:
                logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", f"Invalid mode {mode}. Use 1, 2, 3, or 4.", level="error")
                return {symbol: False for symbol in symbols}
            
            # Group tokens by exchange for efficient subscription
            exchange_tokens = {}
            valid_symbols = []
            
            for symbol in symbols:
                if symbol not in self.symbol_token_map:
                    logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", f"Symbol {symbol} not registered. Call register_symbol() first.", level="warning")
                    continue
                    
                exchange_type = self.symbol_token_map[symbol]['exchange_type']
                token = self.symbol_token_map[symbol]['token']
                
                if exchange_type not in exchange_tokens:
                    exchange_tokens[exchange_type] = []
                    
                exchange_tokens[exchange_type].append(token)
                valid_symbols.append(symbol)
            
            # Create subscriptions in our tracking dictionary
            with self.data_lock:
                for symbol in valid_symbols:
                    if symbol in self.subscribed_symbols:
                        # Already subscribed, just add callback
                        if callback and callback not in self.subscribed_symbols[symbol]['callbacks']:
                            self.subscribed_symbols[symbol]['callbacks'].append(callback)
                    else:
                        # Create new subscription
                        self.subscribed_symbols[symbol] = {
                            'exchange_type': self.symbol_token_map[symbol]['exchange_type'],
                            'token': self.symbol_token_map[symbol]['token'],
                            'mode': mode,
                            'callbacks': [callback] if callback else [],
                            'data': []
                        }
            
            # Create subscription request for Angel One API
            token_list = [
                {
                    "exchangeType": int(exchange_type),
                    "tokens": tokens
                }
                for exchange_type, tokens in exchange_tokens.items()
            ]
            
            if not token_list:
                logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", "No valid symbols to subscribe", level="warning")
                return {symbol: False for symbol in symbols}
            
            # Create a correlation ID for this batch
            correlation_id = f"batch_subscribe_{int(time.time())}"
            
            try:
                self.ws.subscribe(correlation_id, mode, token_list)
                logger.log_websocket_event("BATCH_SUBSCRIBE", f"Subscribed to {len(valid_symbols)} symbols in mode {mode}")
                
                # Create result dictionary
                result = {}
                for symbol in symbols:
                    result[symbol] = symbol in valid_symbols
                    
                return result
            except Exception as e:
                self.last_error = str(e)
                self.error_count += 1
                logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", f"Error in batch subscribe: {str(e)}", level="error")
                
                # Clean up any added subscriptions on failure
                with self.data_lock:
                    for symbol in valid_symbols:
                        if symbol in self.subscribed_symbols and symbol not in list(self.subscribed_symbols.keys()):
                            del self.subscribed_symbols[symbol]
                            
                return {symbol: False for symbol in symbols}
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", f"Error in batch_subscribe: {str(e)}", level="error")
            logger.log_websocket_event("BATCH_SUBSCRIBE_ERROR", traceback.format_exc(), level="error")
            return {symbol: False for symbol in symbols}
    
    def unsubscribe(self, symbol, callback=None):
        """Unsubscribe from a symbol or just remove a specific callback"""
        try:
            if symbol not in self.subscribed_symbols:
                return True  # Already not subscribed
                
            with self.data_lock:
                # If callback specified, only remove that callback
                if callback and callback in self.subscribed_symbols[symbol]['callbacks']:
                    self.subscribed_symbols[symbol]['callbacks'].remove(callback)
                    logger.log_websocket_event("UNSUBSCRIBE", f"Removed callback for symbol: {symbol}")
                    
                    # If callbacks still exist, don't unsubscribe from the feed
                    if self.subscribed_symbols[symbol]['callbacks']:
                        return True
                
                # Either no callback specified or no callbacks left, unsubscribe completely
                exchange_type = self.subscribed_symbols[symbol]['exchange_type']
                token = self.subscribed_symbols[symbol]['token']
                
            # Only unsubscribe from WebSocket if we're connected
            if self.connected:
                # Format for Angel One API unsubscribe
                token_list = [
                    {
                        "exchangeType": int(exchange_type),
                        "tokens": [token]
                    }
                ]
                
                correlation_id = f"unsubscribe_{symbol}_{int(time.time())}"
                try:
                    self.ws.unsubscribe(correlation_id, token_list)  # Updated to match API specs
                    logger.log_websocket_event("UNSUBSCRIBE", f"Unsubscribed from symbol: {symbol} ({exchange_type}:{token})")
                except Exception as e:
                    self.last_error = str(e)
                    self.error_count += 1
                    logger.log_websocket_event("UNSUBSCRIBE_ERROR", f"Error unsubscribing from {symbol}: {str(e)}", level="error")
            
            # Remove from our tracking regardless of WebSocket unsubscribe success
            with self.data_lock:
                if symbol in self.subscribed_symbols:
                    del self.subscribed_symbols[symbol]
                    
            return True
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.log_websocket_event("UNSUBSCRIBE_ERROR", f"Error in unsubscribe for {symbol}: {str(e)}", level="error")
            logger.log_websocket_event("UNSUBSCRIBE_ERROR", traceback.format_exc(), level="error")
            return False
    
    def get_data_as_dataframe(self, symbol, limit=100):
        """Get buffered data as pandas DataFrame"""
        try:
            with self.data_lock:
                if symbol in self.subscribed_symbols and self.subscribed_symbols[symbol]['data']:
                    # Get last 'limit' data points
                    data_points = self.subscribed_symbols[symbol]['data'][-limit:]
                    df = pd.DataFrame(data_points)
                    if not df.empty:
                        df.set_index('timestamp', inplace=True)
                    return df
            return pd.DataFrame()
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("DATA_ERROR", f"Error getting dataframe for {symbol}: {str(e)}", level="error")
            return pd.DataFrame()
    
    def is_symbol_subscribed(self, symbol):
        """Check if a symbol is currently subscribed"""
        return symbol in self.subscribed_symbols
    
    def get_connection_status(self):
        """Get detailed connection status"""
        return {
            'connected': self.connected,
            'reconnect_attempts': self.reconnect_attempts,
            'last_error': self.last_error,
            'error_count': self.error_count,
            'last_data_time': self.last_data_time,
            'subscribed_symbols_count': len(self.subscribed_symbols)
        }
    
    def close_connection(self):
        """Close WebSocket connection"""
        try:
            # Stop health check thread
            self.health_check_running = False
            
            # Close WebSocket connection
            if self.ws and self.connected:
                self.ws.close_connection()
                self.connected = False
                logger.log_websocket_event("CLOSE", "WebSocket connection closed")
                return True
            return False
        except Exception as e:
            self.last_error = str(e)
            logger.log_websocket_event("CLOSE_ERROR", f"Error closing WebSocket connection: {str(e)}", level="error")
            return False

# Singleton instance
websocket_manager = AngelOneWebSocketManager()

def initialize_angelone_websocket(user):
    """
    Initialize the AngelOne WebSocket connection with user credentials
    
    Args:
        user: User model instance with AngelOne credentials
        
    Returns:
        dict: Status information about the connection
    """
    try:
        if not user.angelone_api_key or not user.angelone_client_code or not user.angelone_jwt_token or not user.angelone_feed_token:
            logger.log_websocket_event("INIT_ERROR", "Missing AngelOne credentials", level="error")
            return {
                "success": False, 
                "message": "Missing AngelOne credentials. Please update your settings."
            }
            
        # Get the singleton instance
        ws_manager = websocket_manager
        
        # Configure with user credentials
        config_success = ws_manager.configure(
            auth_token=user.angelone_jwt_token,
            api_key=user.angelone_api_key, 
            client_code=user.angelone_client_code,
            feed_token=user.angelone_feed_token
        )
        
        if not config_success:
            logger.log_websocket_event("CONFIG_ERROR", "Failed to configure AngelOne WebSocket", level="error")
            return {
                "success": False,
                "message": f"WebSocket configuration failed: {ws_manager.last_error}"
            }
            
        # Connect to WebSocket
        connect_success = ws_manager.connect()
        
        if not connect_success:
            logger.log_websocket_event("CONNECT_ERROR", "Failed to connect to AngelOne WebSocket", level="error")
            return {
                "success": False,
                "message": f"WebSocket connection failed: {ws_manager.last_error}"
            }
            
        # Mark user as WebSocket configured
        user.angelone_ws_configured = True
        if connect_success:
            user.angelone_ws_enabled = True
            
        logger.log_websocket_event("INIT_SUCCESS", f"WebSocket initialized for user {user.username}")
        return {
            "success": True,
            "message": "WebSocket connection established successfully",
            "status": ws_manager.get_connection_status()
        }
        
    except Exception as e:
        logger.log_websocket_event("INIT_ERROR", f"Error initializing WebSocket: {str(e)}", level="error")
        return {
            "success": False,
            "message": f"WebSocket initialization error: {str(e)}"
        }