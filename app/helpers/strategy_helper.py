import pandas as pd
import numpy as np
import json
from io import StringIO
import traceback
import ast
import importlib
import contextlib
import sys
import time
import threading
from datetime import datetime, timedelta
from app.helpers.openalgo_helper import get_openalgo_client
from app.helpers.websocket_helper import websocket_manager
from app.helpers.logger_helper import logger

# Store active strategies for real-time processing
active_strategies = {}  

def extract_params_from_code(code):
    """
    Extract parameter definitions from strategy code
    Returns a list of parameter names and default values
    """
    params = {}
    try:
        # Parse the code as an AST
        tree = ast.parse(code)
        
        # Look for variable assignments at the module level
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                # Check for comment before assignment with "# param:"
                if hasattr(node, 'lineno') and node.lineno > 1:
                    prev_line = code.splitlines()[node.lineno - 2]
                    if "# param:" in prev_line:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                if isinstance(node.value, (ast.Num, ast.Str, ast.NameConstant)):
                                    # Get parameter name
                                    param_name = target.id
                                    
                                    # Get parameter value
                                    if isinstance(node.value, ast.Num):
                                        param_value = node.value.n
                                    elif isinstance(node.value, ast.Str):
                                        param_value = node.value.s
                                    elif isinstance(node.value, ast.NameConstant):
                                        param_value = node.value.value
                                    
                                    # Add to params dict
                                    params[param_name] = param_value
    except:
        # If there's an error, just return an empty dict
        pass
    
    return params

def execute_strategy_code(code, historical_data=None, params=None, strategy_name=None, instance_name=None):
    """
    Execute the strategy code and capture signals
    Returns a dict with success flag, signals, and possibly error message
    """
    # Create a StringIO to capture stdout
    stdout_capture = StringIO()
    signals = []
    local_vars = {
        'np': np,
        'pd': pd,
        'signals': signals,
        'historical_data': historical_data
    }
    
    # Add custom parameters if provided
    if params:
        local_vars.update(params)
    
    try:
        # Add signal functions to the local variables
        local_vars['long_entry'] = lambda: signals.append(('long_entry', len(signals) + 1))
        local_vars['long_exit'] = lambda: signals.append(('long_exit', len(signals) + 1))
        local_vars['short_entry'] = lambda: signals.append(('short_entry', len(signals) + 1))
        local_vars['short_exit'] = lambda: signals.append(('short_exit', len(signals) + 1))
        
        # Redirect stdout to our capture
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, {}, local_vars)
        
        # Log signal generation if strategy and instance names are provided
        if strategy_name and instance_name and signals:
            symbol = params.get('symbol', 'unknown') if params else 'unknown'
            for signal_type, signal_id in signals:
                logger.log_signal(
                    strategy_name, 
                    instance_name, 
                    symbol, 
                    signal_type,
                    f"Signal ID: {signal_id}"
                )
        
        # Return success with signals
        return {
            'success': True,
            'signals': signals,
            'output': stdout_capture.getvalue()
        }
    
    except Exception as e:
        # Log execution error
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        if strategy_name and instance_name:
            logger.log_strategy_event(
                strategy_name,
                instance_name,
                "EXECUTION_ERROR",
                error_msg,
                "error"
            )
        
        # Return failure with error message
        return {
            'success': False,
            'error': error_msg,
            'traceback': error_trace
        }

