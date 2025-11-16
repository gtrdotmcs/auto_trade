"""
Unit tests for portfolio management system.
"""

import pytest
from datetime import datetime, timedelta
from kite_auto_trading.services.portfolio_manager import (
    PortfolioManager,
    Position,
    Trade,
    PortfolioSnapshot,
)
from kite_auto_trading.models.base import TransactionType


class TestPortfolioManager:
    """Test suite for PortfolioManager."""
    
    def test_initialization(self):
        """Test portfolio manager initialization."""
        portfolio = PortfolioManager(initial_capital=100000.0)
        
        assert portfolio.initial_capital == 100000.0
        assert portfolio.get_cash_balance() == 100000.0
        assert portfolio.get_portfolio_value() == 100000.0
        assert len(portfolio.get_positions()) == 0
    
    def test_buy_position(self):
        """Test opening a long position."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Buy 100 shares at 500
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'strategy_id': 'STRATEGY1',
            'commission': 0.0,
            'tax': 0.0,
        }
        
        portfolio.update_position(trade)
        
        # Check position
        position = portfolio.get_position('RELIANCE')
        assert position is not None
        assert position.quantity == 100
        assert position.average_price == 500.0
        assert position.current_price == 500.0
        
        # Check cash balance
        assert portfolio.get_cash_balance() == 50000.0  # 100000 - (100 * 500)
        
        # Check portfolio value
        assert portfolio.get_portfolio_value() == 100000.0  # 50000 cash + 50000 position
    
    def test_sell_position(self):
        """Test closing a long position."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Buy 100 shares at 500
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Sell 100 shares at 550
        sell_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 100,
            'price': 550.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade)
        
        # Check position is closed
        position = portfolio.get_position('RELIANCE')
        assert position is None
        
        # Check realized P&L
        assert portfolio.calculate_realized_pnl() == 5000.0  # (550 - 500) * 100
        
        # Check cash balance
        assert portfolio.get_cash_balance() == 105000.0  # 100000 - 50000 + 55000
    
    def test_partial_position_close(self):
        """Test partially closing a position."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Buy 100 shares at 500
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Sell 50 shares at 550
        sell_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 50,
            'price': 550.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade)
        
        # Check position still exists with reduced quantity
        position = portfolio.get_position('RELIANCE')
        assert position is not None
        assert position.quantity == 50
        assert position.average_price == 500.0  # Average price unchanged
        
        # Check realized P&L
        assert portfolio.calculate_realized_pnl() == 2500.0  # (550 - 500) * 50
    
    def test_average_price_calculation(self):
        """Test average price calculation when adding to position."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Buy 100 shares at 500
        trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade1)
        
        # Buy 50 more shares at 600
        trade2 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 50,
            'price': 600.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade2)
        
        # Check position
        position = portfolio.get_position('RELIANCE')
        assert position.quantity == 150
        # Average price = (100*500 + 50*600) / 150 = 533.33
        assert abs(position.average_price - 533.33) < 0.01
    
    def test_unrealized_pnl_calculation(self):
        """Test unrealized P&L calculation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Buy 100 shares at 500
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade)
        
        # Update market price to 550
        portfolio.update_market_price('RELIANCE', 550.0)
        
        # Check unrealized P&L
        position = portfolio.get_position('RELIANCE')
        assert position.unrealized_pnl == 5000.0  # (550 - 500) * 100
        assert portfolio.calculate_unrealized_pnl() == 5000.0
    
    def test_commission_and_tax_calculation(self):
        """Test commission and tax calculation."""
        portfolio = PortfolioManager(
            initial_capital=100000.0,
            commission_rate=0.001,  # 0.1%
            tax_rate=0.0005  # 0.05%
        )
        
        # Buy 100 shares at 500
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
        }
        portfolio.update_position(trade)
        
        # Check costs
        trade_value = 100 * 500.0  # 50000
        expected_commission = trade_value * 0.001  # 50
        expected_tax = trade_value * 0.0005  # 25
        
        summary = portfolio.get_portfolio_summary()
        assert abs(summary['total_commission'] - expected_commission) < 0.01
        assert abs(summary['total_tax'] - expected_tax) < 0.01
        
        # Check cash balance includes costs
        expected_cash = 100000.0 - trade_value - expected_commission - expected_tax
        assert abs(portfolio.get_cash_balance() - expected_cash) < 0.01
    
    def test_multiple_positions(self):
        """Test managing multiple positions."""
        portfolio = PortfolioManager(initial_capital=200000.0, commission_rate=0.0)
        
        # Buy RELIANCE
        trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade1)
        
        # Buy TCS
        trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.BUY,
            'quantity': 50,
            'price': 1000.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade2)
        
        # Check positions
        positions = portfolio.get_positions()
        assert len(positions) == 2
        
        # Check individual positions
        reliance_pos = portfolio.get_position('RELIANCE')
        assert reliance_pos.quantity == 100
        
        tcs_pos = portfolio.get_position('TCS')
        assert tcs_pos.quantity == 50
        
        # Check total positions value
        expected_value = (100 * 500.0) + (50 * 1000.0)  # 100000
        assert portfolio.get_positions_value() == expected_value
    
    def test_portfolio_summary(self):
        """Test portfolio summary generation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Execute some trades
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Update market price
        portfolio.update_market_price('RELIANCE', 550.0)
        
        # Get summary
        summary = portfolio.get_portfolio_summary()
        
        assert summary['initial_capital'] == 100000.0
        assert summary['cash_balance'] == 50000.0
        assert summary['positions_value'] == 55000.0  # 100 * 550
        assert summary['total_value'] == 105000.0
        assert summary['unrealized_pnl'] == 5000.0
        assert summary['num_positions'] == 1
        assert summary['total_trades'] == 1
    
    def test_win_loss_tracking(self):
        """Test win/loss trade tracking."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Winning trade
        buy_trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade1)
        
        sell_trade1 = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 100,
            'price': 550.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade1)
        
        # Losing trade
        buy_trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.BUY,
            'quantity': 50,
            'price': 1000.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER3',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade2)
        
        sell_trade2 = {
            'instrument': 'TCS',
            'transaction_type': TransactionType.SELL,
            'quantity': 50,
            'price': 950.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER4',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade2)
        
        # Check statistics
        summary = portfolio.get_portfolio_summary()
        assert summary['winning_trades'] == 1
        assert summary['losing_trades'] == 1
        assert summary['win_rate'] == 50.0
        assert summary['largest_win'] == 5000.0
        assert summary['largest_loss'] == -2500.0
    
    def test_position_details(self):
        """Test position details retrieval."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.001)
        
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
        }
        portfolio.update_position(trade)
        
        # Update market price
        portfolio.update_market_price('RELIANCE', 550.0)
        
        # Get position details
        details = portfolio.get_position_details()
        assert len(details) == 1
        
        pos_detail = details[0]
        assert pos_detail['instrument'] == 'RELIANCE'
        assert pos_detail['quantity'] == 100
        assert pos_detail['average_price'] == 500.0
        assert pos_detail['current_price'] == 550.0
        assert pos_detail['unrealized_pnl'] == 5000.0
        assert pos_detail['pnl_pct'] == 10.0  # (550-500)/500 * 100
    
    def test_trades_history(self):
        """Test trade history retrieval."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Execute multiple trades
        for i in range(3):
            trade = {
                'instrument': 'RELIANCE',
                'transaction_type': TransactionType.BUY,
                'quantity': 10,
                'price': 500.0 + i * 10,
                'timestamp': datetime.now() + timedelta(minutes=i),
                'order_id': f'ORDER{i+1}',
                'commission': 0.0,
                'tax': 0.0,
            }
            portfolio.update_position(trade)
        
        # Get all trades
        trades = portfolio.get_trades_history()
        assert len(trades) == 3
        
        # Get trades for specific instrument
        reliance_trades = portfolio.get_trades_history(instrument='RELIANCE')
        assert len(reliance_trades) == 3
        
        # Get trades for non-existent instrument
        tcs_trades = portfolio.get_trades_history(instrument='TCS')
        assert len(tcs_trades) == 0
    
    def test_portfolio_snapshots(self):
        """Test portfolio snapshot creation."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Create initial snapshot
        snapshot1 = portfolio.create_snapshot()
        assert snapshot1.total_value == 100000.0
        assert snapshot1.num_positions == 0
        
        # Execute trade
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade)
        
        # Create second snapshot
        snapshot2 = portfolio.create_snapshot()
        assert snapshot2.total_value == 100000.0
        assert snapshot2.num_positions == 1
        
        # Get all snapshots
        snapshots = portfolio.get_snapshots()
        assert len(snapshots) == 2
    
    def test_position_reversal(self):
        """Test position reversal (long to short)."""
        portfolio = PortfolioManager(initial_capital=200000.0, commission_rate=0.0)
        
        # Buy 100 shares (long position)
        buy_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(buy_trade)
        
        # Sell 150 shares (close long and open short)
        sell_trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.SELL,
            'quantity': 150,
            'price': 550.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER2',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(sell_trade)
        
        # Check position is now short
        position = portfolio.get_position('RELIANCE')
        assert position is not None
        assert position.quantity == -50  # Short 50 shares
        assert position.average_price == 550.0
        
        # Check realized P&L from closing long position
        assert portfolio.calculate_realized_pnl() == 5000.0  # (550 - 500) * 100
    
    def test_reset_portfolio(self):
        """Test portfolio reset functionality."""
        portfolio = PortfolioManager(initial_capital=100000.0, commission_rate=0.0)
        
        # Execute trade
        trade = {
            'instrument': 'RELIANCE',
            'transaction_type': TransactionType.BUY,
            'quantity': 100,
            'price': 500.0,
            'timestamp': datetime.now(),
            'order_id': 'ORDER1',
            'commission': 0.0,
            'tax': 0.0,
        }
        portfolio.update_position(trade)
        
        # Reset portfolio
        portfolio.reset()
        
        # Check everything is reset
        assert portfolio.get_cash_balance() == 100000.0
        assert len(portfolio.get_positions()) == 0
        assert portfolio.calculate_realized_pnl() == 0.0
        assert len(portfolio.get_trades_history()) == 0
        
        summary = portfolio.get_portfolio_summary()
        assert summary['total_trades'] == 0
        assert summary['winning_trades'] == 0
        assert summary['losing_trades'] == 0


