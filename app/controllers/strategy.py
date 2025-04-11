from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance
from app.forms.strategy_forms import StrategyForm, StrategyInstanceForm
from app.helpers.strategy_helper import execute_strategy_code, get_historical_data
from app.helpers.openalgo_helper import get_openalgo_client, register_webhook
import json

strategy_bp = Blueprint('strategy', __name__)

@strategy_bp.route('/strategies')
@login_required
def list_strategies():
    strategies = Strategy.query.filter_by(user_id=current_user.id).all()
    return render_template('strategy/list.html', title='My Strategies', strategies=strategies)

@strategy_bp.route('/strategies/new', methods=['GET', 'POST'])
@login_required
def create_strategy():
    form = StrategyForm()
    if form.validate_on_submit():
        # Manual validation for code field since we removed the DataRequired validator
        if not form.code.data or not form.code.data.strip():
            flash("Strategy code is required", "danger")
            return render_template('strategy/create.html', title='Create Strategy', form=form)
            
        # Check if strategy code can be executed
        test_result = execute_strategy_code(form.code.data)
        if not test_result['success']:
            flash(f"Strategy code error: {test_result['error']}", "danger")
            return render_template('strategy/create.html', title='Create Strategy', form=form)
        
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
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to view this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    instances = StrategyInstance.query.filter_by(strategy_id=strategy_id).all()
    return render_template(
        'strategy/view.html',
        title=strategy.name,
        strategy=strategy,
        instances=instances
    )

@strategy_bp.route('/strategies/<int:strategy_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to edit this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    form = StrategyForm()
    
    if form.validate_on_submit():
        # Manual validation for code field since we removed the DataRequired validator
        if not form.code.data or not form.code.data.strip():
            flash("Strategy code is required", "danger")
            return render_template('strategy/edit.html', title='Edit Strategy', form=form, strategy=strategy)
            
        # Check if strategy code can be executed
        test_result = execute_strategy_code(form.code.data)
        if not test_result['success']:
            flash(f"Strategy code error: {test_result['error']}", "danger")
            return render_template('strategy/edit.html', title='Edit Strategy', form=form, strategy=strategy)
        
        strategy.name = form.name.data
        strategy.description = form.description.data
        strategy.code = form.code.data
        db.session.commit()
        
        flash('Strategy updated successfully!', 'success')
        return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))
    
    elif request.method == 'GET':
        form.name.data = strategy.name
        form.description.data = strategy.description
        form.code.data = strategy.code
    
    return render_template('strategy/edit.html', title='Edit Strategy', form=form, strategy=strategy)

@strategy_bp.route('/strategies/<int:strategy_id>/delete', methods=['POST'])
@login_required
def delete_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to delete this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    db.session.delete(strategy)
    db.session.commit()
    
    flash('Strategy deleted successfully!', 'success')
    return redirect(url_for('strategy.list_strategies'))

@strategy_bp.route('/strategies/<int:strategy_id>/test', methods=['POST'])
@login_required
def test_strategy(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Permission denied'})
    
    # Get test parameters from request
    data = request.json
    symbol = data.get('symbol', 'NIFTY')
    exchange = data.get('exchange', 'NSE')
    timeframe = data.get('timeframe', '5m')
    params = data.get('params', {})
    
    # Get historical data
    if not current_user.openalgo_api_key:
        return jsonify({'success': False, 'error': 'OpenAlgo API key not configured'})
    
    try:
        # Get historical data for testing
        hist_data = get_historical_data(current_user, symbol, exchange, timeframe)
        
        # Execute strategy with the data
        result = execute_strategy_code(
            strategy.code,
            historical_data=hist_data,
            params=params
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'signals': result['signals'],
                'stats': result.get('stats', {})
            })
        else:
            return jsonify({'success': False, 'error': result['error']})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@strategy_bp.route('/strategies/<int:strategy_id>/instances/new', methods=['GET', 'POST'])
