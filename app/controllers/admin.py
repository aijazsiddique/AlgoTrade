from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin decorator to restrict routes to admin users only
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def index():
    # Summary metrics for admin dashboard
    users_count = User.query.count()
    strategies_count = Strategy.query.count()
    active_instances_count = StrategyInstance.query.filter_by(is_active=True).count()
    
    return render_template(
        'admin/index.html',
        title='Admin Dashboard',
        users_count=users_count,
        strategies_count=strategies_count,
        active_instances_count=active_instances_count
    )

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    # Get all users
    all_users = User.query.all()
    
    return render_template(
        'admin/users.html',
        title='User Management',
        users=all_users
    )

@admin_bp.route('/users/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    
    # Do not allow admin to remove their own admin status
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    action = 'granted' if user.is_admin else 'removed'
    flash(f'Admin privileges {action} for user "{user.username}".', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/strategies')
@login_required
@admin_required
def strategies():
    # Get all strategies
    all_strategies = Strategy.query.all()
    
    return render_template(
        'admin/strategies.html',
        title='Strategy Management',
        strategies=all_strategies
    )

@admin_bp.route('/instances')
@login_required
@admin_required
def instances():
    # Get all strategy instances
    all_instances = StrategyInstance.query.all()
    
    return render_template(
        'admin/instances.html',
        title='Instance Management',
        instances=all_instances
    )