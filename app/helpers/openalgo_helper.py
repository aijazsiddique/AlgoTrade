from openalgo import api, Strategy
import uuid
import json

def get_openalgo_client(user):
    """
    Create and return an OpenAlgo API client for the given user
    """
    if not user.openalgo_api_key:
        raise ValueError("OpenAlgo API key not configured")
    
    return api(
        api_key=user.openalgo_api_key,
        host=user.openalgo_host_url or "http://127.0.0.1:5000"
    )

def register_webhook(client, strategy_name):
    """
    Register a new webhook with OpenAlgo
    Returns the webhook ID if successful, None otherwise
    """
    try:
        # Generate a unique webhook ID
        webhook_id = f"{strategy_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        
        # TODO: In a production system, you'd need to implement the actual webhook registration
        # For now, we'll simulate it by returning the webhook ID
        return webhook_id
        
    except Exception as e:
        print(f"Error registering webhook: {str(e)}")
        return None

def send_strategy_signal(user, webhook_id, symbol, action, position_size=1):
    """
    Send a signal to OpenAlgo via the Strategy API
    """
    try:
        strategy_client = Strategy(
            host_url=user.openalgo_host_url or "http://127.0.0.1:5000",
            webhook_id=webhook_id
        )
        
        response = strategy_client.strategyorder(symbol, action, position_size)
        return response
        
    except Exception as e:
        print(f"Error sending strategy signal: {str(e)}")
        return {"status": "error", "message": str(e)}

def format_order_params(instance, signal_type):
    """
    Format order parameters based on the strategy instance and signal type
    Returns a dictionary with the order parameters
    
    signal_type can be: 'long_entry', 'long_exit', 'short_entry', 'short_exit'
    """
    # Get the action configuration from the instance
    action_config = getattr(instance, f"{signal_type}_action", None)
    
    if not action_config:
        return None
    
    try:
        # Try to parse as JSON first (for complex configurations)
        return json.loads(action_config)
    except:
        # If it's not JSON, just return the string as is
        return action_config
