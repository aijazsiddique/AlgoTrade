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
            
            # Get funds data
            funds_response = client.funds()
            funds_data = funds_response.get('data', {}) if isinstance(funds_response, dict) else {}
            
            # Get positions data
            positions_response = client.positionbook()
            positions_data = positions_response.get('data', []) if isinstance(positions_response, dict) else []
            
            # Get orders data
            orders_response = client.orderbook()
            orders_data = orders_response.get('data', []) if isinstance(orders_response, dict) else []
            
            # Get holdings data
            holdings_response = client.holdings()
            holdings_data = holdings_response.get('data', []) if isinstance(holdings_response, dict) else []
            
            # Format account info according to API response structure
            account_info = {
                'funds': {
                    'availablecash': funds_data.get('availablecash', '0.00'),
                    'collateral': funds_data.get('collateral', '0.00'),
                    'm2mrealized': funds_data.get('m2mrealized', '0.00'),
                    'm2munrealized': funds_data.get('m2munrealized', '0.00'),
                    'utiliseddebits': funds_data.get('utiliseddebits', '0.00')
                },
                'positions_count': len(positions_data),
                'orders_count': len(orders_data),
                'holdings_count': len(holdings_data)
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
        
        # Calculate total P&L from positions
        total_pnl = sum(float(position.get('pnl', 0)) for position in positions_data 
                        if isinstance(position, dict))
        
        return render_template(
            'dashboard/positions.html',
            title='Positions',
            positions=positions_data,
            total_pnl=total_pnl
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
            
        # Extract the data and stats from the orderbook response
        orders_data = orders_response.get('data', [])
        order_stats = orders_response.get('stats', {})
        
        return render_template(
            'dashboard/orders.html',
            title='Orders',
            orders=orders_data,
            stats={
                'total_orders': order_stats.get('total_orders', 0),
                'buy_orders': order_stats.get('buy_orders', 0),
                'sell_orders': order_stats.get('sell_orders', 0),
                'completed_orders': order_stats.get('completed_orders', 0),
                'open_orders': order_stats.get('open_orders', 0),
                'rejected_orders': order_stats.get('rejected_orders', 0)
            }
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
        trade_stats = trades_response.get('stats', {})
        
        return render_template(
            'dashboard/trades.html',
            title='Trades',
            trades=trades_data,
            stats={
                'total_trades': trade_stats.get('total_trades', 0),
                'buy_trades': trade_stats.get('buy_trades', 0),
                'sell_trades': trade_stats.get('sell_trades', 0),
                'total_value': trade_stats.get('total_value', 0)
            }
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
        holdings_stats = holdings_response.get('stats', {})
        
        return render_template(
            'dashboard/holdings.html',
            title='Holdings',
            holdings=holdings_data,
            stats={
                'total_holdings_value': holdings_stats.get('total_holdings_value', 0),
                'total_investment': holdings_stats.get('total_investment', 0),
                'total_pnl': holdings_stats.get('total_pnl', 0),
                'total_pnl_percentage': holdings_stats.get('total_pnl_percentage', 0)
            }
        )
    except Exception as e:
        flash(f"Could not fetch holdings: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))