class TestPosition:
    """Test suite for Position class."""
    
    def test_position_creation(self):
        """Test position creation."""
        position = Position(
            instrument='RELIANCE',
            quantity=100,
            average_price=500.0,
            current_price=500.0,
            strategy_id='STRATEGY1',
            entry_time=datetime.now(),
            last_update_time=datetime.now()
        )
        
        assert position.instrument == 'RELIANCE'
        assert position.quantity == 100
        assert position.average_price == 500.0
        assert position.unrealized_pnl == 0.0
    
    def test_update_current_price(self):
        """Test updating current price."""
        position = Position(
            instrument='RELIANCE',
            quantity=100,
            average_price=500.0,
            current_price=500.0,
            strategy_id='STRATEGY1',
            entry_time=datetime.now(),
            last_update_time=datetime.now()
        )
        
        # Update price
        position.update_current_price(550.0)
        
        assert position.current_price == 550.0
        assert position.unrealized_pnl == 5000.0  # (550 - 500) * 100
    
    def test_position_value_calculation(self):
        """Test position value calculation."""
        position = Position(
            instrument='RELIANCE',
            quantity=100,
            average_price=500.0,
            current_price=550.0,
            strategy_id='STRATEGY1',
            entry_time=datetime.now(),
            last_update_time=datetime.now()
        )
        
        assert position.get_position_value() == 55000.0  # 100 * 550
        assert position.get_cost_basis() == 50000.0  # 100 * 500
    
    def test_net_pnl_with_costs(self):
        """Test net P&L calculation with costs."""
        position = Position(
            instrument='RELIANCE',
            quantity=100,
            average_price=500.0,
            current_price=550.0,
            strategy_id='STRATEGY1',
            entry_time=datetime.now(),
            last_update_time=datetime.now(),
            total_commission=50.0,
            total_tax=25.0
        )
        
        # Calculate unrealized P&L
        position.update_unrealized_pnl()
        
        # Unrealized P&L = 5000
        # Net P&L = 5000 - 50 - 25 = 4925
        assert position.get_net_pnl() == 4925.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
