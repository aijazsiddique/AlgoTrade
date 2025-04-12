# AlgoTrade Platform Project Documentation

## Project Overview

AlgoTrade is a web-based algorithmic trading platform that allows users to create, manage, and deploy automated trading strategies using the OpenAlgo API. The platform provides a comprehensive interface for strategy development, backtesting, and live trading execution.

### Key Features

- **User Authentication System**: Secure login/registration with password hashing
- **Strategy Management**: Create and manage base trading strategies in Python
- **Strategy Instances**: Deploy multiple instances of a strategy with different parameters
- **Dashboard**: Monitor trading activities and account information
- **Trading Account Integration**: Connect to trading accounts via OpenAlgo API
- **Signal Generation**: Support for various trading signals (long entry/exit, short entry/exit)
- **Responsive Design**: Modern UI with sidebar navigation for desktop and mobile
- **Admin Panel**: Administrative interface for user, strategy, and instance management

### Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **ORM**: SQLAlchemy
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Authentication**: Flask-Login, Flask-Bcrypt
- **Form Handling**: Flask-WTF
- **Code Editing**: CodeMirror
- **Trading API**: OpenAlgo Python library

## Project Structure

```
algotrade/
├── app/                      # Main application package
│   ├── controllers/          # Route controllers
│   │   ├── admin.py          # Admin routes
│   │   ├── auth.py           # Authentication routes
│   │   ├── dashboard.py      # Dashboard and account routes
│   │   └── strategy.py       # Strategy management routes
│   ├── forms/                # Form definitions
│   │   ├── auth_forms.py     # Authentication forms
│   │   ├── strategy_forms.py # Strategy forms
│   │   └── __init__.py
│   ├── helpers/              # Helper functions
│   │   ├── openalgo_helper.py # OpenAlgo API integration
│   │   ├── strategy_helper.py # Strategy execution helpers
│   │   └── __init__.py
│   ├── models/               # Database models
│   │   ├── instance.py       # Strategy instance model
│   │   ├── strategy.py       # Base strategy model
│   │   ├── user.py           # User model
│   │   └── __init__.py
│   ├── static/               # Static assets
│   │   ├── css/
│   │   │   └── style.css     # Custom styles
│   │   └── js/
│   │       └── main.js       # Custom JavaScript
│   ├── templates/            # Jinja2 templates
│   │   ├── admin/            # Admin templates
│   │   │   ├── index.html
│   │   │   ├── users.html
│   │   │   ├── strategies.html
│   │   │   └── instances.html
│   │   ├── auth/             # Authentication templates
│   │   │   ├── login.html
│   │   │   ├── profile.html
│   │   │   └── register.html
│   │   ├── dashboard/        # Dashboard templates
│   │   │   ├── holdings.html
│   │   │   ├── index.html
│   │   │   ├── orders.html
│   │   │   ├── positions.html
│   │   │   └── trades.html
│   │   ├── layout.html       # Base template
│   │   └── strategy/         # Strategy templates
│   │       ├── create.html
│   │       ├── create_instance.html
│   │       ├── edit.html
│   │       ├── edit_instance.html
│   │       ├── list.html
│   │       ├── view.html
│   │       └── view_instance.html
│   └── __init__.py           # Application factory
├── app.py                    # Application entry point
├── init_db.py                # Database initialization script
├── requirements.txt          # Project dependencies
├── README.md                 # Project overview
└── project.md                # Detailed project documentation (this file)
```

## Detailed Implementation

### Database Models

#### User Model (`app/models/user.py`)

The User model handles user authentication and API configuration:

- **Fields**:
  - `id`: Primary key
  - `username`: Unique username
  - `email`: Unique email address
  - `password_hash`: Hashed password using bcrypt
  - `is_admin`: Boolean flag for administrator privileges
  - `openalgo_api_key`: API key for OpenAlgo
  - `openalgo_host_url`: OpenAlgo server URL
  - `created_at` and `updated_at`: Timestamps
  - Relationship with `strategies`

- **Methods**:
  - `set_password()`: Hash and set password
  - `check_password()`: Verify password
  - `load_user()`: Flask-Login user loader

#### Strategy Model (`app/models/strategy.py`)

The Strategy model stores the base trading strategy code:

- **Fields**:
  - `id`: Primary key
  - `name`: Strategy name
  - `description`: Strategy description
  - `code`: Python code for the strategy
  - `created_at` and `updated_at`: Timestamps
  - `user_id`: Foreign key to User
  - Relationship with `instances`

#### Strategy Instance Model (`app/models/instance.py`)

The StrategyInstance model configures specific implementations of a strategy:

