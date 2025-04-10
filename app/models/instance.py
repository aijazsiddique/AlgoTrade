from datetime import datetime
from app import db

class StrategyInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Strategy parameters
    symbol = db.Column(db.String(20), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    
    # Custom parameters (stored as JSON)
    parameters = db.Column(db.JSON, nullable=False, default={})
    
    # Signal configuration
    long_entry_action = db.Column(db.String(255), nullable=True)
    long_exit_action = db.Column(db.String(255), nullable=True)
    short_entry_action = db.Column(db.String(255), nullable=True)
    short_exit_action = db.Column(db.String(255), nullable=True)
    
    # Position sizing and risk management
    position_size = db.Column(db.Float, nullable=True)
    intraday = db.Column(db.Boolean, default=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=False)
    webhook_id = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategy.id'), nullable=False)
    
    def __repr__(self):
        return f"StrategyInstance('{self.name}', Symbol: {self.symbol}, Active: {self.is_active})"
