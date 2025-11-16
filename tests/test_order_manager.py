"""
Unit tests for OrderManager - order lifecycle management.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from kite_auto_trading.services.order_manager import (
    OrderManager,
    OrderUpdate,
    OrderRecord,
    OrderValidationError,
    OrderExecutionError,
)
from kite_auto_trading.models.base import (
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
    OrderExecutor,
)


class MockOrderExecutor(OrderExecutor):
    """Mock implementation of OrderExecutor for testing."""
    
    def __init__(self):
        self.placed_orders = []
        self.cancelled_orders = []
        self.modified_orders = []
        self.should_fail = False
        self.order_counter = 1000
    
    def place_order(self, order: Order) -> str:
        """Mock place order."""
        if self.should_fail:
            raise Exception("Mock execution failure")
        
        exchange_order_id = f"EXC_{self.order_counter}"
        self.order_counter += 1
        self.placed_orders.append((order, exchange_order_id))
        return exchange_order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Mock cancel order."""
        if self.should_fail:
            return False
        self.cancelled_orders.append(order_id)
        return True
    
    def modify_order(self, order_id: str, modifications: dict) -> bool:
        """Mock modify order."""
        if self.should_fail:
            return False
        self.modified_orders.append((order_id, modifications))
        return True
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Mock get order status."""
        return OrderStatus.OPEN


@pytest.fixture
def mock_executor():
    """Create mock executor."""
    return MockOrderExecutor()


@pytest.fixture
def order_manager(mock_executor):
    """Create OrderManager with mock executor."""
    manager = OrderManager(
        executor=mock_executor,
        max_retries=3,
        retry_delay=0.1,
        enable_queue_processing=False  # Disable for synchronous testing
    )
    yield manager
    manager.shutdown()


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        instrument="SBIN",
        transaction_type=TransactionType.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        strategy_id="test_strategy"
    )


class TestOrderValidation:
    """Test order validation logic."""
    
    def test_valid_market_order(self, order_manager, sample_order):
        """Test validation of valid market order."""
        # Should not raise exception
        order_manager._validate_order(sample_order)
    
    def test_valid_limit_order(self, order_manager):
        """Test validation of valid limit order."""
        order = Order(
            instrument="RELIANCE",
            transaction_type=TransactionType.BUY,
            quantity=5,
            order_type=OrderType.LIMIT,
            price=2500.0
        )
        order_manager._validate_order(order)
    
    def test_valid_sl_order(self, order_manager):
        """Test validation of valid stop-loss order."""
        order = Order(
            instrument="INFY",
            transaction_type=TransactionType.SELL,
            quantity=20,
            order_type=OrderType.SL,
            price=1400.0,
            trigger_price=1350.0  # For SELL SL, trigger should be less than price
        )
        order_manager._validate_order(order)
    
    def test_missing_instrument(self, order_manager):
        """Test validation fails for missing instrument."""
        order = Order(
            instrument="",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        with pytest.raises(OrderValidationError, match="Instrument is required"):
            order_manager._validate_order(order)
    
    def test_invalid_quantity(self, order_manager):
        """Test validation fails for invalid quantity."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=0,
            order_type=OrderType.MARKET
        )
        with pytest.raises(OrderValidationError, match="Quantity must be positive"):
            order_manager._validate_order(order)
    
    def test_limit_order_missing_price(self, order_manager):
        """Test validation fails for limit order without price."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=None
        )
        with pytest.raises(OrderValidationError, match="price is required"):
            order_manager._validate_order(order)
    
    def test_sl_order_missing_trigger_price(self, order_manager):
        """Test validation fails for SL order without trigger price."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.SL,
            price=100.0,
            trigger_price=None
        )
        with pytest.raises(OrderValidationError, match="trigger price is required"):
            order_manager._validate_order(order)
    
    def test_sl_order_invalid_price_relationship_buy(self, order_manager):
        """Test validation fails for BUY SL order with invalid price relationship."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.SL,
            price=110.0,
            trigger_price=100.0  # Should be greater than price
        )
        with pytest.raises(OrderValidationError, match="trigger price must be greater"):
            order_manager._validate_order(order)
    
    def test_sl_order_invalid_price_relationship_sell(self, order_manager):
        """Test validation fails for SELL SL order with invalid price relationship."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.SELL,
            quantity=10,
            order_type=OrderType.SL,
            price=90.0,
            trigger_price=100.0  # Should be less than price
        )
        with pytest.raises(OrderValidationError, match="trigger price must be less"):
            order_manager._validate_order(order)


