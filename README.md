# Kite Auto-Trading Application

An automated trading system that integrates with Zerodha's Kite Connect API to execute trading strategies with proper risk management.

## Project Structure

```
kite_auto_trading/
├── __init__.py          # Package initialization
├── main.py              # Application entry point
├── api/                 # API integration layer
│   ├── __init__.py
│   └── base.py          # Base API interfaces
├── config/              # Configuration management
│   └── __init__.py
├── models/              # Data models and structures
│   ├── __init__.py
│   └── base.py          # Base models and interfaces
├── services/            # Business logic services
│   ├── __init__.py
│   └── base.py          # Base service interfaces
└── strategies/          # Trading strategies
    ├── __init__.py
    └── base.py          # Base strategy classes
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Usage

```bash
# Run the application
kite-auto-trading --config config.yaml

# Run in dry-run mode
kite-auto-trading --dry-run --config config.yaml
```

## Development Status

This project is currently under development. The basic structure and interfaces have been established.

## Requirements

- Python 3.8+
- Zerodha Kite Connect API access
- Valid API credentials

## License

MIT License