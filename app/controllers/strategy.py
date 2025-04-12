from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance
from app.forms.strategy_forms import StrategyForm, StrategyInstanceForm
from app.helpers.strategy_helper import extract_params_from_code, execute_strategy_code, get_historical_data
from app.helpers.strategy_helper import activate_strategy_instance, deactivate_strategy_instance
from app.helpers.openalgo_helper import register_webhook
from app.helpers.openalgo_helper import get_openalgo_client
from app.helpers.websocket_helper import websocket_manager
import json
from datetime import datetime, timedelta

strategy_bp = Blueprint('strategy', __name__)

@strategy_bp.route('/strategies')
@login_required
def list_strategies():
    # Get all strategies for the current user
    strategies = Strategy.query.filter_by(user_id=current_user.id).all()
    return render_template('strategy/list.html', title='My Strategies', strategies=strategies)

@strategy_bp.route('/strategies/create', methods=['GET', 'POST'])
@login_required
def create_strategy():
    form = StrategyForm()
    if form.validate_on_submit():
        strategy = Strategy(
            name=form.name.data,
            description=form.description.data,
            code=form.code.data,
            user_id=current_user.id
        )
        db.session.add(strategy)
        db.session.commit()
        flash('Strategy created successfully!', 'success')
        return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))
    return render_template('strategy/create.html', title='Create Strategy', form=form)

@strategy_bp.route('/strategies/<int:strategy_id>')
@login_required
def view_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Ensure the user owns this strategy
    if strategy.user_id != current_user.id and not current_user.is_admin:
        flash("You don't have permission to view this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Extract parameters
    params = extract_params_from_code(strategy.code)
    
    # Get instances using this strategy
    instances = StrategyInstance.query.filter_by(strategy_id=strategy.id).all()
    
    return render_template(
        'strategy/view.html',
        title=strategy.name,
        strategy=strategy,
        params=params,
        instances=instances
    )

@strategy_bp.route('/strategies/<int:strategy_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Ensure the user owns this strategy
    if strategy.user_id != current_user.id:
        flash("You don't have permission to edit this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    form = StrategyForm()
    
    if form.validate_on_submit():
        strategy.name = form.name.data
        strategy.description = form.description.data
        strategy.code = form.code.data
        strategy.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Strategy updated successfully!', 'success')
        return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))
    
    # Populate form with existing data
    if request.method == 'GET':
        form.name.data = strategy.name
        form.description.data = strategy.description
        form.code.data = strategy.code
    
    return render_template('strategy/edit.html', title='Edit Strategy', form=form, strategy=strategy)

@strategy_bp.route('/strategies/<int:strategy_id>/delete', methods=['POST'])
@login_required
def delete_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Ensure the user owns this strategy
    if strategy.user_id != current_user.id:
        flash("You don't have permission to delete this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Check if it has instances
    instances = StrategyInstance.query.filter_by(strategy_id=strategy.id).all()
    if instances:
        flash("Cannot delete strategy with active instances. Delete instances first.", "danger")
        return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))
    
    # Delete the strategy
    db.session.delete(strategy)
    db.session.commit()
    
    flash('Strategy deleted successfully!', 'success')
    return redirect(url_for('strategy.list_strategies'))

