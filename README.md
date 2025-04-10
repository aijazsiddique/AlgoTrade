# AlgoTrade Platform

An algorithmic trading platform using OpenAlgo's REST APIs. This platform provides a comprehensive interface for creating, managing, and deploying trading strategies.

## Features

- User authentication system
- Strategy creation and management
- Strategy instance deployment
- Dashboard for monitoring trading activity
- Integration with OpenAlgo for order execution
- Signal generation for different types of trades:
  - Long entry
  - Long exit
  - Short entry
  - Short exit
- Support for various types of trading instruments:
  - Equity
  - Futures
  - Options

## Project Structure

```
algotrade/
├── app/                      # Main application package
│   ├── controllers/          # Controllers/routes
│   ├── forms/                # Flask-WTF forms
│   ├── helpers/              # Helper functions
│   ├── models/               # SQLAlchemy models
│   ├── static/               # Static files (CSS, JS)
│   └── templates/            # Jinja2 templates
├── app.py                    # Application entry point
├── init_db.py                # Database initialization script
└── requirements.txt          # Project dependencies
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/algotrade.git
cd algotrade
```

2. Create and activate a virtual environment:
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

6. Open your browser and navigate to `http://localhost:5000`

## Default Credentials

After initializing the database, a default admin user is created:
- Username: admin
- Email: admin@example.com
- Password: admin123

## Using the Platform

### Creating a Strategy

1. Log in to your account
2. Navigate to "Strategies" and click "Create New Strategy"
3. Define your strategy code with the following signal functions:
   - `long_entry()` - Generate long entry signal
   - `long_exit()` - Generate long exit signal
   - `short_entry()` - Generate short entry signal
   - `short_exit()` - Generate short exit signal

### Creating a Strategy Instance

1. Open a strategy and click "Create Instance"
2. Configure the instance with:
   - Symbol and exchange
   - Timeframe
   - Strategy parameters
   - Signal actions (what to do on each signal type)
   - Position sizing and risk management

### Activating a Strategy

1. Open the strategy instance
2. Click the "Start" button to activate
3. The platform will now generate trading signals based on your strategy

## Integration with OpenAlgo

The platform uses the OpenAlgo Python library to interact with trading APIs. To connect to your trading account:

1. Navigate to your profile
2. Add your OpenAlgo API key and host URL
3. Save your profile

## Example Strategy

The platform comes with a demo EMA crossover strategy. Here's how it works:

1. It calculates two exponential moving averages (EMA):
   - A fast EMA (default: 20 periods)
   - A slow EMA (default: 50 periods)
2. It generates signals based on crossovers:
   - When fast EMA crosses above slow EMA → Long entry signal
   - When fast EMA crosses below slow EMA → Short entry signal

## License

This project is licensed under the MIT License - see the LICENSE file for details.