class TestOrderSubmission:
    """Test order submission and tracking."""
    
    def test_submit_order_success(self, order_manager, mock_executor, sample_order):
        """Test successful order submission."""
        order_id = order_manager.submit_order(sample_order)
        
        assert order_id is not None
        assert order_id.startswith("ORD_")
        assert order_id in order_manager._orders
        assert order_id in order_manager._pending_orders
    
    def test_submit_order_generates_id(self, order_manager, sample_order):
        """Test that order ID is generated if not provided."""
        assert sample_order.order_id is None
        
        order_id = order_manager.submit_order(sample_order)
        
        assert order_id is not None
        assert sample_order.order_id == order_id
    
    def test_submit_order_validation_failure(self, order_manager):
        """Test order submission fails validation."""
        invalid_order = Order(
            instrument="",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        with pytest.raises(OrderValidationError):
            order_manager.submit_order(invalid_order)
    
    def test_submit_order_skip_validation(self, order_manager):
        """Test order submission with validation skipped."""
        invalid_order = Order(
            instrument="",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        # Should not raise exception when validation is disabled
        order_id = order_manager.submit_order(invalid_order, validate=False)
        assert order_id is not None
    
    def test_execute_order_success(self, order_manager, mock_executor, sample_order):
        """Test successful order execution."""
        order_id = order_manager.submit_order(sample_order)
        
        # Manually execute (since queue processing is disabled)
        order_manager._execute_order(order_id)
        
        # Check executor was called
        assert len(mock_executor.placed_orders) == 1
        placed_order, exchange_id = mock_executor.placed_orders[0]
        assert placed_order.instrument == "SBIN"
        assert exchange_id.startswith("EXC_")
        
        # Check order record updated
        record = order_manager.get_order_record(order_id)
        assert record is not None
        assert len(record.status_history) > 0
    
    def test_execute_order_with_retry(self, order_manager, mock_executor, sample_order):
        """Test order execution with retry on failure."""
        order_id = order_manager.submit_order(sample_order)
        
        # Make first attempt fail
        mock_executor.should_fail = True
        order_manager._execute_order(order_id)
        
        # Check retry was queued
        record = order_manager.get_order_record(order_id)
        assert record.retry_count == 1
        
        # Make second attempt succeed
        mock_executor.should_fail = False
        order_manager._execute_order(order_id)
        
        # Check order was placed
        assert len(mock_executor.placed_orders) == 1
    
    def test_execute_order_max_retries_exceeded(self, order_manager, mock_executor, sample_order):
        """Test order rejection after max retries."""
        order_id = order_manager.submit_order(sample_order)
        
        # Make all attempts fail
        mock_executor.should_fail = True
        
        # Execute with retries
        for _ in range(order_manager.max_retries):
            order_manager._execute_order(order_id)
        
        # Check order was rejected
        status = order_manager.get_order_status(order_id)
        assert status == OrderStatus.REJECTED
        
        # Check statistics
        stats = order_manager.get_statistics()
        assert stats['total_rejected'] == 1


class TestOrderModification:
    """Test order modification functionality."""
    
    def test_modify_order_quantity(self, order_manager, mock_executor, sample_order):
        """Test modifying order quantity."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        # Modify quantity
        success = order_manager.modify_order(order_id, quantity=20)
        
        assert success is True
        assert len(mock_executor.modified_orders) == 1
        
        # Check order was updated
        order = order_manager.get_order(order_id)
        assert order.quantity == 20
    
    def test_modify_order_price(self, order_manager, mock_executor):
        """Test modifying order price."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=500.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        # Modify price
        success = order_manager.modify_order(order_id, price=510.0)
        
        assert success is True
        
        # Check order was updated
        updated_order = order_manager.get_order(order_id)
        assert updated_order.price == 510.0
    
    def test_modify_order_multiple_fields(self, order_manager, mock_executor):
        """Test modifying multiple order fields."""
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=500.0
        )
        
        order_id = order_manager.submit_order(order)
        order_manager._execute_order(order_id)
        
        # Modify multiple fields
        success = order_manager.modify_order(
            order_id,
            quantity=15,
            price=505.0
        )
        
        assert success is True
        
        # Check modifications
        _, modifications = mock_executor.modified_orders[0]
        assert modifications['quantity'] == 15
        assert modifications['price'] == 505.0
    
    def test_modify_order_not_found(self, order_manager):
        """Test modifying non-existent order."""
        success = order_manager.modify_order("INVALID_ID", quantity=20)
        assert success is False
    
    def test_modify_completed_order(self, order_manager, sample_order):
        """Test cannot modify completed order."""
        order_id = order_manager.submit_order(sample_order)
        
        # Mark as complete
        order_manager._update_order_status(order_id, OrderStatus.COMPLETE)
        
        # Try to modify
        success = order_manager.modify_order(order_id, quantity=20)
        assert success is False
    
    def test_modify_order_invalid_quantity(self, order_manager, mock_executor, sample_order):
        """Test modification fails with invalid quantity."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        # Try to modify with invalid quantity
        success = order_manager.modify_order(order_id, quantity=0)
        assert success is False


class TestOrderCancellation:
    """Test order cancellation functionality."""
    
    def test_cancel_order_success(self, order_manager, mock_executor, sample_order):
        """Test successful order cancellation."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        # Cancel order
        success = order_manager.cancel_order(order_id)
        
        assert success is True
        assert len(mock_executor.cancelled_orders) == 1
        
        # Check order status
        status = order_manager.get_order_status(order_id)
        assert status == OrderStatus.CANCELLED
        
        # Check statistics
        stats = order_manager.get_statistics()
        assert stats['total_cancelled'] == 1
    
    def test_cancel_order_not_found(self, order_manager):
        """Test cancelling non-existent order."""
        success = order_manager.cancel_order("INVALID_ID")
        assert success is False
    
    def test_cancel_completed_order(self, order_manager, sample_order):
        """Test cannot cancel completed order."""
        order_id = order_manager.submit_order(sample_order)
        
        # Mark as complete
        order_manager._update_order_status(order_id, OrderStatus.COMPLETE)
        
        # Try to cancel
        success = order_manager.cancel_order(order_id)
        assert success is False
    
    def test_cancel_order_executor_failure(self, order_manager, mock_executor, sample_order):
        """Test cancellation when executor fails."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._execute_order(order_id)
        
        # Make executor fail
        mock_executor.should_fail = True
        
        # Try to cancel
        success = order_manager.cancel_order(order_id)
        assert success is False


class TestOrderTracking:
    """Test order tracking and querying."""
    
    def test_get_order_status(self, order_manager, sample_order):
        """Test getting order status."""
        order_id = order_manager.submit_order(sample_order)
        
        status = order_manager.get_order_status(order_id)
        assert status == OrderStatus.PENDING
    
    def test_get_order(self, order_manager, sample_order):
        """Test getting order details."""
        order_id = order_manager.submit_order(sample_order)
        
        order = order_manager.get_order(order_id)
        assert order is not None
        assert order.instrument == "SBIN"
        assert order.quantity == 10
    
    def test_get_order_record(self, order_manager, sample_order):
        """Test getting complete order record."""
        order_id = order_manager.submit_order(sample_order)
        
        record = order_manager.get_order_record(order_id)
        assert record is not None
        assert record.order.instrument == "SBIN"
        assert record.submitted_at is not None
        assert isinstance(record.status_history, list)
    
    def test_get_all_orders(self, order_manager):
        """Test getting all orders."""
        # Submit multiple orders
        for i in range(3):
            order = Order(
                instrument=f"STOCK{i}",
                transaction_type=TransactionType.BUY,
                quantity=10,
                order_type=OrderType.MARKET
            )
            order_manager.submit_order(order)
        
        all_orders = order_manager.get_all_orders()
        assert len(all_orders) == 3
    
    def test_get_orders_by_status(self, order_manager):
        """Test filtering orders by status."""
        # Submit orders
        order1_id = order_manager.submit_order(Order(
            instrument="STOCK1",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        ))
        
        order2_id = order_manager.submit_order(Order(
            instrument="STOCK2",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        ))
        
        # Update one to complete
        order_manager._update_order_status(order1_id, OrderStatus.COMPLETE)
        
        # Get pending orders
        pending = order_manager.get_pending_orders()
        assert len(pending) == 1
        assert pending[0].instrument == "STOCK2"
        
        # Get completed orders
        completed = order_manager.get_all_orders(OrderStatus.COMPLETE)
        assert len(completed) == 1
        assert completed[0].instrument == "STOCK1"
    
    def test_get_pending_orders(self, order_manager, sample_order):
        """Test getting pending orders."""
        order_manager.submit_order(sample_order)
        
        pending = order_manager.get_pending_orders()
        assert len(pending) == 1
        assert pending[0].status == OrderStatus.PENDING
    
    def test_get_open_orders(self, order_manager, sample_order):
        """Test getting open orders."""
        order_id = order_manager.submit_order(sample_order)
        order_manager._update_order_status(order_id, OrderStatus.OPEN)
        
        open_orders = order_manager.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0].status == OrderStatus.OPEN


class TestOrderUpdates:
    """Test order update handling."""
    
    def test_update_order_from_exchange(self, order_manager, sample_order):
        """Test updating order from exchange update."""
        order_id = order_manager.submit_order(sample_order)
        
        # Create update
        update = OrderUpdate(
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            filled_quantity=10,
            average_price=500.0,
            message="Order filled"
        )
        
        # Apply update
        order_manager.update_order_from_exchange(update)
        
        # Check order was updated
        order = order_manager.get_order(order_id)
        assert order.status == OrderStatus.COMPLETE
        
        record = order_manager.get_order_record(order_id)
        assert record.filled_quantity == 10
        assert record.average_price == 500.0
    
    def test_order_callbacks(self, order_manager, sample_order):
        """Test order update callbacks."""
        callback_called = []
        
        def test_callback(update: OrderUpdate):
            callback_called.append(update)
        
        # Register callback
        order_manager.register_callback(test_callback)
        
        # Submit and update order
        order_id = order_manager.submit_order(sample_order)
        
        update = OrderUpdate(
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            filled_quantity=10,
            average_price=500.0
        )
        
        order_manager.update_order_from_exchange(update)
        
        # Check callback was called
        assert len(callback_called) > 0
        assert callback_called[-1].order_id == order_id
        assert callback_called[-1].status == OrderStatus.COMPLETE


class TestStatistics:
    """Test order statistics."""
    
    def test_initial_statistics(self, order_manager):
        """Test initial statistics are zero."""
        stats = order_manager.get_statistics()
        
        assert stats['total_submitted'] == 0
        assert stats['total_completed'] == 0
        assert stats['total_cancelled'] == 0
        assert stats['total_rejected'] == 0
        assert stats['pending_count'] == 0
        assert stats['total_orders'] == 0
    
    def test_statistics_after_operations(self, order_manager, mock_executor):
        """Test statistics are updated correctly."""
        # Submit orders
        order1_id = order_manager.submit_order(Order(
            instrument="STOCK1",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        ))
        
        order2_id = order_manager.submit_order(Order(
            instrument="STOCK2",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        ))
        
        # Execute orders
        order_manager._execute_order(order1_id)
        order_manager._execute_order(order2_id)
        
        # Complete one, cancel another
        order_manager.update_order_from_exchange(OrderUpdate(
            order_id=order1_id,
            status=OrderStatus.COMPLETE,
            filled_quantity=10,
            average_price=500.0
        ))
        
        order_manager.cancel_order(order2_id)
        
        # Check statistics
        stats = order_manager.get_statistics()
        assert stats['total_submitted'] == 2
        assert stats['total_completed'] == 1
        assert stats['total_cancelled'] == 1
        assert stats['total_orders'] == 2


class TestQueueProcessing:
    """Test order queue processing."""
    
    def test_queue_processing_start_stop(self, mock_executor):
        """Test starting and stopping queue processing."""
        manager = OrderManager(
            executor=mock_executor,
            enable_queue_processing=True
        )
        
        # Check thread is running
        assert manager._queue_processor_thread is not None
        assert manager._queue_processor_thread.is_alive()
        
        # Stop processing
        manager.stop_queue_processing()
        
        # Wait a bit for thread to stop
        time.sleep(0.5)
        
        assert not manager._queue_processor_thread.is_alive()
        
        manager.shutdown()
    
    def test_queue_processing_executes_orders(self, mock_executor):
        """Test queue processor executes orders automatically."""
        manager = OrderManager(
            executor=mock_executor,
            enable_queue_processing=True
        )
        
        # Submit order
        order = Order(
            instrument="SBIN",
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET
        )
        
        order_id = manager.submit_order(order)
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check order was executed
        assert len(mock_executor.placed_orders) == 1
        
        manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
