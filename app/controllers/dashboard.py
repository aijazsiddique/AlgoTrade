from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance
from app import db
from app.helpers.openalgo_helper import get_openalgo_client

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    strategies = Strategy.query.filter_by(user_id=current_user.id).all()
    active_instances = StrategyInstance.query.join(Strategy).filter(
        Strategy.user_id == current_user.id,
        StrategyInstance.is_active == True
    ).count()
    
    # Get account information if API key is available
    account_info = None
    if current_user.openalgo_api_key:
        try:
            client = get_openalgo_client(current_user)
            funds = client.funds()
            positions = client.positionbook()
            orders = client.orderbook()
            
            account_info = {
                'funds': funds.get('data', {}),
                'positions_count': len(positions.get('data', [])),
                'orders_count': len(orders.get('data', []))
            }
        except Exception as e:
            flash(f"Could not fetch account information: {str(e)}", "warning")
    
    return render_template(
        'dashboard/index.html',
        title='Dashboard',
        strategies_count=len(strategies),
        active_instances=active_instances,
        account_info=account_info
    )

@dashboard_bp.route('/dashboard/positions')
@login_required
def positions():
    if not current_user.openalgo_api_key:
        flash("Please set up your OpenAlgo API key in your profile.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        client = get_openalgo_client(current_user)
        positions_response = client.positionbook()
        
        # Check if the response is valid and has the expected structure
        if not isinstance(positions_response, dict) or 'data' not in positions_response:
            flash("Invalid response format from OpenAlgo API", "danger")
            return redirect(url_for('dashboard.index'))
            
        positions_data = positions_response.get('data', [])
        
        # Process positions to ensure they have the required attributes
        processed_positions = []
        for position in positions_data:
            # If position is a string, convert it to a dictionary with default values
            if isinstance(position, str):
                processed_positions.append({
                    'symbol': position,
                    'exchange': 'N/A',
                    'product': 'N/A',
                    'netqty': 0,
                    'avgprice': 0,
                    'ltp': 0,
                    'pnl': 0
                })
            else:
                # Ensure position has all required attributes
                if not isinstance(position, dict):
                    position = {}  # Convert to dictionary if not already
                
                processed_position = {
                    'symbol': position.get('symbol', 'N/A'),
                    'exchange': position.get('exchange', 'N/A'),
                    'product': position.get('product', 'N/A'),
                    'netqty': position.get('netqty', 0),
                    'avgprice': position.get('avgprice', 0),
                    'ltp': position.get('ltp', 0),
                    'pnl': position.get('pnl', 0)
                }
                processed_positions.append(processed_position)
        
        return render_template(
            'dashboard/positions.html',
            title='Positions',
            positions=processed_positions
        )
    except Exception as e:
        flash(f"Could not fetch positions: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard/orders')
@login_required
def orders():
    if not current_user.openalgo_api_key:
        flash("Please set up your OpenAlgo API key in your profile.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        client = get_openalgo_client(current_user)
        orders_response = client.orderbook()
        
        # Check if the response is valid and has the expected structure
        if not isinstance(orders_response, dict) or 'data' not in orders_response:
            flash("Invalid response format from OpenAlgo API", "danger")
            return redirect(url_for('dashboard.index'))
            
        orders_data = orders_response.get('data', [])
        
        # Process orders to ensure they have the required attributes
        processed_orders = []
        for order in orders_data:
            # If order is a string, convert it to a dictionary with default values
            if isinstance(order, str):
                # Try to handle it as order ID
                processed_orders.append({
                    'orderid': order,
                    'symbol': 'N/A',
                    'pricetype': 'N/A',
                    'action': 'N/A',
                    'quantity': 0,
                    'price': 0,
                    'status': 'UNKNOWN',
                    'updatetime': 'N/A'
                })
            else:
                # Ensure order has all required attributes
                if not isinstance(order, dict):
                    order = {}  # Convert to dictionary if not already
                
                processed_order = {
                    'orderid': order.get('orderid', 'N/A'),
                    'symbol': order.get('symbol', 'N/A'),
                    'pricetype': order.get('pricetype', 'N/A'),
                    'action': order.get('action', 'N/A'),
                    'quantity': order.get('quantity', 0),
                    'price': order.get('price', 0),
                    'status': order.get('status', 'UNKNOWN'),
                    'updatetime': order.get('updatetime', 'N/A')
                }
                processed_orders.append(processed_order)
        
        return render_template(
            'dashboard/orders.html',
            title='Orders',
            orders=processed_orders
        )
    except Exception as e:
        flash(f"Could not fetch orders: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard/trades')
@login_required
def trades():
    if not current_user.openalgo_api_key:
        flash("Please set up your OpenAlgo API key in your profile.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        client = get_openalgo_client(current_user)
        trades_response = client.tradebook()
        
        # Check if the response is valid and has the expected structure
        if not isinstance(trades_response, dict) or 'data' not in trades_response:
            flash("Invalid response format from OpenAlgo API", "danger")
            return redirect(url_for('dashboard.index'))
            
        trades_data = trades_response.get('data', [])
        
        # Process trades to ensure they have the required attributes
        processed_trades = []
        for trade in trades_data:
            # If trade is a string, convert it to a dictionary with default values
            if isinstance(trade, str):
                processed_trades.append({
                    'tradeid': trade,
                    'orderid': 'N/A',
                    'symbol': 'N/A',
                    'exchange': 'N/A',
                    'action': 'N/A',
                    'quantity': 0,
                    'price': 0,
                    'tradetime': 'N/A'
                })
            else:
                # Ensure trade has all required attributes
                if not isinstance(trade, dict):
                    trade = {}  # Convert to dictionary if not already
                
                processed_trade = {
                    'tradeid': trade.get('tradeid', 'N/A'),
                    'orderid': trade.get('orderid', 'N/A'),
                    'symbol': trade.get('symbol', 'N/A'),
                    'exchange': trade.get('exchange', 'N/A'),
                    'action': trade.get('action', 'N/A'),
                    'quantity': trade.get('quantity', 0),
                    'price': trade.get('price', 0),
                    'tradetime': trade.get('tradetime', 'N/A')
                }
                processed_trades.append(processed_trade)
        
        return render_template(
            'dashboard/trades.html',
            title='Trades',
            trades=processed_trades
        )
    except Exception as e:
        flash(f"Could not fetch trades: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard/holdings')
@login_required
def holdings():
    if not current_user.openalgo_api_key:
        flash("Please set up your OpenAlgo API key in your profile.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        client = get_openalgo_client(current_user)
        holdings_response = client.holdings()
        
        # Check if the response is valid and has the expected structure
        if not isinstance(holdings_response, dict) or 'data' not in holdings_response:
            flash("Invalid response format from OpenAlgo API", "danger")
            return redirect(url_for('dashboard.index'))
            
        holdings_data = holdings_response.get('data', [])
        
        # Process holdings to ensure they have the required attributes
        processed_holdings = []
        for holding in holdings_data:
            # If holding is a string, convert it to a dictionary with default values
            if isinstance(holding, str):
                processed_holdings.append({
                    'symbol': holding,
                    'exchange': 'N/A',
                    'isin': 'N/A',
                    'quantity': 0,
                    'averageprice': 0,
                    'ltp': 0,
                    'currentvalue': 0
                })
            else:
                # Ensure holding has all required attributes
                if not isinstance(holding, dict):
                    holding = {}  # Convert to dictionary if not already
                
                processed_holding = {
                    'symbol': holding.get('symbol', 'N/A'),
                    'exchange': holding.get('exchange', 'N/A'),
                    'isin': holding.get('isin', 'N/A'),
                    'quantity': holding.get('quantity', 0),
                    'averageprice': holding.get('averageprice', 0),
                    'ltp': holding.get('ltp', 0),
                    'currentvalue': holding.get('currentvalue', 0)
                }
                processed_holdings.append(processed_holding)
        
        return render_template(
            'dashboard/holdings.html',
            title='Holdings',
            holdings=processed_holdings
        )
    except Exception as e:
        flash(f"Could not fetch holdings: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))