@strategy_bp.route('/strategies/<int:strategy_id>/test', methods=['POST'])
@login_required
def test_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Ensure the user owns this strategy or is admin
    if strategy.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'error': "You don't have permission to test this strategy."})
    
    # Get test parameters from form
    data = request.get_json()
    symbol = data.get('symbol')
    exchange = data.get('exchange')
    timeframe = data.get('timeframe')
    params = data.get('params', {})
    
    # Generate date range (last 30 days)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Fetch historical data - first try WebSocket if available
    historical_data = None
    if websocket_manager.connected and websocket_manager.is_symbol_subscribed(symbol):
        historical_data = websocket_manager.get_data_as_dataframe(symbol, 500)
    
    # If WebSocket data not available, fall back to OpenAlgo API
    if historical_data is None or historical_data.empty:
        try:
            historical_data = get_historical_data(
                current_user, symbol, exchange, timeframe, 
                start_date=start_date, end_date=end_date
            )
        except Exception as e:
            return jsonify({'success': False, 'error': f"Error fetching historical data: {str(e)}"})
    
    if historical_data.empty:
        return jsonify({'success': False, 'error': "No historical data available for this symbol and timeframe."})
    
    # Execute strategy
    try:
        # Pass custom params and historical_data to the strategy
        test_params = params.copy()
        
        result = execute_strategy_code(
            strategy.code,
            historical_data=historical_data,
            params=test_params
        )
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result.get('error', "Unknown error executing strategy code."),
                'traceback': result.get('traceback', "")
            })
        
        return jsonify({
            'success': True,
            'signals': result['signals'],
            'output': result.get('output', "")
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@strategy_bp.route('/strategies/<int:strategy_id>/instance/create', methods=['GET', 'POST'])
@login_required
def create_instance(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Ensure the user owns this strategy
    if strategy.user_id != current_user.id:
        flash("You don't have permission to create instances for this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Extract parameters from strategy code
    params = extract_params_from_code(strategy.code)
    
    form = StrategyInstanceForm()
    
    if form.validate_on_submit():
        # Create instance with form data
        instance = StrategyInstance(
            name=form.name.data,
            description=form.description.data,
            symbol=form.symbol.data,
            exchange=form.exchange.data,
            timeframe=form.timeframe.data,
            parameters=json.dumps(form.parameters.data),
            long_entry_action=form.long_entry_action.data,
            long_exit_action=form.long_exit_action.data,
            short_entry_action=form.short_entry_action.data,
            short_exit_action=form.short_exit_action.data,
            position_size=form.position_size.data,
            intraday=form.intraday.data,
            strategy_id=strategy.id,
            is_active=False  # Initially inactive
        )
        
        db.session.add(instance)
        db.session.commit()
        
        flash('Strategy instance created successfully!', 'success')
        return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    return render_template(
        'strategy/create_instance.html',
        title='Create Instance',
        form=form,
        strategy=strategy,
        params=params
    )

@strategy_bp.route('/instances/<int:instance_id>')
@login_required
def view_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = instance.strategy
    
    # Ensure the user owns this instance's strategy or is admin
    if strategy.user_id != current_user.id and not current_user.is_admin:
        flash("You don't have permission to view this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Use parameters directly, no need to parse JSON as SQLAlchemy does that automatically
    parameters = instance.parameters if instance.parameters else {}
    
    return render_template(
        'strategy/view_instance.html',
        title=instance.name,
        instance=instance,
        strategy=strategy,
        parameters=parameters
    )

@strategy_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = instance.strategy
    
    # Ensure the user owns this instance's strategy
    if strategy.user_id != current_user.id:
        flash("You don't have permission to edit this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Cannot edit active instances
    if instance.is_active:
        flash("Cannot edit active instances. Please deactivate first.", "warning")
        return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    # Extract parameters from strategy code
    strategy_params = extract_params_from_code(strategy.code)
    
    form = StrategyInstanceForm()
    
    if form.validate_on_submit():
        # Update instance with form data
        instance.name = form.name.data
        instance.description = form.description.data
        instance.symbol = form.symbol.data
        instance.exchange = form.exchange.data
        instance.timeframe = form.timeframe.data
        instance.parameters = json.dumps(form.parameters.data)
        instance.long_entry_action = form.long_entry_action.data
        instance.long_exit_action = form.long_exit_action.data
        instance.short_entry_action = form.short_entry_action.data
        instance.short_exit_action = form.short_exit_action.data
        instance.position_size = form.position_size.data
        instance.intraday = form.intraday.data
        instance.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Strategy instance updated successfully!', 'success')
        return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    # Populate form with existing data
    if request.method == 'GET':
        form.name.data = instance.name
        form.description.data = instance.description
        form.symbol.data = instance.symbol
        form.exchange.data = instance.exchange
        form.timeframe.data = instance.timeframe
        form.parameters.data = instance.parameters if instance.parameters else {}
        form.long_entry_action.data = instance.long_entry_action
        form.long_exit_action.data = instance.long_exit_action
        form.short_entry_action.data = instance.short_entry_action
        form.short_exit_action.data = instance.short_exit_action
        form.position_size.data = instance.position_size
        form.intraday.data = instance.intraday
    
    return render_template(
        'strategy/edit_instance.html',
        title='Edit Instance',
        form=form,
        instance=instance,
        strategy=strategy,
        params=strategy_params
    )

@strategy_bp.route('/instances/<int:instance_id>/delete', methods=['POST'])
@login_required
def delete_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = instance.strategy
    
    # Ensure the user owns this instance's strategy
    if strategy.user_id != current_user.id:
        flash("You don't have permission to delete this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Deactivate if active
    if instance.is_active:
        deactivate_strategy_instance(instance.id)
    
    # Delete the instance
    db.session.delete(instance)
    db.session.commit()
    
    flash('Strategy instance deleted successfully!', 'success')
    return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))

@strategy_bp.route('/instances/<int:instance_id>/toggle', methods=['POST'])
@login_required
def toggle_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    
    # Ensure the user owns this instance's strategy
    if instance.strategy.user_id != current_user.id:
        flash("You don't have permission to modify this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    # Toggle active status
    if instance.is_active:
        # Deactivate
        result = deactivate_strategy_instance(instance.id)
        instance.is_active = False
        instance.webhook_id = None
    else:
        # Check if OpenAlgo API key is configured
        if not current_user.openalgo_api_key:
            flash("Please configure your OpenAlgo API key in your profile.", "warning")
            return redirect(url_for('auth.profile'))
            
        # Check if WebSocket is connected - warn but allow to continue
        if not websocket_manager.connected:
            flash("Warning: AngelOne WebSocket is not connected. Will use OpenAlgo for data.", "warning")
        
        # Register webhook with OpenAlgo for order execution
        client = get_openalgo_client(current_user)
        webhook_id = register_webhook(client, instance.name)
        
        if webhook_id:
            instance.webhook_id = webhook_id
            instance.is_active = True
            
            # Start the real-time data processing
            result = activate_strategy_instance(current_user, instance)
            
            if not result['success']:
                flash(f"Error activating strategy: {result.get('error')}", "danger")
                return redirect(url_for('strategy.view_instance', instance_id=instance.id))
        else:
            flash("Failed to register webhook with OpenAlgo.", "danger")
            return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    db.session.commit()
    
    status = "activated" if instance.is_active else "deactivated"
    flash(f"Strategy instance {status} successfully.", "success")
    return redirect(url_for('strategy.view_instance', instance_id=instance.id))
