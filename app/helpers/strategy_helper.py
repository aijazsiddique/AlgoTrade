import pandas as pd
import numpy as np
import json
from io import StringIO
import traceback
import ast
import importlib
import contextlib
import sys
from app.helpers.openalgo_helper import get_openalgo_client

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

def execute_strategy_code(code, historical_data=None, params=None):
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
        
        # Return success with signals
        return {
            'success': True,
            'signals': signals,
            'output': stdout_capture.getvalue()
        }
    
    except Exception as e:
        # Return failure with error message
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }

def get_historical_data(user, symbol, exchange, timeframe, start_date=None, end_date=None):
    """
    Fetch historical data from OpenAlgo
    Returns a pandas DataFrame with OHLC data
    """
    client = get_openalgo_client(user)
    
    # Get historical data
    result = client.history(
        symbol=symbol,
        exchange=exchange,
        interval=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    # The result should already be a pandas DataFrame based on OpenAlgo implementation
    return result

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