def get_historical_data(user, symbol, exchange, timeframe, start_date=None, end_date=None):
    """
    Fetch historical data from OpenAlgo
    Returns a pandas DataFrame with OHLC data
    """
    try:
        client = get_openalgo_client(user)
        
        # Log data request
        logger.log_strategy_event(
            "DataFetch", 
            f"{symbol}@{exchange}", 
            "HISTORICAL_DATA_REQUEST", 
            f"Timeframe: {timeframe}, Start: {start_date}, End: {end_date}"
        )
        
        # Get historical data
        result = client.history(
            symbol=symbol,
            exchange=exchange,
            interval=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        # Log result summary
        data_points = len(result) if isinstance(result, pd.DataFrame) else 0
        logger.log_strategy_event(
            "DataFetch", 
            f"{symbol}@{exchange}", 
            "HISTORICAL_DATA_RECEIVED", 
            f"Received {data_points} data points"
        )
        
        # The result should already be a pandas DataFrame based on OpenAlgo implementation
        return result
    except Exception as e:
        # Log error
        logger.log_strategy_event(
            "DataFetch", 
            f"{symbol}@{exchange}", 
            "HISTORICAL_DATA_ERROR", 
            str(e),
            "error"
        )
        # Reraise the exception
        raise

def backtest_strategy(strategy_code, historical_data, params=None):
    """
    Run a backtest of the strategy on historical data
    Returns a dict with performance metrics and trade list
    """
    # Execute the strategy code
    result = execute_strategy_code(strategy_code, historical_data, params)
    
    if not result['success']:
        return result
    
    # Process the signals into trades
    signals = result['signals']
    trades = []
    
    # TODO: Implement backtest logic
    
    return {
        'success': True,
        'trades': trades,
        'metrics': {
            'total_trades': len(trades),
            'win_rate': 0,
            'profit_factor': 0,
            'max_drawdown': 0
        }
    }

def get_realtime_data(symbol, limit=100):
    """
    Get real-time data for a symbol from the WebSocket connection
    Returns a pandas DataFrame with OHLC data
    """
    return websocket_manager.get_data_as_dataframe(symbol, limit)

def is_symbol_subscribed(symbol):
    """
    Check if a symbol is already subscribed to in the WebSocket
    """
    return websocket_manager.is_symbol_subscribed(symbol)

def subscribe_symbol(symbol, exchange_type, token, callback=None):
    """
    Subscribe to a symbol's real-time data
    """
    # First register the symbol if not already registered
    if symbol not in websocket_manager.symbol_token_map:
        websocket_manager.register_symbol(symbol, exchange_type, token)
    
    # Then subscribe to the symbol
    return websocket_manager.subscribe(symbol, callback)

def process_realtime_data(user_id, instance_id, symbol, exchange_type, token, strategy_code, params=None):
    """
    Process real-time data for a strategy instance
    This runs in a background thread
    """
    from app.models.instance import StrategyInstance
    from app.models.user import User
    from app import db
    
    # Load user and instance objects
    user = User.query.get(user_id)
    instance = StrategyInstance.query.get(instance_id)
    
    if not user or not instance:
        logger.log_strategy_event(
            "Unknown", 
            f"ID: {instance_id}", 
            "INITIALIZATION_ERROR", 
            f"User ID: {user_id}, Instance ID: {instance_id} - Could not load User or Instance",
            "error"
        )
        return
    
    # Log strategy start
    strategy_name = instance.strategy.name
    instance_name = instance.name
    
    logger.log_strategy_event(
        strategy_name, 
        instance_name, 
        "STARTED", 
        f"Processing real-time data for {symbol} (User: {user.username})"
    )
    
    # Initialize variables
    use_websocket = True
    position = 0
    last_signal_time = None
    signals = []
    
    # Try to get real-time data via WebSocket
    if not is_symbol_subscribed(symbol):
        try:
            # Try to subscribe to the symbol
            success = subscribe_symbol(symbol, exchange_type, token)
            use_websocket = success
            if success:
                logger.log_strategy_event(
                    strategy_name, 
                    instance_name, 
                    "WEBSOCKET_SUBSCRIBE", 
                    f"Successfully subscribed to {symbol} via WebSocket"
                )
            else:
                logger.log_strategy_event(
                    strategy_name, 
                    instance_name, 
                    "WEBSOCKET_SUBSCRIBE_FAILED", 
                    f"Failed to subscribe to {symbol} via WebSocket, falling back to OpenAlgo",
                    "warning"
                )
                use_websocket = False
        except Exception as e:
            logger.log_strategy_event(
                strategy_name, 
                instance_name, 
                "WEBSOCKET_SUBSCRIBE_ERROR", 
                f"Error subscribing to {symbol}: {str(e)}",
                "error"
            )
            use_websocket = False
    
    # Get initial historical data for context
    initial_data = None
    
    # Try WebSocket first
    if use_websocket:
        initial_data = get_realtime_data(symbol)
    
    # Fall back to OpenAlgo if WebSocket data is empty
    if initial_data is None or initial_data.empty:
        try:
            logger.log_strategy_event(
                strategy_name, 
                instance_name, 
                "INITIAL_DATA", 
                f"Getting initial data from OpenAlgo API for {symbol}"
            )
            
            initial_data = get_historical_data(
                user, 
                symbol, 
                instance.exchange,
                instance.timeframe,
                start_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d")
            )
        except Exception as e:
            logger.log_strategy_event(
                strategy_name, 
                instance_name, 
                "INITIAL_DATA_ERROR", 
                f"Error getting initial data: {str(e)}",
                "error"
            )
    
    current_data = initial_data.copy() if not initial_data is None and not initial_data.empty else pd.DataFrame()
    
    # Log data status
    if current_data.empty:
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "NO_DATA", 
            "No initial data available. Will wait for data.",
            "warning"
        )
    else:
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "DATA_READY", 
            f"Initial data loaded with {len(current_data)} data points"
        )
    
    # Main processing loop
    while instance_id in active_strategies:
        try:
            new_data = None
            
            # Try WebSocket first if available
            if use_websocket:
                new_data = get_realtime_data(symbol)
                
                # If we got data from WebSocket, append/merge with current data
                if not new_data.empty:
                    if current_data.empty:
                        current_data = new_data
                        logger.log_strategy_event(
                            strategy_name, 
                            instance_name, 
                            "DATA_UPDATE", 
                            f"Received initial WebSocket data with {len(new_data)} points"
                        )
                    else:
                        # Append new data and remove duplicates
                        current_data = pd.concat([current_data, new_data])
                        current_data = current_data[~current_data.index.duplicated(keep='last')]
                        
                        # Sort by timestamp
                        current_data.sort_index(inplace=True)
                        
                        logger.log_strategy_event(
                            strategy_name, 
                            instance_name, 
                            "DATA_UPDATE", 
                            f"Updated data from WebSocket, now have {len(current_data)} points"
                        )
            
            # Fall back to OpenAlgo if WebSocket failed or had no data
            if new_data is None or new_data.empty:
                try:
                    # Fall back to OpenAlgo for data
                    end_date = datetime.now().strftime("%Y-%m-%d")
                    start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    logger.log_strategy_event(
                        strategy_name, 
                        instance_name, 
                        "FALLBACK_DATA", 
                        f"Falling back to OpenAlgo API for {symbol} data"
                    )
                    
                    new_data = get_historical_data(
                        user, 
                        symbol, 
                        instance.exchange, 
                        instance.timeframe,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if not new_data.empty:
                        current_data = new_data
                        logger.log_strategy_event(
                            strategy_name, 
                            instance_name, 
                            "DATA_UPDATE", 
                            f"Updated data from OpenAlgo API, now have {len(current_data)} points"
                        )
                except Exception as e:
                    logger.log_strategy_event(
                        strategy_name, 
                        instance_name, 
                        "FALLBACK_DATA_ERROR", 
                        f"Error fetching fallback data: {str(e)}",
                        "error"
                    )
            
            # If we have data, execute the strategy
            if not current_data.empty:
                # Create a custom params dict
                strategy_params = params.copy() if params else {}
                strategy_params['historical_data'] = current_data
                strategy_params['symbol'] = symbol
                
                # Execute strategy code
                result = execute_strategy_code(
                    strategy_code, 
                    current_data, 
                    strategy_params,
                    strategy_name,
                    instance_name
                )
                
                if result['success'] and result['signals']:
                    # Process new signals
                    new_signals = result['signals']
                    current_time = datetime.now()
                    
                    # Avoid duplicate signals - only process if we have new ones
                    if len(new_signals) > len(signals):
                        latest_signals = new_signals[len(signals):]
                        signals = new_signals
                        
                        logger.log_strategy_event(
                            strategy_name, 
                            instance_name, 
                            "SIGNALS_DETECTED", 
                            f"Detected {len(latest_signals)} new signals"
                        )
                        
                        for signal_type, signal_id in latest_signals:
                            # Skip if we've sent a signal recently (avoid duplicates)
                            if last_signal_time and (current_time - last_signal_time).total_seconds() < 60:
                                logger.log_strategy_event(
                                    strategy_name, 
                                    instance_name, 
                                    "SIGNAL_SKIPPED", 
                                    f"Signal {signal_type} skipped - too soon after last signal",
                                    "warning"
                                )
                                continue
                                
                            # Handle position tracking and signal sending
                            if signal_type == 'long_entry' and position <= 0:
                                position = 1
                                # Send signal to broker
                                from app.helpers.openalgo_helper import send_strategy_signal
                                logger.log_strategy_event(
                                    strategy_name, 
                                    instance_name, 
                                    "SIGNAL_SENDING", 
                                    f"Sending LONG_ENTRY for {symbol} with action {instance.long_entry_action}"
                                )
                                
                                response = send_strategy_signal(
                                    user,
                                    instance.webhook_id,
                                    symbol,
                                    instance.long_entry_action,
                                    instance.position_size
                                )
                                
                                # Log trade execution
                                logger.log_trade(
                                    instance.webhook_id,
                                    symbol,
                                    instance.long_entry_action,
                                    instance.position_size,
                                    str(response)
                                )
                                
                                last_signal_time = current_time
                                
                            elif signal_type == 'long_exit' and position > 0:
                                position = 0
                                # Send signal to broker
                                from app.helpers.openalgo_helper import send_strategy_signal
                                logger.log_strategy_event(
                                    strategy_name, 
                                    instance_name, 
                                    "SIGNAL_SENDING", 
                                    f"Sending LONG_EXIT for {symbol} with action {instance.long_exit_action}"
                                )
                                
                                response = send_strategy_signal(
                                    user,
                                    instance.webhook_id,
                                    symbol,
                                    instance.long_exit_action,
                                    instance.position_size
                                )
                                
                                # Log trade execution
                                logger.log_trade(
                                    instance.webhook_id,
                                    symbol,
                                    instance.long_exit_action,
                                    instance.position_size,
                                    str(response)
                                )
                                
                                last_signal_time = current_time
                                
                            elif signal_type == 'short_entry' and position >= 0:
                                position = -1
                                # Send signal to broker
                                from app.helpers.openalgo_helper import send_strategy_signal
                                logger.log_strategy_event(
                                    strategy_name, 
                                    instance_name, 
                                    "SIGNAL_SENDING", 
                                    f"Sending SHORT_ENTRY for {symbol} with action {instance.short_entry_action}"
                                )
                                
                                response = send_strategy_signal(
                                    user,
                                    instance.webhook_id,
                                    symbol,
                                    instance.short_entry_action,
                                    instance.position_size
                                )
                                
                                # Log trade execution
                                logger.log_trade(
                                    instance.webhook_id,
                                    symbol,
                                    instance.short_entry_action,
                                    instance.position_size,
                                    str(response)
                                )
                                
                                last_signal_time = current_time
                                
                            elif signal_type == 'short_exit' and position < 0:
                                position = 0
                                # Send signal to broker
                                from app.helpers.openalgo_helper import send_strategy_signal
                                logger.log_strategy_event(
                                    strategy_name, 
                                    instance_name, 
                                    "SIGNAL_SENDING", 
                                    f"Sending SHORT_EXIT for {symbol} with action {instance.short_exit_action}"
                                )
                                
                                response = send_strategy_signal(
                                    user,
                                    instance.webhook_id,
                                    symbol,
                                    instance.short_exit_action,
                                    instance.position_size
                                )
                                
                                # Log trade execution
                                logger.log_trade(
                                    instance.webhook_id,
                                    symbol,
                                    instance.short_exit_action,
                                    instance.position_size,
                                    str(response)
                                )
                                
                                last_signal_time = current_time
            
            # Sleep before next cycle (10 seconds)
            time.sleep(10)
            
        except Exception as e:
            logger.log_strategy_event(
                strategy_name, 
                instance_name, 
                "PROCESSING_ERROR", 
                f"Error in real-time processing: {str(e)}",
                "error"
            )
            logger.log_strategy_event(
                strategy_name, 
                instance_name, 
                "TRACEBACK", 
                traceback.format_exc(),
                "error"
            )
            time.sleep(30)  # Longer sleep on error
    
    # Log strategy stopped
    logger.log_strategy_event(
        strategy_name, 
        instance_name, 
        "STOPPED", 
        f"Strategy instance stopped processing"
    )

def activate_strategy_instance(user, instance):
    """
    Activate a strategy instance for real-time processing
    """
    instance_id = instance.id
    strategy_name = instance.strategy.name
    instance_name = instance.name
    
    # Check if already active
    if instance_id in active_strategies:
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "ACTIVATE", 
            "Strategy already active"
        )
        return {'success': True, 'message': 'Strategy already active'}
    
    try:
        # Load the strategy code
        strategy_code = instance.strategy.code
        
        # Get params directly, no need to parse JSON as SQLAlchemy does that automatically
        params = instance.parameters if instance.parameters else {}
        
        # Mark as active
        active_strategies[instance_id] = True
        
        # Get the symbol exchange mapping
        symbol_mapping = get_symbol_token_mapping(instance.symbol, instance.exchange)
        
        # Log activation
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "ACTIVATE", 
            f"Activating strategy for {instance.symbol} with {len(params)} parameters"
        )
        
        # Start processing thread
        thread = threading.Thread(
            target=process_realtime_data,
            args=(
                user.id, 
                instance.id, 
                instance.symbol, 
                symbol_mapping['exchange_type'], 
                symbol_mapping['token'], 
                strategy_code, 
                params
            ),
            name=f"Strategy-{instance_id}"
        )
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'message': 'Strategy activated successfully'}
        
    except Exception as e:
        if instance_id in active_strategies:
            del active_strategies[instance_id]
            
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "ACTIVATION_ERROR", 
            f"Error activating strategy: {str(e)}",
            "error"
        )
        return {'success': False, 'error': str(e)}