- **Fields**:
  - `id`: Primary key
  - `name`: Instance name
  - `description`: Instance description
  - `symbol`, `exchange`, `timeframe`: Instrument settings
  - `parameters`: JSON field for custom parameters
  - Signal actions: `long_entry_action`, `long_exit_action`, etc.
  - `position_size`: Position sizing percentage
  - `intraday`: Boolean for intraday trading flag
  - `is_active`: Boolean activation status
  - `webhook_id`: ID for OpenAlgo webhook
  - `created_at` and `updated_at`: Timestamps
  - `strategy_id`: Foreign key to Strategy

### Controllers/Routes

#### Authentication Controller (`app/controllers/auth.py`)

Handles user authentication, registration, and profile management:

- `/register`: User registration
- `/login`: User login
- `/logout`: User logout
- `/profile`: User profile and API settings

#### Dashboard Controller (`app/controllers/dashboard.py`)

Manages dashboard views and account information:

- `/dashboard`: Main dashboard view
- `/dashboard/positions`: Current positions
- `/dashboard/orders`: Order book
- `/dashboard/trades`: Trade book
- `/dashboard/holdings`: Stock holdings

#### Strategy Controller (`app/controllers/strategy.py`)

Manages strategy and instance creation, editing, and deployment:

- `/strategies`: List all strategies
- `/strategies/new`: Create new strategy
- `/strategies/<id>`: View strategy details
- `/strategies/<id>/edit`: Edit strategy
- `/strategies/<id>/delete`: Delete strategy
- `/strategies/<id>/test`: Test strategy
- `/strategies/<id>/instances/new`: Create new instance
- `/instances/<id>`: View instance details
- `/instances/<id>/edit`: Edit instance
- `/instances/<id>/delete`: Delete instance
- `/instances/<id>/toggle`: Activate/deactivate instance

#### Admin Controller (`app/controllers/admin.py`)

Manages administrator interface and user management:

- `/admin`: Main admin dashboard with summary statistics
- `/admin/users`: User management interface
- `/admin/users/<id>/toggle_admin`: Toggle admin privileges for users
- `/admin/strategies`: View all strategies across users
- `/admin/instances`: View all strategy instances across users

### Helper Functions

#### OpenAlgo Helpers (`app/helpers/openalgo_helper.py`)

Provides integration with the OpenAlgo API:

- `get_openalgo_client()`: Create API client
- `register_webhook()`: Register strategy webhook
- `send_strategy_signal()`: Send trading signals
- `format_order_params()`: Format order parameters

#### Strategy Helpers (`app/helpers/strategy_helper.py`)

Helps with strategy execution and testing:

- `extract_params_from_code()`: Parse parameters from strategy code
- `execute_strategy_code()`: Run strategy with test data
- `get_historical_data()`: Fetch data for backtesting
- `backtest_strategy()`: Run backtest on historical data

### Frontend Templates

#### Layout Template (`app/templates/layout.html`)

The main layout template with the sidebar and structure:

- Sidebar navigation
- Top navbar
- Content area
- JavaScript and CSS includes

#### Dashboard Templates (`app/templates/dashboard/`)

Templates for the dashboard and account information:

- `index.html`: Main dashboard
- `positions.html`, `orders.html`, etc.: Account views

#### Strategy Templates (`app/templates/strategy/`)

Templates for strategy management:

- `list.html`: Strategy list
- `create.html`, `edit.html`: Strategy forms
- `view.html`: Strategy details
- `create_instance.html`, `edit_instance.html`: Instance forms
- `view_instance.html`: Instance details

#### Authentication Templates (`app/templates/auth/`)

Templates for user authentication:

- `login.html`: Login form
- `register.html`: Registration form
- `profile.html`: User profile form

#### Admin Templates (`app/templates/admin/`)

Templates for the admin dashboard and management interfaces:

- `index.html`: Admin dashboard with summary statistics
- `users.html`: User management interface
- `strategies.html`: Strategy management overview
- `instances.html`: Instance management overview

### CSS & JavaScript

#### Custom CSS (`app/static/css/style.css`)

Custom styling for the platform:

- Sidebar styling
- Card designs
- Color scheme (#F3EEEA, #EBE3D5, #B0A695, #776B5D)
- Responsive adjustments
- Form styling
- Dashboard components

#### Custom JavaScript (`app/static/js/main.js`)

JavaScript functionality:

- Sidebar toggling
- Form handling
- Strategy testing
- UI interactions

## Key Functionality Details

### User Authentication Flow

1. User registers with email, username, and password
2. Password is hashed using bcrypt before storage
3. Login credentials are validated against database
4. Flask-Login handles session management
5. User profile allows updating API keys and credentials

### Strategy Creation Process

1. User writes Python strategy code using provided functions
   - `long_entry()`, `long_exit()`, `short_entry()`, `short_exit()`
2. Strategy parameters are parsed from code comments
3. Code is validated and stored in the database
4. User can test the strategy with historical data

### Strategy Instance Deployment

1. User creates an instance of a base strategy
2. Configures symbol, exchange, timeframe, and parameters
3. Sets up actions for different signal types
4. Configures position sizing and intraday settings
5. Activates the instance which registers a webhook with OpenAlgo

### Trading Signal Flow

1. Strategy instance is active and monitoring the market
2. When signals are generated, they trigger the webhook
3. OpenAlgo executes the configured action (e.g., buy/sell)
4. Results are reflected in the trading account

### Admin Management Flow

1. Users with admin privileges can access the admin dashboard
2. Admins can view all users, strategies, and instances in the system
3. Admins can grant or revoke admin privileges for other users
4. Admins can monitor system activity and performance

## Extension Points

### Adding New Strategy Types

To add new strategy types:

1. Extend the strategy helper functions in `strategy_helper.py`
2. Add new signal types if needed
3. Update the strategy templates to support new parameters

### Custom Indicators

To add custom technical indicators:

1. Add the indicator calculation to the strategy helper
2. Update the example code template
3. Include documentation in the strategy creation form

### Advanced Backtesting

To enhance backtesting capabilities:

1. Extend the `backtest_strategy()` function
2. Add performance metrics calculation
3. Create visualization components for backtesting results

### Multi-Broker Support

To support multiple brokers:

1. Extend the OpenAlgo helper to support different broker APIs
2. Add broker selection to the user profile
3. Update the instance configuration to support broker-specific settings

### Error Handling and Robustness

The platform includes robust error handling for API interactions:

1. All API responses are validated for expected structure
2. Type checking ensures compatibility with templates
3. Graceful fallbacks provide usable information even with unexpected data formats
4. User feedback through flash messages gives clear error information

## Database Schema

### Users Table

```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(60) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT 0,
    openalgo_api_key VARCHAR(100),
    openalgo_host_url VARCHAR(255) DEFAULT "http://127.0.0.1:5000",
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### Strategies Table

```sql
CREATE TABLE strategy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id)
);
```

### Strategy Instances Table

```sql
CREATE TABLE strategy_instance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    parameters JSON NOT NULL DEFAULT '{}',
    long_entry_action VARCHAR(255),
    long_exit_action VARCHAR(255),
    short_entry_action VARCHAR(255),
    short_exit_action VARCHAR(255),
    position_size FLOAT,
    intraday BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT FALSE,
    webhook_id VARCHAR(100),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    strategy_id INTEGER NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategy (id)
);
```

## Installation and Setup

### Prerequisites

- Python 3.8+
- pip
- OpenAlgo account and API key

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/algotrade.git
   cd algotrade
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python init_db.py
   ```

5. (Optional) Apply migrations if updating an existing installation:
   ```bash
   flask db migrate -m "Description of changes"
   flask db upgrade
   ```

6. Run the application:
   ```bash
   python app.py
   ```

7. Access the application at `http://localhost:5000`

### Default Credentials

After initialization, a default admin user is created:
- Username: admin
- Email: admin@example.com
- Password: admin123

## Color Scheme

The platform uses an beautiful color palette:

- **#222831** (Dark blue/black) as the primary dark color for the sidebar, primary buttons, and dark backgrounds
- **#393E46** (Dark gray) as a secondary dark color for hover states, borders, and secondary elements
- **#00ADB5**  (Teal) as the accent color for highlights, active states, and success indicators
- **#EEEEEE** (Light gray) as the main background color for light elements

This palette creates a professional, warm, and timeless aesthetic.

## OpenAlgo API Integration

The platform uses the OpenAlgo Python library for trading operations:

### API Client Initialization

```python
from openalgo import api

client = api(
    api_key=user.openalgo_api_key,
    host=user.openalgo_host_url
)
```

### Strategy Signals

```python
from openalgo import Strategy

strategy_client = Strategy(
    host_url=user.openalgo_host_url,
    webhook_id=webhook_id
)

# Send signal
response = strategy_client.strategyorder(symbol, action, position_size)
```

### Account Operations

```python
# Get funds
funds = client.funds()

# Get positions
positions = client.positionbook()

# Get orders
orders = client.orderbook()

# Get trades
trades = client.tradebook()

# Get holdings
holdings = client.holdings()
```

## Example Strategy

The platform comes with a demo EMA crossover strategy:

```python
# EMA Crossover Strategy
# This strategy generates signals based on EMA crossovers

import numpy as np
import pandas as pd

# Define parameters (will be customizable in instances)
# param:
slow_ema = 50  # Slow EMA period
# param:
fast_ema = 20  # Fast EMA period

def run_strategy(df):
    """
    Main strategy function
    df: DataFrame with OHLC data
    """
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
```

## Contributing

To contribute to the project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

### Code Style

- Follow PEP 8 guidelines for Python code
- Use consistent indentation (4 spaces)
- Add docstrings to functions and classes
- Use meaningful variable and function names

## License

This project is licensed under the MIT License.

## Acknowledgements

- OpenAlgo for providing the trading API
- Flask and related extensions for the web framework
- Bootstrap for the frontend components