@login_required
def create_instance(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to add instances to this strategy.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    form = StrategyInstanceForm()
    
    if form.validate_on_submit():
        parameters = {}
        # Get custom parameters from form
        for field_name, field_value in request.form.items():
            if field_name.startswith('param_'):
                param_name = field_name[6:]  # Remove 'param_' prefix
                parameters[param_name] = field_value
        
        instance = StrategyInstance(
            name=form.name.data,
            description=form.description.data,
            symbol=form.symbol.data,
            exchange=form.exchange.data,
            timeframe=form.timeframe.data,
            parameters=parameters,
            long_entry_action=form.long_entry_action.data,
            long_exit_action=form.long_exit_action.data,
            short_entry_action=form.short_entry_action.data,
            short_exit_action=form.short_exit_action.data,
            position_size=form.position_size.data,
            intraday=form.intraday.data,
            strategy_id=strategy.id
        )
        
        db.session.add(instance)
        db.session.commit()
        
        flash('Strategy instance created successfully!', 'success')
        return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    return render_template(
        'strategy/create_instance.html',
        title='Create Strategy Instance',
        form=form,
        strategy=strategy
    )

@strategy_bp.route('/instances/<int:instance_id>')
@login_required
def view_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = Strategy.query.get_or_404(instance.strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to view this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    return render_template(
        'strategy/view_instance.html',
        title=instance.name,
        instance=instance,
        strategy=strategy
    )

@strategy_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = Strategy.query.get_or_404(instance.strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to edit this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    form = StrategyInstanceForm()
    
    if form.validate_on_submit():
        parameters = {}
        # Get custom parameters from form
        for field_name, field_value in request.form.items():
            if field_name.startswith('param_'):
                param_name = field_name[6:]  # Remove 'param_' prefix
                parameters[param_name] = field_value
        
        instance.name = form.name.data
        instance.description = form.description.data
        instance.symbol = form.symbol.data
        instance.exchange = form.exchange.data
        instance.timeframe = form.timeframe.data
        instance.parameters = parameters
        instance.long_entry_action = form.long_entry_action.data
        instance.long_exit_action = form.long_exit_action.data
        instance.short_entry_action = form.short_entry_action.data
        instance.short_exit_action = form.short_exit_action.data
        instance.position_size = form.position_size.data
        instance.intraday = form.intraday.data
        
        db.session.commit()
        
        flash('Strategy instance updated successfully!', 'success')
        return redirect(url_for('strategy.view_instance', instance_id=instance.id))
    
    elif request.method == 'GET':
        form.name.data = instance.name
        form.description.data = instance.description
        form.symbol.data = instance.symbol
        form.exchange.data = instance.exchange
        form.timeframe.data = instance.timeframe
        form.long_entry_action.data = instance.long_entry_action
        form.long_exit_action.data = instance.long_exit_action
        form.short_entry_action.data = instance.short_entry_action
        form.short_exit_action.data = instance.short_exit_action
        form.position_size.data = instance.position_size
        form.intraday.data = instance.intraday
    
    return render_template(
        'strategy/edit_instance.html',
        title='Edit Strategy Instance',
        form=form,
        instance=instance,
        strategy=strategy,
        parameters=instance.parameters
    )

@strategy_bp.route('/instances/<int:instance_id>/delete', methods=['POST'])
@login_required
def delete_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = Strategy.query.get_or_404(instance.strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to delete this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    db.session.delete(instance)
    db.session.commit()
    
    flash('Strategy instance deleted successfully!', 'success')
    return redirect(url_for('strategy.view_strategy', strategy_id=strategy.id))

@strategy_bp.route('/instances/<int:instance_id>/toggle', methods=['POST'])
@login_required
def toggle_instance(instance_id):
    instance = StrategyInstance.query.get_or_404(instance_id)
    strategy = Strategy.query.get_or_404(instance.strategy_id)
    
    # Check if user is the owner
    if strategy.user_id != current_user.id:
        flash("You don't have permission to modify this instance.", "danger")
        return redirect(url_for('strategy.list_strategies'))
    
    if not current_user.openalgo_api_key:
        flash("Please configure your OpenAlgo API key in your profile.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        if instance.is_active:
            # Deactivate the instance
            instance.is_active = False
            instance.webhook_id = None
            db.session.commit()
            flash('Strategy instance deactivated successfully!', 'success')
        else:
            # Register webhook and activate the instance
            client = get_openalgo_client(current_user)
            webhook_id = register_webhook(client, instance.name)
            
            if webhook_id:
                instance.is_active = True
                instance.webhook_id = webhook_id
                db.session.commit()
                flash('Strategy instance activated successfully!', 'success')
            else:
                flash('Failed to register webhook with OpenAlgo.', 'danger')
    
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('strategy.view_instance', instance_id=instance.id))
