from app import app, db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.instance import StrategyInstance

def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if there are any users
        if User.query.count() == 0:
            # Create admin user
            admin = User(username="admin", email="admin@example.com")
            admin.set_password("admin123")
            admin.openalgo_api_key = ""  # Add your API key here if available
            admin.openalgo_host_url = "http://127.0.0.1:5000"
            
            db.session.add(admin)
            
            # Create demo strategy
            demo_strategy = Strategy(
                name="EMA Crossover Strategy",
                description="A simple EMA crossover strategy for demonstration",
                code="""# EMA Crossover Strategy
# This strategy generates signals based on EMA crossovers

import numpy as np
import pandas as pd

# Define parameters (will be customizable in instances)
# param:
slow_ema = 50  # Slow EMA period
# param:
fast_ema = 20  # Fast EMA period

def run_strategy(df):
    \"\"\"
    Main strategy function
    df: DataFrame with OHLC data
    \"\"\"
    # Calculate EMAs
    df['slow_ema'] = df['close'].ewm(span=slow_ema, adjust=False).mean()
    df['fast_ema'] = df['close'].ewm(span=fast_ema, adjust=False).mean()
    
    # Previous EMAs for comparison
    df['slow_ema_prev'] = df['slow_ema'].shift(1)
    df['fast_ema_prev'] = df['fast_ema'].shift(1)
    
    # Generate signals
    for i in range(1, len(df)):
        # Check for crossover (fast crosses above slow)
        if df['fast_ema_prev'].iloc[i] <= df['slow_ema_prev'].iloc[i] and df['fast_ema'].iloc[i] > df['slow_ema'].iloc[i]:
            long_entry()
        
        # Check for crossunder (fast crosses below slow)
        elif df['fast_ema_prev'].iloc[i] >= df['slow_ema_prev'].iloc[i] and df['fast_ema'].iloc[i] < df['slow_ema'].iloc[i]:
            short_entry()
    
    return df

# Execute the strategy if historical data is provided
if historical_data is not None:
    result = run_strategy(historical_data)
    print(f"Strategy executed with parameters: slow_ema={slow_ema}, fast_ema={fast_ema}")
    print(f"Generated {len(signals)} signals")
""",
                user_id=1  # Admin user
            )
            
            db.session.add(demo_strategy)
            db.session.commit()
            
            # Create strategy instances
            nifty_instance = StrategyInstance(
                name="NIFTY Options Strategy",
                description="EMA crossover on NIFTY futures with options trading",
                symbol="NIFTY",
                exchange="NFO",
                timeframe="5m",
                parameters={"slow_ema": 9, "fast_ema": 21},
                long_entry_action="BUY NIFTY 18000 CE",
                long_exit_action="SELL NIFTY 18000 CE",
                short_entry_action="BUY NIFTY 18000 PE",
                short_exit_action="SELL NIFTY 18000 PE",
                position_size=5.0,
                intraday=True,
                strategy_id=1
            )
            
            banknifty_instance = StrategyInstance(
                name="BankNIFTY Futures Strategy",
                description="EMA crossover on BankNIFTY futures with futures trading",
                symbol="BANKNIFTY",
                exchange="NFO",
                timeframe="15m",
                parameters={"slow_ema": 19, "fast_ema": 50},
                long_entry_action="BUY BANKNIFTY-FUT",
                long_exit_action="SELL BANKNIFTY-FUT",
                short_entry_action="SELL BANKNIFTY-FUT",
                short_exit_action="BUY BANKNIFTY-FUT",
                position_size=10.0,
                intraday=True,
                strategy_id=1
            )
            
            sbin_instance = StrategyInstance(
                name="SBIN Equity Strategy",
                description="EMA crossover on SBIN equity for long-term holding",
                symbol="SBIN",
                exchange="NSE",
                timeframe="D",
                parameters={"slow_ema": 50, "fast_ema": 200},
                long_entry_action="BUY SBIN",
                long_exit_action="SELL SBIN",
                short_entry_action="",
                short_exit_action="",
                position_size=2.0,
                intraday=False,
                strategy_id=1
            )
            
            db.session.add_all([nifty_instance, banknifty_instance, sbin_instance])
            db.session.commit()
            
            print("Database initialized with demo data.")
        else:
            print("Database already contains data. Skipping initialization.")

if __name__ == "__main__":
    init_db()
