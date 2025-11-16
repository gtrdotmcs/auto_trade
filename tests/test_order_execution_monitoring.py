"""
Integration tests for order execution monitoring.
Tests real-time order status updates, fill tracking, partial fills, 
position reconciliation, and execution reporting.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from kite_auto_trading.services.order_manager import (
    OrderManager,
    OrderUpdate,
    Fill,
    ExecutionReport,
    PositionUpdate,
)
from kite_auto_trading.models.base import (
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
    OrderExecutor,
)


class MockExecutorWithMonitoring(OrderExecutor):
    """Mock executor that simulates real-time order updates and fills."""
    
    def __init__(self):
        self.placed_orders = {}
        self.order_counter = 1000
        self.order_statuses = {}
        self.order_fills = {}
        self.should_fail = False
        self._lock = threading.Lock()
    
    def place_order(self, order: Order) -> str:
        """Mock place order with tracking."""
        if self.should_fail:
            raise Exception("Mock execution failure")
        
        with self._lock:
            exchange_order_id = f"EXC_{self.order_counter}"
            self.order_counter += 1
            
            self.placed_orders[exchange_order_id] = order
            self.order_statuses[exchange_order_id] = OrderStatus.OPEN
            self.order_fills[exchange_order_id] = {
                'filled_quantity': 0,
                'average_price': 0.0,
                'fills': [],
                'commission': 0.0
            }
            
            return exchange_order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Mock cancel order."""
        with self._lock:
            if order_id in self.order_statuses:
                self.order_statuses[order_id] = OrderStatus.CANCELLED
                return True
            return False
    
    def modify_order(self, order_id: str, modifications: dict) -> bool:
        """Mock modify order."""
        with self._lock:
            if order_id in self.placed_orders:
                order = self.placed_orders[order_id]
                for key, value in modifications.items():
                    setattr(order, key, value)
                return True
            return False
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Mock get order status."""
        with self._lock:
            return self.order_statuses.get(order_id, OrderStatus.PENDING)
    
    def simulate_fill(self, exchange_order_id: str, quantity: int, price: float):
        """Simulate a fill for testing."""
        with self._lock:
            if exchange_order_id not in self.order_fills:
                return
            
            fill_data = self.order_fills[exchange_order_id]
            order = self.placed_orders[exchange_order_id]
            
            # Add fill
            fill_data['fills'].append({
                'quantity': quantity,
                'price': price,
                'timestamp': datetime.now()
            })
            
            # Update filled quantity
            fill_data['filled_quantity'] += quantity
            
            # Calculate average price
            total_value = sum(f['quantity'] * f['price'] for f in fill_data['fills'])
            fill_data['average_price'] = total_value / fill_data['filled_quantity']
            
            # Update status
            if fill_data['filled_quantity'] >= order.quantity:
                self.order_statuses[exchange_order_id] = OrderStatus.COMPLETE
            else:
                self.order_statuses[exchange_order_id] = OrderStatus.OPEN
    
    def get_order_details(self, exchange_order_id: str) -> dict:
        """Get detailed order information."""
        with self._lock:
            if exchange_order_id not in self.order_fills:
                return {}
            
            return {
                'status': self.order_statuses.get(exchange_order_id, OrderStatus.PENDING),
                'filled_quantity': self.order_fills[exchange_order_id]['filled_quantity'],
                'average_price': self.order_fills[exchange_order_id]['average_price'],
                'fills': self.order_fills[exchange_order_id]['fills'],
                'commission': self.order_fills[exchange_order_id]['commission'],
                'last_update_time': datetime.now()
            }


@pytest.fixture
def mock_executor():
    """Create mock executor with monitoring support."""
    return MockExecutorWithMonitoring()


@pytest.fixture
def order_manager(mock_executor):
    """Create OrderManager with monitoring enabled."""
    manager = OrderManager(
        executor=mock_executor,
        max_retries=3,
        retry_delay=0.1,
        enable_queue_processing=False
    )
    yield manager
    manager.shutdown()


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        instrument="SBIN",
        transaction_type=TransactionType.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=500.0,
        strategy_id="test_strategy"
    )


class TestRealTimeOrderStatusUpdates:
    """Test real-time order status updates."""
    
    def test_order_status_update_from_exchange(self, order_manager, sample_order):
        """Test updating order status from exchange."""
        order_id = order_manager.submit_order(sample_order)
        
        # Create status update
        update = OrderUpdate(
            order_id=order_id,
            status=OrderStatus.OPEN,
            filled_quantity=0,
            average_price=0.0,
            message="Order accepted by exchange"
        )
        
        order_manager.update_order_from_exchange(update)
        
        # Verify status updated
        assert order_manager.get_order_status(order_id) == OrderStatus.OPEN
        
        # Verify update in history
        record = order_manager.get_order_record(order_id)
        assert len(record.status_history) > 0
        assert any(u.status == OrderStatus.OPEN for u in record.status_history)
    
    def test_multiple_status_updates(self, order_manager, sample_order):
        """Test multiple status updates for an order."""
        order_id = order_manager.submit_order(sample_order)
        
        # Simulate status progression
        statuses = [
            (OrderStatus.OPEN, "Order placed"),
            (OrderStatus.OPEN, "Partially filled"),
            (OrderStatus.COMPLETE, "Order completed")
        ]
        
        for status, message in statuses:
            update = OrderUpdate(
                order_id=order_id,
                status=status,
                message=message
            )
            order_manager.update_order_from_exchange(update)
        
        # Verify final status
        assert order_manager.get_order_status(order_id) == OrderStatus.COMPLETE
        
        # Verify all updates recorded
        record = order_manager.get_order_record(order_id)
        assert len(record.status_history) >= 3
    
    def test_status_update_callbacks(self, order_manager, sample_order):
        """Test callbacks are triggered on status updates."""
        callback_updates = []
        
        def status_callback(update: OrderUpdate):
            callback_updates.append(update)
        
        order_manager.register_callback(status_callback)
        
        order_id = order_manager.submit_order(sample_order)
        
        # Send status update
        update = OrderUpdate(
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            filled_quantity=100,
            average_price=500.0
        )
        order_manager.update_order_from_exchange(update)
        
        # Verify callback was called
        assert len(callback_updates) > 0
        assert any(u.status == OrderStatus.COMPLETE for u in callback_updates)


class TestFillTracking:
    """Test fill tracking functionality."""
    
    def test_single_fill_processing(self, order_manager, sample_order):
        """Test processing a single complete fill."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        # Get exchange order ID
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        assert exchange_order_id is not None
        
        # Create fill
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=100,
            price=500.0,
            timestamp=datetime.now()
        )
        
        order_manager.process_fill(fill)
        
        # Verify fill recorded
        record = order_manager.get_order_record(order_id)
        assert len(record.fills) == 1
        assert record.filled_quantity == 100
        assert record.average_price == 500.0
        assert record.order.status == OrderStatus.COMPLETE
    
    def test_partial_fill_processing(self, order_manager):
        """Test processing partial fills."""
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            price=2500.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        # Get exchange order ID
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # First partial fill
        fill1 = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=40,
            price=2500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill1)
        
        # Verify partial fill
        record = order_manager.get_order_record(order_id)
        assert record.filled_quantity == 40
        assert record.order.status == OrderStatus.OPEN
        
        # Second partial fill
        fill2 = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_002",
            quantity=60,
            price=2505.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill2)
        
        # Verify complete
        record = order_manager.get_order_record(order_id)
        assert record.filled_quantity == 100
        assert record.order.status == OrderStatus.COMPLETE
        assert len(record.fills) == 2
    
    def test_average_price_calculation(self, order_manager):
        """Test average price calculation with multiple fills."""
        order = Order(
            instrument="INFY",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1500.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # Multiple fills at different prices
        fills = [
            (30, 1500.0),
            (40, 1505.0),
            (30, 1510.0)
        ]
        
        for i, (qty, price) in enumerate(fills):
            fill = Fill(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                fill_id=f"FILL_{i+1:03d}",
                quantity=qty,
                price=price,
                timestamp=datetime.now()
            )
            order_manager.process_fill(fill)
        
        # Calculate expected average
        total_value = sum(qty * price for qty, price in fills)
        expected_avg = total_value / 100
        
        record = order_manager.get_order_record(order_id)
        assert abs(record.average_price - expected_avg) < 0.01
    
    def test_fill_callbacks(self, order_manager, sample_order):
        """Test fill callbacks are triggered."""
        fill_notifications = []
        
        def fill_callback(fill: Fill):
            fill_notifications.append(fill)
        
        order_manager.register_fill_callback(fill_callback)
        
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=100,
            price=500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Verify callback was called
        assert len(fill_notifications) == 1
        assert fill_notifications[0].quantity == 100


class TestPositionReconciliation:
    """Test position reconciliation functionality."""
    
    def test_position_update_from_buy_fill(self, order_manager):
        """Test position update from buy order fill."""
        order = Order(
            instrument="TCS",
            transaction_type=TransactionType.BUY,
            quantity=50,
            order_type=OrderType.MARKET,
            price=3500.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=50,
            price=3500.0,
            timestamp=datetime.now()
        )
        
        order_manager.process_fill(fill)
        
        # Verify position
        positions = order_manager.get_position_summary("TCS")
        assert "TCS" in positions
        position = positions["TCS"]
        assert position.net_quantity == 50
        assert position.average_price == 3500.0
    
    def test_position_update_from_sell_fill(self, order_manager):
        """Test position update from sell order fill."""
        # First buy to establish position
        buy_order = Order(
            instrument="HDFC",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1600.0
        )
        
        buy_id = order_manager.submit_order(buy_order)
        order_manager._execute_order(buy_id)
        
        record = order_manager.get_order_record(buy_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        buy_fill = Fill(
            order_id=buy_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_BUY",
            quantity=100,
            price=1600.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(buy_fill)
        
        # Now sell
        sell_order = Order(
            instrument="HDFC",
            transaction_type=TransactionType.SELL,
            quantity=60,
            order_type=OrderType.MARKET,
            price=1650.0
        )
        
        sell_id = order_manager.submit_order(sell_order)
        order_manager._execute_order(sell_id)
        
        record = order_manager.get_order_record(sell_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        sell_fill = Fill(
            order_id=sell_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_SELL",
            quantity=60,
            price=1650.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(sell_fill)
        
        # Verify position reduced
        positions = order_manager.get_position_summary("HDFC")
        position = positions["HDFC"]
        assert position.net_quantity == 40
        assert position.average_price == 1600.0  # Original avg price maintained
    
    def test_realized_pnl_calculation(self, order_manager):
        """Test realized P&L calculation when closing position."""
        # Buy at 1000
        buy_order = Order(
            instrument="WIPRO",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1000.0
        )
        
        buy_id = order_manager.submit_order(buy_order)
        order_manager._execute_order(buy_id)
        
        record = order_manager.get_order_record(buy_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        buy_fill = Fill(
            order_id=buy_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_BUY",
            quantity=100,
            price=1000.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(buy_fill)
        
        # Sell at 1100 (profit of 100 per share)
        sell_order = Order(
            instrument="WIPRO",
            transaction_type=TransactionType.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1100.0
        )
        
        sell_id = order_manager.submit_order(sell_order)
        order_manager._execute_order(sell_id)
        
        record = order_manager.get_order_record(sell_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        sell_fill = Fill(
            order_id=sell_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_SELL",
            quantity=100,
            price=1100.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(sell_fill)
        
        # Verify realized P&L
        positions = order_manager.get_position_summary("WIPRO")
        position = positions["WIPRO"]
        assert position.net_quantity == 0
        assert position.realized_pnl == 10000.0  # 100 shares * 100 profit
    
    def test_position_callbacks(self, order_manager):
        """Test position update callbacks."""
        position_updates = []
        
        def position_callback(position: PositionUpdate):
            position_updates.append(position)
        
        order_manager.register_position_callback(position_callback)
        
        order = Order(
            instrument="ICICI",
            transaction_type=TransactionType.BUY,
            quantity=50,
            order_type=OrderType.MARKET,
            price=900.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=50,
            price=900.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Verify callback was called
        assert len(position_updates) > 0
        assert any(p.instrument == "ICICI" for p in position_updates)
    
    def test_broker_position_reconciliation_match(self, order_manager):
        """Test position reconciliation when positions match."""
        # Create internal position
        order = Order(
            instrument="AXIS",
            transaction_type=TransactionType.BUY,
            quantity=75,
            order_type=OrderType.MARKET,
            price=800.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=75,
            price=800.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Broker position matches
        broker_position = {
            'net_quantity': 75,
            'average_price': 800.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0
        }
        
        # Reconcile
        match = order_manager.reconcile_position_with_broker("AXIS", broker_position)
        assert match is True
    
    def test_broker_position_reconciliation_mismatch(self, order_manager):
        """Test position reconciliation when positions don't match."""
        # Create internal position
        order = Order(
            instrument="KOTAK",
            transaction_type=TransactionType.BUY,
            quantity=50,
            order_type=OrderType.MARKET,
            price=1800.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=50,
            price=1800.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Broker position differs
        broker_position = {
            'net_quantity': 60,  # Different quantity
            'average_price': 1800.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0
        }
        
        # Reconcile
        match = order_manager.reconcile_position_with_broker("KOTAK", broker_position)
        assert match is False


class TestExecutionReporting:
    """Test execution reporting and audit trail."""
    
    def test_execution_report_generation(self, order_manager, sample_order):
        """Test generating execution report for completed order."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # Process fill
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=100,
            price=500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Get execution report
        report = order_manager.get_execution_report(order_id)
        
        assert report is not None
        assert report.order_id == order_id
        assert report.instrument == "SBIN"
        assert report.total_quantity == 100
        assert report.filled_quantity == 100
        assert report.remaining_quantity == 0
        assert report.average_fill_price == 500.0
        assert report.status == OrderStatus.COMPLETE
        assert len(report.fills) == 1
    
    def test_execution_report_with_partial_fills(self, order_manager):
        """Test execution report with multiple partial fills."""
        order = Order(
            instrument="TATAMOTORS",
            transaction_type=TransactionType.BUY,
            quantity=200,
            order_type=OrderType.LIMIT,
            price=450.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # Multiple fills
        fills_data = [(80, 450.0), (70, 451.0), (50, 449.0)]
        
        for i, (qty, price) in enumerate(fills_data):
            fill = Fill(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                fill_id=f"FILL_{i+1:03d}",
                quantity=qty,
                price=price,
                timestamp=datetime.now()
            )
            order_manager.process_fill(fill)
        
        # Get execution report
        report = order_manager.get_execution_report(order_id)
        
        assert report.filled_quantity == 200
        assert len(report.fills) == 3
        assert report.status == OrderStatus.COMPLETE
        assert report.first_fill_at is not None
        assert report.completed_at is not None
    
    def test_execution_callbacks(self, order_manager, sample_order):
        """Test execution report callbacks."""
        execution_reports = []
        
        def execution_callback(report: ExecutionReport):
            execution_reports.append(report)
        
        order_manager.register_execution_callback(execution_callback)
        
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=100,
            price=500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Verify callback was called
        assert len(execution_reports) == 1
        assert execution_reports[0].order_id == order_id
    
    def test_audit_trail_generation(self, order_manager, sample_order):
        """Test audit trail generation."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # Process fill
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=100,
            price=500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Get audit trail
        audit_trail = order_manager.get_audit_trail(order_id=order_id)
        
        assert len(audit_trail) > 0
        
        # Check for different event types
        event_types = {entry['event_type'] for entry in audit_trail}
        assert 'ORDER_SUBMITTED' in event_types
        assert 'FILL' in event_types
    
    def test_audit_trail_time_filtering(self, order_manager):
        """Test audit trail with time filtering."""
        start_time = datetime.now()
        
        # Submit and process order
        order = Order(
            instrument="MARUTI",
            transaction_type=TransactionType.BUY,
            quantity=25,
            order_type=OrderType.MARKET,
            price=8000.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=25,
            price=8000.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        end_time = datetime.now()
        
        # Get audit trail with time filter
        audit_trail = order_manager.get_audit_trail(
            start_time=start_time,
            end_time=end_time
        )
        
        assert len(audit_trail) > 0
        
        # Verify all entries are within time range
        for entry in audit_trail:
            assert start_time <= entry['timestamp'] <= end_time
    
    def test_execution_summary(self, order_manager):
        """Test execution summary generation."""
        # Submit multiple orders
        instruments = ["STOCK1", "STOCK2", "STOCK3"]
        
        for instrument in instruments:
            order = Order(
                instrument=instrument,
                transaction_type=TransactionType.BUY,
                quantity=50,
                order_type=OrderType.MARKET,
                price=1000.0
            )
            
            order_id = order_manager.submit_order(order)
            order_manager._execute_order(order_id)
            
            record = order_manager.get_order_record(order_id)
            exchange_order_id = None
            for update in record.status_history:
                if update.exchange_order_id:
                    exchange_order_id = update.exchange_order_id
                    break
            
            fill = Fill(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                fill_id=f"FILL_{instrument}",
                quantity=50,
                price=1000.0,
                timestamp=datetime.now()
            )
            order_manager.process_fill(fill)
        
        # Get execution summary
        summary = order_manager.get_execution_summary()
        
        assert summary['total_orders'] == 3
        assert summary['completed_orders'] == 3
        assert len(summary['instruments_traded']) == 3
        assert summary['total_volume'] > 0
        assert summary['fill_rate'] == 1.0
    
    def test_position_reconciliation_report(self, order_manager):
        """Test position reconciliation report generation."""
        # Create positions
        instruments_data = [
            ("POS1", 100, 500.0),
            ("POS2", 50, 1000.0),
            ("POS3", 75, 750.0)
        ]
        
        for instrument, qty, price in instruments_data:
            order = Order(
                instrument=instrument,
                transaction_type=TransactionType.BUY,
                quantity=qty,
                order_type=OrderType.MARKET,
                price=price
            )
            
            order_id = order_manager.submit_order(order)
            order_manager._execute_order(order_id)
            
            record = order_manager.get_order_record(order_id)
            exchange_order_id = None
            for update in record.status_history:
                if update.exchange_order_id:
                    exchange_order_id = update.exchange_order_id
                    break
            
            fill = Fill(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                fill_id=f"FILL_{instrument}",
                quantity=qty,
                price=price,
                timestamp=datetime.now()
            )
            order_manager.process_fill(fill)
        
        # Get reconciliation report
        report = order_manager.get_position_reconciliation_report()
        
        assert report['total_positions'] == 3
        assert report['summary']['instruments_with_positions'] == 3
        assert len(report['positions']) == 3
        
        # Verify position details
        for instrument, qty, price in instruments_data:
            assert instrument in report['positions']
            pos = report['positions'][instrument]
            assert pos['net_quantity'] == qty
            assert pos['average_price'] == price


class TestCompleteExecutionFlows:
    """Integration tests for complete order execution flows."""
    
    def test_complete_market_order_flow(self, order_manager, mock_executor):
        """Test complete flow for market order execution."""
        order = Order(
            instrument="FULLFLOW",
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1000.0,
            strategy_id="integration_test"
        )
        
        # Track all events
        status_updates = []
        fills = []
        execution_reports = []
        position_updates = []
        
        order_manager.register_callback(lambda u: status_updates.append(u))
        order_manager.register_fill_callback(lambda f: fills.append(f))
        order_manager.register_execution_callback(lambda r: execution_reports.append(r))
        order_manager.register_position_callback(lambda p: position_updates.append(p))
        
        # Submit order
        order_id = order_manager.submit_order(order)
        assert order_id is not None
        
        # Execute order
        order_manager._execute_order(order_id)
        
        # Verify order was placed
        assert len(mock_executor.placed_orders) == 1
        
        # Get exchange order ID
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        assert exchange_order_id is not None
        
        # Simulate fill
        fill = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_COMPLETE",
            quantity=100,
            price=1000.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill)
        
        # Verify all callbacks were triggered
        assert len(status_updates) > 0
        assert len(fills) == 1
        assert len(execution_reports) == 1
        assert len(position_updates) > 0
        
        # Verify final state
        final_status = order_manager.get_order_status(order_id)
        assert final_status == OrderStatus.COMPLETE
        
        # Verify execution report
        report = order_manager.get_execution_report(order_id)
        assert report.filled_quantity == 100
        assert report.status == OrderStatus.COMPLETE
        
        # Verify position
        positions = order_manager.get_position_summary("FULLFLOW")
        assert "FULLFLOW" in positions
        assert positions["FULLFLOW"].net_quantity == 100
    
    def test_partial_fill_flow(self, order_manager, mock_executor):
        """Test complete flow with partial fills."""
        order = Order(
            instrument="PARTIALFILL",
            transaction_type=TransactionType.BUY,
            quantity=150,
            order_type=OrderType.LIMIT,
            price=2000.0
        )
        
        fills_received = []
        order_manager.register_fill_callback(lambda f: fills_received.append(f))
        
        # Submit and execute
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        record = order_manager.get_order_record(order_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        # First partial fill
        fill1 = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_001",
            quantity=50,
            price=2000.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill1)
        
        # Verify still open
        assert order_manager.get_order_status(order_id) == OrderStatus.OPEN
        assert len(fills_received) == 1
        
        # Second partial fill
        fill2 = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_002",
            quantity=60,
            price=2005.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill2)
        
        # Still open
        assert order_manager.get_order_status(order_id) == OrderStatus.OPEN
        assert len(fills_received) == 2
        
        # Final fill
        fill3 = Fill(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_003",
            quantity=40,
            price=1995.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(fill3)
        
        # Now complete
        assert order_manager.get_order_status(order_id) == OrderStatus.COMPLETE
        assert len(fills_received) == 3
        
        # Verify execution report
        report = order_manager.get_execution_report(order_id)
        assert report.filled_quantity == 150
        assert len(report.fills) == 3
        
        # Verify average price calculation
        expected_avg = (50*2000.0 + 60*2005.0 + 40*1995.0) / 150
        assert abs(report.average_fill_price - expected_avg) < 0.01
    
    def test_round_trip_trade_flow(self, order_manager, mock_executor):
        """Test complete round trip trade (buy then sell)."""
        instrument = "ROUNDTRIP"
        
        # Buy order
        buy_order = Order(
            instrument=instrument,
            transaction_type=TransactionType.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1500.0
        )
        
        buy_id = order_manager.submit_order(buy_order)
        order_manager._execute_order(buy_id)
        
        record = order_manager.get_order_record(buy_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        buy_fill = Fill(
            order_id=buy_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_BUY",
            quantity=100,
            price=1500.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(buy_fill)
        
        # Verify position
        positions = order_manager.get_position_summary(instrument)
        assert positions[instrument].net_quantity == 100
        assert positions[instrument].realized_pnl == 0.0
        
        # Sell order at profit
        sell_order = Order(
            instrument=instrument,
            transaction_type=TransactionType.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            price=1600.0
        )
        
        sell_id = order_manager.submit_order(sell_order)
        order_manager._execute_order(sell_id)
        
        record = order_manager.get_order_record(sell_id)
        exchange_order_id = None
        for update in record.status_history:
            if update.exchange_order_id:
                exchange_order_id = update.exchange_order_id
                break
        
        sell_fill = Fill(
            order_id=sell_id,
            exchange_order_id=exchange_order_id,
            fill_id="FILL_SELL",
            quantity=100,
            price=1600.0,
            timestamp=datetime.now()
        )
        order_manager.process_fill(sell_fill)
        
        # Verify position closed with profit
        positions = order_manager.get_position_summary(instrument)
        assert positions[instrument].net_quantity == 0
        assert positions[instrument].realized_pnl == 10000.0  # 100 * (1600 - 1500)
        
        # Verify both orders complete
        assert order_manager.get_order_status(buy_id) == OrderStatus.COMPLETE
        assert order_manager.get_order_status(sell_id) == OrderStatus.COMPLETE
        
        # Verify execution summary
        summary = order_manager.get_execution_summary()
        assert summary['total_orders'] >= 2
        assert summary['completed_orders'] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
