# API Reference Guide

Complete reference documentation for the Kite Auto Trading application's internal APIs and interfaces.

## Table of Contents

1. [Core Components](#core-components)
2. [API Client](#api-client)
3. [Strategy Engine](#strategy-engine)
4. [Risk Manager](#risk-manager)
5. [Order Manager](#order-manager)
6. [Portfolio Manager](#portfolio-manager)
7. [Market Data Feed](#market-data-feed)
8. [Data Models](#data-models)
9. [Configuration](#configuration)
10. [Utilities](#utilities)

---

## Core Components

### TradingApplication

Main application orchestrator that coordinates all components.

**Location**: `kite_auto_trading/main.py`

#### Methods

##### `__init__(config: AppConfig)`

Initialize the trading application with configuration.

**Parameters**:
- `config` (AppConfig): Application configuration object

**Example**:
```python
from kite_auto_trading.main import TradingApplication
from kite_auto_trading.config.models import AppConfig

config = AppConfig.from_file('config.yaml')
app = TradingApplication(config)
```

##### `start() -> bool`

Start the trading application and all components.

**Returns**:
- `bool`: True if started successfully, False otherwise

**Example**:
```python
if app.start():
    print("Application started successfully")
```

##### `stop()`

Stop the trading application gracefully.

**Example**:
```python
app.stop()
```

##### `get_status() -> dict`

Get current application status.

**Returns**:
- `dict`: Status information including component states

**Example**:
```python
status = app.get_status()
print(f"Status: {status['state']}")
```

---

## API Client

### KiteAPIClient

Interface for all Kite Connect API operations.

**Location**: `kite_auto_trading/api/kite_client.py`

#### Methods

##### `__init__(config: APIConfig)`

Initialize the Kite API client.

**Parameters**:
- `config` (APIConfig): API configuration

##### `authenticate(api_key: str, access_token: str) -> bool`

Authenticate with Kite Connect API.

**Parameters**:
- `api_key` (str): Kite API key
- `access_token` (str): Access token

**Returns**:
- `bool`: True if authentication successful

**Example**:
```python
from kite_auto_trading.api.kite_client import KiteAPIClient
from kite_auto_trading.config.models import APIConfig

config = APIConfig(api_key="your_key", access_token="your_token")
client = KiteAPIClient(config)

if client.authenticate(config.api_key, config.access_token):
    print("Authenticated successfully")
```

##### `place_order(order: Order) -> str`

Place a trading order.

**Parameters**:
- `order` (Order): Order object with details

**Returns**:
- `str`: Order ID if successful

**Raises**:
- `Exception`: If order placement fails

**Example**:
```python
from kite_auto_trading.models.base import Order, OrderType, TransactionType

order = Order(
    instrument="RELIANCE",
    transaction_type=TransactionType.BUY,
    quantity=10,
    order_type=OrderType.MARKET
)

order_id = client.place_order(order)
print(f"Order placed: {order_id}")
```

##### `get_positions() -> List[dict]`

Retrieve current positions.

**Returns**:
- `List[dict]`: List of position dictionaries

**Example**:
```python
positions = client.get_positions()
for pos in positions:
    print(f"{pos['tradingsymbol']}: {pos['quantity']}")
```

##### `get_funds() -> dict`

Get available funds and margins.

**Returns**:
- `dict`: Funds information

**Example**:
```python
funds = client.get_funds()
available = funds['equity']['available']['cash']
print(f"Available funds: ₹{available}")
```

##### `get_orders() -> List[dict]`

Retrieve all orders for the day.

**Returns**:
- `List[dict]`: List of order dictionaries

**Example**:
```python
orders = client.get_orders()
for order in orders:
    print(f"Order {order['order_id']}: {order['status']}")
```

##### `cancel_order(order_id: str) -> bool`

Cancel an existing order.

**Parameters**:
- `order_id` (str): Order ID to cancel

**Returns**:
- `bool`: True if cancellation successful

**Example**:
```python
if client.cancel_order("order_123"):
    print("Order cancelled")
```

---

## Strategy Engine

### StrategyBase

Abstract base class for all trading strategies.

**Location**: `kite_auto_trading/strategies/base.py`

#### Methods

##### `evaluate(market_data: dict) -> List[Signal]`

Evaluate market data and generate trading signals.

**Parameters**:
- `market_data` (dict): Current market data

**Returns**:
- `List[Signal]`: List of trading signals

**Example**:
```python
from kite_auto_trading.strategies.base import StrategyBase

class MyStrategy(StrategyBase):
    def evaluate(self, market_data):
        signals = []
        # Strategy logic here
        return signals
```

##### `get_entry_conditions() -> dict`

Get entry condition configuration.

**Returns**:
- `dict`: Entry conditions

##### `get_exit_conditions() -> dict`

Get exit condition configuration.

**Returns**:
- `dict`: Exit conditions

### MovingAverageCrossover

Moving average crossover strategy implementation.

**Location**: `kite_auto_trading/strategies/moving_average_crossover.py`

#### Parameters

- `short_period` (int): Short MA period (default: 10)
- `long_period` (int): Long MA period (default: 20)
- `instruments` (List[str]): List of instruments to trade

**Example**:
```python
from kite_auto_trading.strategies.moving_average_crossover import MovingAverageCrossover

strategy = MovingAverageCrossover(
    short_period=10,
    long_period=20,
    instruments=["RELIANCE", "TCS"]
)

signals = strategy.evaluate(market_data)
```

### RSIMeanReversion

RSI-based mean reversion strategy.

**Location**: `kite_auto_trading/strategies/rsi_mean_reversion.py`

#### Parameters

- `rsi_period` (int): RSI calculation period (default: 14)
- `oversold_threshold` (float): Oversold level (default: 30)
- `overbought_threshold` (float): Overbought level (default: 70)
- `instruments` (List[str]): List of instruments to trade

**Example**:
```python
from kite_auto_trading.strategies.rsi_mean_reversion import RSIMeanReversion

strategy = RSIMeanReversion(
    rsi_period=14,
    oversold_threshold=30,
    overbought_threshold=70,
    instruments=["INFY", "WIPRO"]
)

signals = strategy.evaluate(market_data)
```

---

## Risk Manager

### RiskManager

Manages risk limits and validates trading decisions.

**Location**: `kite_auto_trading/services/risk_manager.py`

#### Methods

##### `__init__(config: RiskConfig)`

Initialize risk manager with configuration.

**Parameters**:
- `config` (RiskConfig): Risk management configuration

##### `validate_order(order: Order) -> bool`

Validate if order meets risk criteria.

**Parameters**:
- `order` (Order): Order to validate

**Returns**:
- `bool`: True if order passes validation

**Example**:
```python
from kite_auto_trading.services.risk_manager import RiskManager
from kite_auto_trading.config.models import RiskConfig

risk_config = RiskConfig(
    max_daily_loss=5000.0,
    max_position_size_percent=2.0,
    stop_loss_percent=2.0,
    target_profit_percent=4.0
)

risk_manager = RiskManager(risk_config)

if risk_manager.validate_order(order):
    # Place order
    pass
```

##### `calculate_position_size(signal: Signal, account_balance: float) -> int`

Calculate appropriate position size based on risk parameters.

**Parameters**:
- `signal` (Signal): Trading signal
- `account_balance` (float): Available account balance

**Returns**:
- `int`: Recommended quantity

**Example**:
```python
quantity = risk_manager.calculate_position_size(signal, 100000.0)
print(f"Recommended quantity: {quantity}")
```

##### `check_daily_limits() -> bool`

Check if daily trading limits have been reached.

**Returns**:
- `bool`: True if within limits

**Example**:
```python
if not risk_manager.check_daily_limits():
    print("Daily loss limit reached - stopping trading")
```

##### `update_daily_pnl(pnl: float)`

Update daily P&L tracking.

**Parameters**:
- `pnl` (float): P&L amount to add

**Example**:
```python
risk_manager.update_daily_pnl(-500.0)  # Record a loss
```

---

## Order Manager

### OrderManager

Manages order lifecycle and execution.

**Location**: `kite_auto_trading/services/order_manager.py`

#### Methods

##### `__init__(config: APIConfig)`

Initialize order manager.

**Parameters**:
- `config` (APIConfig): API configuration

##### `place_order(order: Order) -> str`

Place an order and track its execution.

**Parameters**:
- `order` (Order): Order to place

**Returns**:
- `str`: Order ID

**Example**:
```python
from kite_auto_trading.services.order_manager import OrderManager

order_manager = OrderManager(api_config)
order_id = order_manager.place_order(order)
```

##### `get_order_status(order_id: str) -> dict`

Get current status of an order.

**Parameters**:
- `order_id` (str): Order ID

**Returns**:
- `dict`: Order status information

**Example**:
```python
status = order_manager.get_order_status(order_id)
print(f"Order status: {status['status']}")
```

##### `cancel_order(order_id: str) -> bool`

Cancel a pending order.

**Parameters**:
- `order_id` (str): Order ID to cancel

**Returns**:
- `bool`: True if cancelled successfully

**Example**:
```python
if order_manager.cancel_order(order_id):
    print("Order cancelled")
```

##### `modify_order(order_id: str, **kwargs) -> bool`

Modify an existing order.

**Parameters**:
- `order_id` (str): Order ID
- `**kwargs`: Order parameters to modify

**Returns**:
- `bool`: True if modified successfully

**Example**:
```python
order_manager.modify_order(order_id, quantity=15, price=2550.0)
```

---

## Portfolio Manager

### PortfolioManager

Tracks positions and calculates P&L.

**Location**: `kite_auto_trading/services/portfolio_manager.py`

#### Methods

##### `__init__(config: RiskConfig)`

Initialize portfolio manager.

**Parameters**:
- `config` (RiskConfig): Risk configuration

##### `get_positions() -> List[Position]`

Get all current positions.

**Returns**:
- `List[Position]`: List of position objects

**Example**:
```python
from kite_auto_trading.services.portfolio_manager import PortfolioManager

portfolio = PortfolioManager(risk_config)
positions = portfolio.get_positions()

for pos in positions:
    print(f"{pos.instrument}: {pos.quantity} @ ₹{pos.average_price}")
```

##### `calculate_unrealized_pnl() -> float`

Calculate total unrealized P&L.

**Returns**:
- `float`: Unrealized P&L amount

**Example**:
```python
unrealized = portfolio.calculate_unrealized_pnl()
print(f"Unrealized P&L: ₹{unrealized}")
```

##### `calculate_realized_pnl() -> float`

Calculate total realized P&L.

**Returns**:
- `float`: Realized P&L amount

**Example**:
```python
realized = portfolio.calculate_realized_pnl()
print(f"Realized P&L: ₹{realized}")
```

##### `generate_report(start_date: datetime, end_date: datetime) -> dict`

Generate portfolio report for date range.

**Parameters**:
- `start_date` (datetime): Report start date
- `end_date` (datetime): Report end date

**Returns**:
- `dict`: Report data

**Example**:
```python
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

report = portfolio.generate_report(start_date, end_date)
print(f"Total P&L: ₹{report['total_pnl']}")
```

---

## Market Data Feed

### MarketDataFeed

Manages real-time market data subscriptions.

**Location**: `kite_auto_trading/services/market_data_feed.py`

#### Methods

##### `__init__(config: APIConfig)`

Initialize market data feed.

**Parameters**:
- `config` (APIConfig): API configuration

##### `connect()`

Connect to market data WebSocket.

**Example**:
```python
from kite_auto_trading.services.market_data_feed import MarketDataFeed

feed = MarketDataFeed(api_config)
feed.connect()
```

##### `subscribe(instruments: List[str])`

Subscribe to instruments for real-time data.

**Parameters**:
- `instruments` (List[str]): List of instrument symbols

**Example**:
```python
feed.subscribe(["RELIANCE", "TCS", "INFY"])
```

##### `unsubscribe(instruments: List[str])`

Unsubscribe from instruments.

**Parameters**:
- `instruments` (List[str]): List of instrument symbols

**Example**:
```python
feed.unsubscribe(["WIPRO"])
```

##### `get_latest_tick(instrument: str) -> Tick`

Get latest tick data for instrument.

**Parameters**:
- `instrument` (str): Instrument symbol

**Returns**:
- `Tick`: Latest tick data

**Example**:
```python
tick = feed.get_latest_tick("RELIANCE")
print(f"Last price: ₹{tick.last_price}")
```

---

## Data Models

### Order

Represents a trading order.

**Location**: `kite_auto_trading/models/base.py`

#### Attributes

- `instrument` (str): Trading symbol
- `transaction_type` (TransactionType): BUY or SELL
- `quantity` (int): Order quantity
- `order_type` (OrderType): MARKET, LIMIT, SL, SL-M
- `price` (Optional[float]): Limit price
- `trigger_price` (Optional[float]): Trigger price for SL orders
- `strategy_id` (Optional[str]): Strategy that generated the order

**Example**:
```python
from kite_auto_trading.models.base import Order, OrderType, TransactionType

order = Order(
    instrument="RELIANCE",
    transaction_type=TransactionType.BUY,
    quantity=10,
    order_type=OrderType.LIMIT,
    price=2500.0
)
```

### Signal

Represents a trading signal from a strategy.

**Location**: `kite_auto_trading/models/signals.py`

#### Attributes

- `signal_type` (SignalType): BUY, SELL, or HOLD
- `instrument` (str): Trading symbol
- `price` (float): Signal price
- `quantity` (int): Recommended quantity
- `strategy_name` (str): Strategy that generated signal
- `timestamp` (datetime): Signal generation time
- `confidence` (Optional[float]): Signal confidence (0-1)

**Example**:
```python
from kite_auto_trading.models.signals import Signal, SignalType
from datetime import datetime

signal = Signal(
    signal_type=SignalType.BUY,
    instrument="TCS",
    price=3500.0,
    quantity=5,
    strategy_name="ma_crossover",
    timestamp=datetime.now(),
    confidence=0.85
)
```

### Tick

Represents real-time market tick data.

**Location**: `kite_auto_trading/models/market_data.py`

#### Attributes

- `instrument` (str): Trading symbol
- `last_price` (float): Last traded price
- `volume` (int): Volume traded
- `timestamp` (datetime): Tick timestamp
- `bid` (Optional[float]): Best bid price
- `ask` (Optional[float]): Best ask price

**Example**:
```python
from kite_auto_trading.models.market_data import Tick
from datetime import datetime

tick = Tick(
    instrument="INFY",
    last_price=1450.50,
    volume=1000000,
    timestamp=datetime.now()
)
```

---

## Configuration

### AppConfig

Main application configuration.

**Location**: `kite_auto_trading/config/models.py`

#### Methods

##### `from_file(path: str) -> AppConfig`

Load configuration from YAML file.

**Parameters**:
- `path` (str): Path to config file

**Returns**:
- `AppConfig`: Configuration object

**Example**:
```python
from kite_auto_trading.config.models import AppConfig

config = AppConfig.from_file('config.yaml')
```

##### `from_dict(data: dict) -> AppConfig`

Create configuration from dictionary.

**Parameters**:
- `data` (dict): Configuration dictionary

**Returns**:
- `AppConfig`: Configuration object

**Example**:
```python
config_dict = {
    'api': {'api_key': 'key', 'access_token': 'token'},
    'risk': {'max_daily_loss': 5000.0}
}

config = AppConfig.from_dict(config_dict)
```

---

## Utilities

### LoggingService

Centralized logging service.

**Location**: `kite_auto_trading/services/logging_service.py`

#### Methods

##### `log_trade(trade_details: dict)`

Log trade execution.

**Parameters**:
- `trade_details` (dict): Trade information

**Example**:
```python
from kite_auto_trading.services.logging_service import LoggingService

logger = LoggingService()
logger.log_trade({
    'order_id': 'order_123',
    'instrument': 'RELIANCE',
    'quantity': 10,
    'price': 2500.0
})
```

##### `log_error(message: str, context: dict)`

Log error with context.

**Parameters**:
- `message` (str): Error message
- `context` (dict): Error context

**Example**:
```python
logger.log_error("Order placement failed", {
    'instrument': 'TCS',
    'error_code': 'INSUFFICIENT_FUNDS'
})
```

### MonitoringService

System monitoring and alerting.

**Location**: `kite_auto_trading/services/monitoring_service.py`

#### Methods

##### `track_metric(metric_name: str, value: float)`

Track a performance metric.

**Parameters**:
- `metric_name` (str): Metric name
- `value` (float): Metric value

**Example**:
```python
from kite_auto_trading.services.monitoring_service import MonitoringService

monitor = MonitoringService()
monitor.track_metric('daily_pnl', 1500.0)
```

##### `send_alert(alert_type: str, message: str)`

Send an alert notification.

**Parameters**:
- `alert_type` (str): Alert type
- `message` (str): Alert message

**Example**:
```python
monitor.send_alert('RISK_LIMIT', 'Daily loss limit approaching')
```

---

## Error Handling

All API methods may raise the following exceptions:

- `ConnectionError`: Network connectivity issues
- `AuthenticationError`: API authentication failures
- `ValidationError`: Invalid parameters or configuration
- `RiskLimitError`: Risk limits exceeded
- `OrderRejectionError`: Order rejected by exchange

**Example Error Handling**:
```python
try:
    order_id = client.place_order(order)
except ConnectionError:
    logger.log_error("Network error", {'operation': 'place_order'})
except RiskLimitError as e:
    logger.log_error(f"Risk limit exceeded: {e}", {})
except Exception as e:
    logger.log_error(f"Unexpected error: {e}", {})
```

---

## Best Practices

1. **Always validate orders** before placement using RiskManager
2. **Handle exceptions** gracefully with proper logging
3. **Monitor performance** using MonitoringService
4. **Use configuration files** instead of hardcoding values
5. **Test strategies** with historical data before live trading
6. **Implement proper logging** for audit trails
7. **Set appropriate risk limits** based on account size
8. **Monitor daily P&L** and stop trading if limits reached

---

## Examples

### Complete Trading Workflow

```python
from kite_auto_trading.main import TradingApplication
from kite_auto_trading.config.models import AppConfig

# Load configuration
config = AppConfig.from_file('config.yaml')

# Initialize application
app = TradingApplication(config)

# Start trading
if app.start():
    print("Trading application started")
    
    # Application runs until stopped
    try:
        while True:
            status = app.get_status()
            print(f"Status: {status}")
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping application...")
        app.stop()
```

### Custom Strategy Implementation

```python
from kite_auto_trading.strategies.base import StrategyBase
from kite_auto_trading.models.signals import Signal, SignalType
from datetime import datetime

class CustomStrategy(StrategyBase):
    def __init__(self, instruments, threshold=0.02):
        super().__init__("custom_strategy", instruments)
        self.threshold = threshold
    
    def evaluate(self, market_data):
        signals = []
        
        for instrument in self.instruments:
            if instrument in market_data:
                price = market_data[instrument]['last_price']
                
                # Custom logic here
                if self.should_buy(price):
                    signal = Signal(
                        signal_type=SignalType.BUY,
                        instrument=instrument,
                        price=price,
                        quantity=10,
                        strategy_name=self.name,
                        timestamp=datetime.now()
                    )
                    signals.append(signal)
        
        return signals
    
    def should_buy(self, price):
        # Implement your logic
        return True
```

---

## Version History

- **v1.0.0**: Initial release with core functionality
- **v1.1.0**: Added backtesting capabilities
- **v1.2.0**: Enhanced risk management features

---

## Support

For questions or issues:
- Check documentation in `docs/` directory
- Review example configurations in `config/` directory
- Consult Kite Connect API documentation: https://kite.trade/docs/connect/v3/