def deactivate_strategy_instance(instance_id):
    """
    Deactivate a strategy instance
    """
    from app.models.instance import StrategyInstance
    
    instance = StrategyInstance.query.get(instance_id)
    strategy_name = instance.strategy.name if instance else "Unknown"
    instance_name = instance.name if instance else f"ID: {instance_id}"
    
    if instance_id in active_strategies:
        del active_strategies[instance_id]
        logger.log_strategy_event(
            strategy_name, 
            instance_name, 
            "DEACTIVATE", 
            "Strategy deactivated successfully"
        )
        return {'success': True, 'message': 'Strategy deactivated successfully'}
        
    logger.log_strategy_event(
        strategy_name, 
        instance_name, 
        "DEACTIVATE_ERROR", 
        "Strategy not active",
        "warning"
    )
    return {'success': False, 'error': 'Strategy not active'}

def get_symbol_token_mapping(symbol, exchange):
    """
    Get the token and exchange type for a symbol
    This is a simplified example - in a production system,
    you would maintain a proper symbol database or API to get this mapping
    """
    # Simplified mapping for demonstration
    # In a real system, you would fetch this from a database or API
    mappings = {
        'NSE': {
            'RELIANCE': {'exchange_type': 1, 'token': '2885'},
            'SBIN': {'exchange_type': 1, 'token': '3045'},
            'TCS': {'exchange_type': 1, 'token': '11536'},
            'INFY': {'exchange_type': 1, 'token': '1594'},
            'HDFCBANK': {'exchange_type': 1, 'token': '1333'},
            'NIFTY': {'exchange_type': 1, 'token': '26000'},
            'BANKNIFTY': {'exchange_type': 1, 'token': '26009'}
        },
        'BSE': {
            'RELIANCE': {'exchange_type': 2, 'token': '500325'},
            'SBIN': {'exchange_type': 2, 'token': '500112'},
            'TCS': {'exchange_type': 2, 'token': '532540'},
            'INFY': {'exchange_type': 2, 'token': '500209'},
            'HDFCBANK': {'exchange_type': 2, 'token': '500180'}
        },
        'NFO': {
            'NIFTY-FUT': {'exchange_type': 3, 'token': '26000'},
            'BANKNIFTY-FUT': {'exchange_type': 3, 'token': '26009'}
        }
    }
    
    if exchange in mappings and symbol in mappings[exchange]:
        return mappings[exchange][symbol]
    
    # Log mapping not found
    logger.log_strategy_event(
        "SymbolMapper", 
        f"{symbol}@{exchange}", 
        "MAPPING_NOT_FOUND", 
        f"No mapping found for {symbol}@{exchange}, using default",
        "warning"
    )
    
    # Default mapping if not found
    return {'exchange_type': 1, 'token': '26000'}
