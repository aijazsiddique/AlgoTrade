from datetime import datetime
from app import db

class SymbolMapping(db.Model):
    __tablename__ = 'symbol_mapping'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(50), nullable=False)
    exchange = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    
    # AngelOne specific fields
    exchange_type = db.Column(db.Integer, nullable=False)
    token = db.Column(db.String(50), nullable=False)
    
    # Audit fields
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"SymbolMapping('{self.symbol}@{self.exchange}', exchange_type={self.exchange_type}, token={self.token})"
    
    @staticmethod
    def find_mapping(symbol, exchange):
        """Find the token mapping for a symbol and exchange"""
        return SymbolMapping.query.filter_by(
            symbol=symbol,
            exchange=exchange
        ).first()
    
    @classmethod
    def get_or_create_default(cls, symbol, exchange):
        """
        Get the mapping or create a default one if not found.
        In production, you would never want to create default mappings,
        but this is helpful for development/testing.
        """
        mapping = cls.find_mapping(symbol, exchange)
        
        if mapping:
            return mapping
            
        # For demo purposes only - in production, you would raise an exception
        # or implement proper symbol lookup via API
        default_exchange_type = 1  # NSE
        default_token = '26000'  # Default to NIFTY
        
        if exchange == 'BSE':
            default_exchange_type = 2
        elif exchange == 'NFO':
            default_exchange_type = 3
            
        new_mapping = cls(
            symbol=symbol,
            exchange=exchange,
            description=f"Auto-generated mapping for {symbol}@{exchange}",
            exchange_type=default_exchange_type,
            token=default_token
        )
        
        db.session.add(new_mapping)
        db.session.commit()
        
        return new_mapping