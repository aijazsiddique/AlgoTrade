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
        positions = client.positionbook()
        return render_template(
            'dashboard/positions.html',
            title='Positions',
            positions=positions.get('data', [])
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
        orders = client.orderbook()
        return render_template(
            'dashboard/orders.html',
            title='Orders',
            orders=orders.get('data', [])
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
        trades = client.tradebook()
        return render_template(
            'dashboard/trades.html',
            title='Trades',
            trades=trades.get('data', [])
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
        holdings = client.holdings()
        return render_template(
            'dashboard/holdings.html',
            title='Holdings',
            holdings=holdings.get('data', [])
        )
    except Exception as e:
        flash(f"Could not fetch holdings: {str(e)}", "danger")
        return redirect(url_for('dashboard.index'))
