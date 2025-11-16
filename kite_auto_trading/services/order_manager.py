"""
Order management system for handling order lifecycle, queue processing, and execution tracking.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from queue import Queue, Empty

from kite_auto_trading.models.base import (
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
    OrderExecutor,
)


logger = logging.getLogger(__name__)


class OrderValidationError(Exception):
    """Exception raised when order validation fails."""
    pass


class OrderExecutionError(Exception):
    """Exception raised when order execution fails."""
    pass


@dataclass
class OrderUpdate:
    """Represents an order status update."""
    order_id: str
    status: OrderStatus
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""
    exchange_order_id: Optional[str] = None


@dataclass
class Fill:
    """Represents a partial or complete fill of an order."""
    order_id: str
    exchange_order_id: str
    fill_id: str
    quantity: int
    price: float
    timestamp: datetime
    exchange_timestamp: Optional[datetime] = None
    trade_id: Optional[str] = None


@dataclass
class ExecutionReport:
    """Comprehensive execution report for an order."""
    order_id: str
    exchange_order_id: str
    instrument: str
    transaction_type: TransactionType
    order_type: OrderType
    total_quantity: int
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: float
    fills: List[Fill]
    status: OrderStatus
    submitted_at: datetime
    first_fill_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_commission: float = 0.0
    slippage: float = 0.0


@dataclass
class PositionUpdate:
    """Represents a position update from order execution."""
    instrument: str
    net_quantity: int
    average_price: float
    realized_pnl: float
    unrealized_pnl: float
    timestamp: datetime


@dataclass
class OrderRecord:
    """Internal record for tracking order lifecycle."""
    order: Order
    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    filled_quantity: int = 0
    average_price: float = 0.0
    status_history: List[OrderUpdate] = field(default_factory=list)
    fills: List[Fill] = field(default_factory=list)
    retry_count: int = 0
    error_message: str = ""
    exchange_order_id: Optional[str] = None
    first_fill_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_commission: float = 0.0


class OrderManager:
    """
    Manages order lifecycle including validation, submission, tracking, and modifications.
    
    Features:
    - Order queue processing with priority handling
    - Order validation before submission
    - Status tracking and updates
    - Order modification and cancellation
    - Retry logic for failed orders
    - Thread-safe operations
    """
    
    def __init__(
        self,
        executor: OrderExecutor,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_queue_processing: bool = True
    ):
        """
        Initialize OrderManager.
        
        Args:
            executor: OrderExecutor implementation for placing orders
            max_retries: Maximum number of retry attempts for failed orders
            retry_delay: Delay in seconds between retry attempts
            enable_queue_processing: Whether to enable automatic queue processing
        """
        self.executor = executor
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Order tracking
        self._orders: Dict[str, OrderRecord] = {}
        self._order_queue: Queue = Queue()
        self._pending_orders: Set[str] = set()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Queue processing
        self._queue_processor_thread: Optional[threading.Thread] = None
        self._stop_processing = threading.Event()
        self._enable_queue_processing = enable_queue_processing
        
        # Callbacks
        self._order_callbacks: List[Callable[[OrderUpdate], None]] = []
        self._fill_callbacks: List[Callable[[Fill], None]] = []
        self._execution_callbacks: List[Callable[[ExecutionReport], None]] = []
        self._position_callbacks: List[Callable[[PositionUpdate], None]] = []
        
        # Execution monitoring
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_enabled = False
        self._monitoring_interval = 1.0  # seconds
        self._position_tracker: Dict[str, PositionUpdate] = {}
        
        # Statistics
        self._stats = {
            'total_submitted': 0,
            'total_completed': 0,
            'total_cancelled': 0,
            'total_rejected': 0,
            'total_failed': 0,
            'total_fills': 0,
            'total_volume': 0.0,
            'total_commission': 0.0,
        }
        
        if self._enable_queue_processing:
            self.start_queue_processing()
        
        logger.info("OrderManager initialized")
    
    def start_queue_processing(self) -> None:
        """Start the order queue processing thread."""
        if self._queue_processor_thread and self._queue_processor_thread.is_alive():
            logger.warning("Queue processing already running")
            return
        
        self._stop_processing.clear()
        self._queue_processor_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="OrderQueueProcessor"
        )
        self._queue_processor_thread.start()
        logger.info("Order queue processing started")
    
    def stop_queue_processing(self) -> None:
        """Stop the order queue processing thread."""
        if not self._queue_processor_thread or not self._queue_processor_thread.is_alive():
            logger.warning("Queue processing not running")
            return
        
        self._stop_processing.set()
        self._queue_processor_thread.join(timeout=5.0)
        logger.info("Order queue processing stopped")
    
    def submit_order(self, order: Order, validate: bool = True) -> str:
        """
        Submit an order for execution.
        
        Args:
            order: Order object to submit
            validate: Whether to validate order before submission
            
        Returns:
            Internal order ID for tracking
            
        Raises:
            OrderValidationError: If order validation fails
        """
        with self._lock:
            # Validate order if requested
            if validate:
                self._validate_order(order)
            
            # Generate internal order ID if not present
            if not order.order_id:
                order.order_id = self._generate_order_id()
            
            # Create order record
            record = OrderRecord(
                order=order,
                submitted_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Store order record
            self._orders[order.order_id] = record
            self._pending_orders.add(order.order_id)
            
            # Add to queue for processing
            self._order_queue.put(order.order_id)
            
            logger.info(
                f"Order submitted: {order.order_id} - "
                f"{order.transaction_type.value} {order.quantity} {order.instrument}"
            )
            
            return order.order_id
    
    def _validate_order(self, order: Order) -> None:
        """
        Validate order parameters.
        
        Args:
            order: Order to validate
            
        Raises:
            OrderValidationError: If validation fails
        """
        # Check required fields
        if not order.instrument:
            raise OrderValidationError("Instrument is required")
        
        if not order.transaction_type:
            raise OrderValidationError("Transaction type is required")
        
        if order.quantity <= 0:
            raise OrderValidationError("Quantity must be positive")
        
        # Validate order type specific requirements
        if order.order_type in [OrderType.LIMIT, OrderType.SL]:
            if order.price is None or order.price <= 0:
                raise OrderValidationError(
                    f"Valid price is required for {order.order_type.value} orders"
                )
        
        if order.order_type in [OrderType.SL, OrderType.SL_M]:
            if order.trigger_price is None or order.trigger_price <= 0:
                raise OrderValidationError(
                    f"Valid trigger price is required for {order.order_type.value} orders"
                )
        
        # Validate price relationships for stop-loss orders
        if order.order_type == OrderType.SL:
            if order.transaction_type == TransactionType.BUY:
                if order.trigger_price <= order.price:
                    raise OrderValidationError(
                        "For BUY SL orders, trigger price must be greater than limit price"
                    )
            else:  # SELL
                if order.trigger_price >= order.price:
                    raise OrderValidationError(
                        "For SELL SL orders, trigger price must be less than limit price"
                    )
    
    def _process_queue(self) -> None:
        """Process orders from the queue (runs in separate thread)."""
        logger.info("Order queue processor started")
        
        while not self._stop_processing.is_set():
            try:
                # Get order from queue with timeout
                order_id = self._order_queue.get(timeout=1.0)
                
                # Process the order
                self._execute_order(order_id)
                
                self._order_queue.task_done()
                
            except Empty:
                # No orders in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error processing order queue: {e}", exc_info=True)
        
        logger.info("Order queue processor stopped")
    
    def _execute_order(self, order_id: str) -> None:
        """
        Execute an order through the executor.
        
        Args:
            order_id: Internal order ID to execute
        """
        with self._lock:
            if order_id not in self._orders:
                logger.error(f"Order not found: {order_id}")
                return
            
            record = self._orders[order_id]
            order = record.order
        
        try:
            # Update status to OPEN (being processed)
            self._update_order_status(
                order_id,
                OrderStatus.OPEN,
                message="Order submitted to exchange"
            )
            
            # Execute through the executor
            exchange_order_id = self.executor.place_order(order)
            
            # Update order with exchange ID
            with self._lock:
                record.order.order_id = exchange_order_id
                self._pending_orders.discard(order_id)
                self._stats['total_submitted'] += 1
            
            # Create update with exchange order ID
            update = OrderUpdate(
                order_id=order_id,
                status=OrderStatus.OPEN,
                timestamp=datetime.now(),
                message="Order placed successfully",
                exchange_order_id=exchange_order_id
            )
            
            self._add_status_update(order_id, update)
            self._notify_callbacks(update)
            
            logger.info(f"Order executed successfully: {order_id} -> {exchange_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to execute order {order_id}: {e}")
            
            with self._lock:
                record.retry_count += 1
                record.error_message = str(e)
            
            # Retry if under max retries
            if record.retry_count < self.max_retries:
                logger.info(
                    f"Retrying order {order_id} "
                    f"(attempt {record.retry_count + 1}/{self.max_retries})"
                )
                time.sleep(self.retry_delay)
                self._order_queue.put(order_id)
            else:
                # Max retries exceeded, mark as rejected
                self._update_order_status(
                    order_id,
                    OrderStatus.REJECTED,
                    message=f"Order rejected after {self.max_retries} attempts: {str(e)}"
                )
                
                with self._lock:
                    self._pending_orders.discard(order_id)
                    self._stats['total_rejected'] += 1
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[OrderType] = None
    ) -> bool:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            order_type: New order type (optional)
            
        Returns:
            True if modification successful, False otherwise
        """
        with self._lock:
            if order_id not in self._orders:
                logger.error(f"Order not found: {order_id}")
                return False
            
            record = self._orders[order_id]
            order = record.order
            
            # Check if order can be modified
            if order.status in [OrderStatus.COMPLETE, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                logger.warning(f"Cannot modify order in {order.status.value} status")
                return False
            
            # Build modifications dict
            modifications = {}
            
            if quantity is not None:
                if quantity <= 0:
                    logger.error("Quantity must be positive")
                    return False
                modifications['quantity'] = quantity
                order.quantity = quantity
            
            if price is not None:
                if price <= 0:
                    logger.error("Price must be positive")
                    return False
                modifications['price'] = price
                order.price = price
            
            if trigger_price is not None:
                if trigger_price <= 0:
                    logger.error("Trigger price must be positive")
                    return False
                modifications['trigger_price'] = trigger_price
                order.trigger_price = trigger_price
            
            if order_type is not None:
                modifications['order_type'] = order_type
                order.order_type = order_type
            
            if not modifications:
                logger.warning("No modifications specified")
                return False
        
        try:
            # Get exchange order ID
            exchange_order_id = self._get_exchange_order_id(order_id)
            if not exchange_order_id:
                logger.error(f"Exchange order ID not found for {order_id}")
                return False
            
            # Modify through executor
            success = self.executor.modify_order(exchange_order_id, modifications)
            
            if success:
                self._update_order_status(
                    order_id,
                    order.status,
                    message=f"Order modified: {', '.join(modifications.keys())}"
                )
                logger.info(f"Order modified successfully: {order_id}")
            else:
                logger.warning(f"Order modification failed: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to modify order {order_id}: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        with self._lock:
            if order_id not in self._orders:
                logger.error(f"Order not found: {order_id}")
                return False
            
            record = self._orders[order_id]
            order = record.order
            
            # Check if order can be cancelled
            if order.status in [OrderStatus.COMPLETE, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                logger.warning(f"Cannot cancel order in {order.status.value} status")
                return False
        
        try:
            # Get exchange order ID
            exchange_order_id = self._get_exchange_order_id(order_id)
            if not exchange_order_id:
                logger.error(f"Exchange order ID not found for {order_id}")
                return False
            
            # Cancel through executor
            success = self.executor.cancel_order(exchange_order_id)
            
            if success:
                self._update_order_status(
                    order_id,
                    OrderStatus.CANCELLED,
                    message="Order cancelled by user"
                )
                
                with self._lock:
                    self._pending_orders.discard(order_id)
                    self._stats['total_cancelled'] += 1
                
                logger.info(f"Order cancelled successfully: {order_id}")
            else:
                logger.warning(f"Order cancellation failed: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Get current status of an order.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            OrderStatus if order exists, None otherwise
        """
        with self._lock:
            if order_id not in self._orders:
                return None
            return self._orders[order_id].order.status
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order details.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            Order object if exists, None otherwise
        """
        with self._lock:
            if order_id not in self._orders:
                return None
            return self._orders[order_id].order
    
    def get_order_record(self, order_id: str) -> Optional[OrderRecord]:
        """
        Get complete order record including history.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            OrderRecord if exists, None otherwise
        """
        with self._lock:
            if order_id not in self._orders:
                return None
            return self._orders[order_id]
    
    def get_all_orders(self, status_filter: Optional[OrderStatus] = None) -> List[Order]:
        """
        Get all orders, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of Order objects
        """
        with self._lock:
            orders = []
            for record in self._orders.values():
                if status_filter is None or record.order.status == status_filter:
                    orders.append(record.order)
            return orders
    
    def get_pending_orders(self) -> List[Order]:
        """
        Get all pending orders.
        
        Returns:
            List of pending Order objects
        """
        return self.get_all_orders(OrderStatus.PENDING)
    
    def get_open_orders(self) -> List[Order]:
        """
        Get all open orders.
        
        Returns:
            List of open Order objects
        """
        return self.get_all_orders(OrderStatus.OPEN)
    
    def update_order_from_exchange(self, update: OrderUpdate) -> None:
        """
        Update order status from exchange updates.
        
        Args:
            update: OrderUpdate with latest information from exchange
        """
        with self._lock:
            if update.order_id not in self._orders:
                logger.warning(f"Received update for unknown order: {update.order_id}")
                return
            
            record = self._orders[update.order_id]
            
            # Update order status
            record.order.status = update.status
            record.filled_quantity = update.filled_quantity
            record.average_price = update.average_price
            record.updated_at = update.timestamp
            
            # Add to history
            self._add_status_update(update.order_id, update)
            
            # Update statistics
            if update.status == OrderStatus.COMPLETE:
                self._stats['total_completed'] += 1
                self._pending_orders.discard(update.order_id)
            elif update.status == OrderStatus.CANCELLED:
                self._stats['total_cancelled'] += 1
                self._pending_orders.discard(update.order_id)
            elif update.status == OrderStatus.REJECTED:
                self._stats['total_rejected'] += 1
                self._pending_orders.discard(update.order_id)
            
            # Notify callbacks
            self._notify_callbacks(update)
            
            logger.debug(
                f"Order updated: {update.order_id} -> {update.status.value} "
                f"(filled: {update.filled_quantity}/{record.order.quantity})"
            )
    
    def register_callback(self, callback: Callable[[OrderUpdate], None]) -> None:
        """
        Register a callback for order updates.
        
        Args:
            callback: Function to call on order updates
        """
        with self._lock:
            self._order_callbacks.append(callback)
        logger.info(f"Registered order callback: {callback.__name__}")
    
    def register_fill_callback(self, callback: Callable[[Fill], None]) -> None:
        """
        Register a callback for fill updates.
        
        Args:
            callback: Function to call on fill updates
        """
        with self._lock:
            self._fill_callbacks.append(callback)
        logger.info(f"Registered fill callback: {callback.__name__}")
    
    def register_execution_callback(self, callback: Callable[[ExecutionReport], None]) -> None:
        """
        Register a callback for execution reports.
        
        Args:
            callback: Function to call on execution reports
        """
        with self._lock:
            self._execution_callbacks.append(callback)
        logger.info(f"Registered execution callback: {callback.__name__}")
    
    def register_position_callback(self, callback: Callable[[PositionUpdate], None]) -> None:
        """
        Register a callback for position updates.
        
        Args:
            callback: Function to call on position updates
        """
        with self._lock:
            self._position_callbacks.append(callback)
        logger.info(f"Registered position callback: {callback.__name__}")
    
    def start_execution_monitoring(self) -> None:
        """Start real-time execution monitoring."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Execution monitoring already running")
            return
        
        self._monitoring_enabled = True
        self._monitoring_thread = threading.Thread(
            target=self._monitor_executions,
            daemon=True,
            name="ExecutionMonitor"
        )
        self._monitoring_thread.start()
        logger.info("Execution monitoring started")
    
    def stop_execution_monitoring(self) -> None:
        """Stop real-time execution monitoring."""
        if not self._monitoring_thread or not self._monitoring_thread.is_alive():
            logger.warning("Execution monitoring not running")
            return
        
        self._monitoring_enabled = False
        self._monitoring_thread.join(timeout=5.0)
        logger.info("Execution monitoring stopped")
    
    def _monitor_executions(self) -> None:
        """Monitor order executions in real-time (runs in separate thread)."""
        logger.info("Execution monitor started")
        
        while self._monitoring_enabled:
            try:
                # Get all orders that need monitoring (OPEN and PENDING)
                monitored_orders = []
                with self._lock:
                    for order_id, record in self._orders.items():
                        if record.order.status in [OrderStatus.OPEN, OrderStatus.PENDING]:
                            exchange_id = record.exchange_order_id or self._get_exchange_order_id(order_id)
                            if exchange_id:
                                monitored_orders.append((order_id, exchange_id, record.order.status))
                
                # Check status and fills for each monitored order
                for order_id, exchange_order_id, current_status in monitored_orders:
                    try:
                        # Get latest order details from executor
                        order_details = self._get_order_details_from_executor(exchange_order_id)
                        
                        if order_details:
                            # Process status updates
                            if order_details['status'] != current_status:
                                self._handle_status_change(order_id, order_details)
                            
                            # Process any new fills
                            self._check_and_process_fills(order_id, order_details)
                            
                            # Update execution metrics
                            self._update_execution_metrics(order_id, order_details)
                    
                    except Exception as e:
                        logger.error(f"Error monitoring order {order_id}: {e}")
                        # Mark order for retry monitoring
                        self._mark_for_retry_monitoring(order_id)
                
                # Perform position reconciliation
                self._reconcile_positions()
                
                # Sleep before next check
                time.sleep(self._monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in execution monitor: {e}", exc_info=True)
                time.sleep(self._monitoring_interval)
        
        logger.info("Execution monitor stopped")
    
    def _get_order_details_from_executor(self, exchange_order_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive order details from executor."""
        try:
            # This would typically call executor methods to get:
            # - Current status
            # - Fill information
            # - Timestamps
            # - Commission details
            
            # For now, return basic status (this would be enhanced based on actual executor implementation)
            status = self.executor.get_order_status(exchange_order_id)
            
            # Mock additional details that would come from a real executor
            return {
                'status': status,
                'filled_quantity': 0,  # Would be populated by real executor
                'average_price': 0.0,  # Would be populated by real executor
                'fills': [],  # Would be populated by real executor
                'commission': 0.0,  # Would be populated by real executor
                'last_update_time': datetime.now()
            }
        except Exception as e:
            logger.error(f"Failed to get order details for {exchange_order_id}: {e}")
            return None
    
    def _handle_status_change(self, order_id: str, order_details: Dict[str, Any]) -> None:
        """Handle order status changes detected during monitoring."""
        new_status = order_details['status']
        
        update = OrderUpdate(
            order_id=order_id,
            status=new_status,
            filled_quantity=order_details.get('filled_quantity', 0),
            average_price=order_details.get('average_price', 0.0),
            timestamp=order_details.get('last_update_time', datetime.now()),
            message=f"Status changed to {new_status.value} via monitoring"
        )
        
        self._process_status_update(update)
        
        # Log significant status changes
        if new_status in [OrderStatus.COMPLETE, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            logger.info(f"Order {order_id} reached terminal status: {new_status.value}")
    
    def _check_and_process_fills(self, order_id: str, order_details: Dict[str, Any]) -> None:
        """Check for new fills and process them."""
        with self._lock:
            if order_id not in self._orders:
                return
            
            record = self._orders[order_id]
            current_filled = record.filled_quantity
            new_filled = order_details.get('filled_quantity', 0)
            
            # Check if there are new fills
            if new_filled > current_filled:
                # Calculate fill quantity
                fill_quantity = new_filled - current_filled
                fill_price = order_details.get('average_price', 0.0)
                
                # Create fill object
                fill = Fill(
                    order_id=order_id,
                    exchange_order_id=record.exchange_order_id or "",
                    fill_id=f"FILL_{order_id}_{len(record.fills) + 1}",
                    quantity=fill_quantity,
                    price=fill_price,
                    timestamp=order_details.get('last_update_time', datetime.now()),
                    exchange_timestamp=order_details.get('last_update_time'),
                    trade_id=order_details.get('trade_id')
                )
                
                # Process the fill
                self.process_fill(fill)
                
                logger.info(f"Detected and processed new fill: {order_id} - {fill_quantity}@{fill_price}")
    
    def _update_execution_metrics(self, order_id: str, order_details: Dict[str, Any]) -> None:
        """Update execution metrics and commission tracking."""
        with self._lock:
            if order_id not in self._orders:
                return
            
            record = self._orders[order_id]
            
            # Update commission if available
            commission = order_details.get('commission', 0.0)
            if commission > record.total_commission:
                additional_commission = commission - record.total_commission
                record.total_commission = commission
                self._stats['total_commission'] += additional_commission
    
    def _mark_for_retry_monitoring(self, order_id: str) -> None:
        """Mark an order for retry monitoring after error."""
        # This could implement exponential backoff or other retry logic
        logger.debug(f"Marked order {order_id} for retry monitoring")
    
    def _reconcile_positions(self) -> None:
        """Perform position reconciliation to ensure accuracy."""
        try:
            # This would typically:
            # 1. Get current positions from broker
            # 2. Compare with internal position tracking
            # 3. Identify and log discrepancies
            # 4. Optionally correct internal tracking
            
            # For now, just validate internal consistency
            with self._lock:
                for instrument, position in self._position_tracker.items():
                    # Validate position data consistency
                    if position.net_quantity == 0 and position.average_price != 0:
                        logger.warning(f"Position inconsistency detected for {instrument}: zero quantity but non-zero avg price")
                    
                    # Update unrealized P&L if current price is available
                    # This would require market data integration
                    # position.unrealized_pnl = self._calculate_unrealized_pnl(position)
        
        except Exception as e:
            logger.error(f"Error during position reconciliation: {e}")
    
    def process_fill(self, fill: Fill) -> None:
        """
        Process a fill notification from the exchange.
        
        Args:
            fill: Fill object with execution details
        """
        with self._lock:
            if fill.order_id not in self._orders:
                logger.warning(f"Received fill for unknown order: {fill.order_id}")
                return
            
            record = self._orders[fill.order_id]
            
            # Add fill to record
            record.fills.append(fill)
            
            # Update fill statistics
            previous_filled = record.filled_quantity
            record.filled_quantity += fill.quantity
            
            # Calculate new average price
            if record.filled_quantity > 0:
                total_value = (previous_filled * record.average_price) + (fill.quantity * fill.price)
                record.average_price = total_value / record.filled_quantity
            
            # Set first fill timestamp
            if record.first_fill_at is None:
                record.first_fill_at = fill.timestamp
            
            # Update order status based on fill
            if record.filled_quantity >= record.order.quantity:
                # Fully filled
                record.order.status = OrderStatus.COMPLETE
                record.completed_at = fill.timestamp
                self._stats['total_completed'] += 1
                self._pending_orders.discard(fill.order_id)
            else:
                # Partially filled, keep as OPEN
                record.order.status = OrderStatus.OPEN
            
            # Update statistics
            self._stats['total_fills'] += 1
            self._stats['total_volume'] += fill.quantity * fill.price
            
            record.updated_at = fill.timestamp
        
        # Update position tracking
        self._update_position_from_fill(fill)
        
        # Notify callbacks
        self._notify_fill_callbacks(fill)
        
        # Create and send order update
        update = OrderUpdate(
            order_id=fill.order_id,
            status=record.order.status,
            filled_quantity=record.filled_quantity,
            average_price=record.average_price,
            timestamp=fill.timestamp,
            message=f"Fill: {fill.quantity}@{fill.price}",
            exchange_order_id=fill.exchange_order_id
        )
        
        self._add_status_update(fill.order_id, update)
        self._notify_callbacks(update)
        
        # Generate execution report if order is complete
        if record.order.status == OrderStatus.COMPLETE:
            execution_report = self._generate_execution_report(fill.order_id)
            self._notify_execution_callbacks(execution_report)
        
        logger.info(
            f"Processed fill: {fill.order_id} - {fill.quantity}@{fill.price} "
            f"(total filled: {record.filled_quantity}/{record.order.quantity})"
        )
    
    def _update_position_from_fill(self, fill: Fill) -> None:
        """Update position tracking from fill with enhanced reconciliation."""
        with self._lock:
            if fill.order_id not in self._orders:
                return
            
            record = self._orders[fill.order_id]
            instrument = record.order.instrument
            
            # Get or create position update
            if instrument not in self._position_tracker:
                self._position_tracker[instrument] = PositionUpdate(
                    instrument=instrument,
                    net_quantity=0,
                    average_price=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    timestamp=fill.timestamp
                )
            
            position = self._position_tracker[instrument]
            
            # Store previous state for reconciliation
            prev_state = {
                'net_quantity': position.net_quantity,
                'average_price': position.average_price,
                'realized_pnl': position.realized_pnl
            }
            
            # Calculate position change
            quantity_change = fill.quantity
            if record.order.transaction_type == TransactionType.SELL:
                quantity_change = -quantity_change
            
            # Update position with enhanced logic
            old_quantity = position.net_quantity
            old_avg_price = position.average_price
            
            # Calculate position change
            new_quantity = old_quantity + quantity_change
            
            # Handle position updates based on transaction type
            if old_quantity == 0:
                # New position
                position.net_quantity = new_quantity
                position.average_price = fill.price
            elif (old_quantity > 0 and quantity_change > 0) or (old_quantity < 0 and quantity_change < 0):
                # Adding to existing position (same direction)
                position.net_quantity = new_quantity
                total_value = (abs(old_quantity) * old_avg_price) + (abs(quantity_change) * fill.price)
                position.average_price = total_value / abs(new_quantity)
            else:
                # Reducing or reversing position - calculate realized PnL
                reduction_quantity = min(abs(quantity_change), abs(old_quantity))
                
                if old_quantity > 0:  # Long position being reduced
                    realized_pnl = reduction_quantity * (fill.price - old_avg_price)
                else:  # Short position being reduced
                    realized_pnl = reduction_quantity * (old_avg_price - fill.price)
                
                position.realized_pnl += realized_pnl
                position.net_quantity = new_quantity
                
                # Update average price based on remaining position
                if new_quantity == 0:
                    # Position fully closed
                    position.average_price = 0.0
                elif (old_quantity > 0 and new_quantity > 0) or (old_quantity < 0 and new_quantity < 0):
                    # Still have position in same direction, keep old average
                    position.average_price = old_avg_price
                else:
                    # Position reversed, use fill price for new position
                    position.average_price = fill.price
            
            position.timestamp = fill.timestamp
            
            # Validate position update
            self._validate_position_update(instrument, prev_state, position, fill)
        
        # Notify position callbacks
        self._notify_position_callbacks(position)
        
        # Log position change for audit
        logger.info(
            f"Position updated for {instrument}: "
            f"qty={position.net_quantity}, avg_price={position.average_price:.2f}, "
            f"realized_pnl={position.realized_pnl:.2f}"
        )
    
    def _validate_position_update(self, instrument: str, prev_state: Dict[str, Any], 
                                current_position: PositionUpdate, fill: Fill) -> None:
        """Validate position update for consistency."""
        try:
            # Check for reasonable price ranges
            if current_position.average_price < 0:
                logger.error(f"Invalid negative average price for {instrument}: {current_position.average_price}")
            
            # Check for extreme position sizes (could indicate error)
            if abs(current_position.net_quantity) > 1000000:  # Configurable threshold
                logger.warning(f"Large position detected for {instrument}: {current_position.net_quantity}")
            
            # Validate realized PnL calculation
            if abs(current_position.realized_pnl - prev_state['realized_pnl']) > abs(fill.quantity * fill.price):
                logger.warning(f"Large PnL change detected for {instrument}: {current_position.realized_pnl}")
            
        except Exception as e:
            logger.error(f"Error validating position update for {instrument}: {e}")
    
    def reconcile_position_with_broker(self, instrument: str, broker_position: Dict[str, Any]) -> bool:
        """
        Reconcile internal position with broker position.
        
        Args:
            instrument: Instrument to reconcile
            broker_position: Position data from broker
            
        Returns:
            True if positions match, False if discrepancy found
        """
        with self._lock:
            internal_position = self._position_tracker.get(instrument)
            
            if not internal_position:
                # No internal position but broker has position
                if broker_position.get('net_quantity', 0) != 0:
                    logger.warning(
                        f"Position discrepancy for {instrument}: "
                        f"Internal=0, Broker={broker_position.get('net_quantity', 0)}"
                    )
                    
                    # Create internal position to match broker
                    self._position_tracker[instrument] = PositionUpdate(
                        instrument=instrument,
                        net_quantity=broker_position.get('net_quantity', 0),
                        average_price=broker_position.get('average_price', 0.0),
                        realized_pnl=broker_position.get('realized_pnl', 0.0),
                        unrealized_pnl=broker_position.get('unrealized_pnl', 0.0),
                        timestamp=datetime.now()
                    )
                    return False
                return True
            
            # Compare positions
            broker_qty = broker_position.get('net_quantity', 0)
            broker_avg = broker_position.get('average_price', 0.0)
            
            qty_match = internal_position.net_quantity == broker_qty
            price_match = abs(internal_position.average_price - broker_avg) < 0.01  # Allow small rounding differences
            
            if not qty_match or not price_match:
                logger.warning(
                    f"Position discrepancy for {instrument}: "
                    f"Internal qty={internal_position.net_quantity}, avg={internal_position.average_price:.2f} "
                    f"Broker qty={broker_qty}, avg={broker_avg:.2f}"
                )
                
                # Optionally update internal position to match broker
                # This would depend on business logic and confidence in broker data
                return False
            
            return True
    
    def get_position_reconciliation_report(self) -> Dict[str, Any]:
        """
        Generate position reconciliation report.
        
        Returns:
            Dictionary containing reconciliation status
        """
        report = {
            'timestamp': datetime.now(),
            'total_positions': len(self._position_tracker),
            'positions': {},
            'summary': {
                'total_net_value': 0.0,
                'total_realized_pnl': 0.0,
                'total_unrealized_pnl': 0.0,
                'instruments_with_positions': 0
            }
        }
        
        with self._lock:
            for instrument, position in self._position_tracker.items():
                position_value = position.net_quantity * position.average_price
                
                report['positions'][instrument] = {
                    'net_quantity': position.net_quantity,
                    'average_price': position.average_price,
                    'position_value': position_value,
                    'realized_pnl': position.realized_pnl,
                    'unrealized_pnl': position.unrealized_pnl,
                    'last_updated': position.timestamp.isoformat()
                }
                
                # Update summary
                if position.net_quantity != 0:
                    report['summary']['instruments_with_positions'] += 1
                    report['summary']['total_net_value'] += abs(position_value)
                
                report['summary']['total_realized_pnl'] += position.realized_pnl
                report['summary']['total_unrealized_pnl'] += position.unrealized_pnl
        
        return report
    
    def _generate_execution_report(self, order_id: str) -> ExecutionReport:
        """Generate comprehensive execution report for an order."""
        with self._lock:
            if order_id not in self._orders:
                raise ValueError(f"Order not found: {order_id}")
            
            record = self._orders[order_id]
            order = record.order
            
            # Calculate slippage (if market order)
            slippage = 0.0
            if order.order_type == OrderType.MARKET and record.average_price > 0 and order.price:
                if order.transaction_type == TransactionType.BUY:
                    slippage = record.average_price - order.price
                else:
                    slippage = order.price - record.average_price
            
            return ExecutionReport(
                order_id=order_id,
                exchange_order_id=record.exchange_order_id or "",
                instrument=order.instrument,
                transaction_type=order.transaction_type,
                order_type=order.order_type,
                total_quantity=order.quantity,
                filled_quantity=record.filled_quantity,
                remaining_quantity=order.quantity - record.filled_quantity,
                average_fill_price=record.average_price,
                fills=record.fills.copy(),
                status=order.status,
                submitted_at=record.submitted_at or datetime.now(),
                first_fill_at=record.first_fill_at,
                completed_at=record.completed_at,
                total_commission=record.total_commission,
                slippage=slippage
            )
    
    def get_execution_report(self, order_id: str) -> Optional[ExecutionReport]:
        """
        Get execution report for an order.
        
        Args:
            order_id: Order ID to get report for
            
        Returns:
            ExecutionReport if order exists, None otherwise
        """
        try:
            return self._generate_execution_report(order_id)
        except ValueError:
            return None
    
    def get_position_summary(self, instrument: Optional[str] = None) -> Dict[str, PositionUpdate]:
        """
        Get position summary for all instruments or specific instrument.
        
        Args:
            instrument: Optional instrument to filter by
            
        Returns:
            Dictionary of instrument -> PositionUpdate
        """
        with self._lock:
            if instrument:
                return {instrument: self._position_tracker.get(instrument)} if instrument in self._position_tracker else {}
            return self._position_tracker.copy()
    
    def get_fills_for_order(self, order_id: str) -> List[Fill]:
        """
        Get all fills for a specific order.
        
        Args:
            order_id: Order ID to get fills for
            
        Returns:
            List of Fill objects
        """
        with self._lock:
            if order_id not in self._orders:
                return []
            return self._orders[order_id].fills.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get order management statistics.
        
        Returns:
            Dictionary containing statistics
        """
        with self._lock:
            return {
                **self._stats,
                'pending_count': len(self._pending_orders),
                'total_orders': len(self._orders),
                'queue_size': self._order_queue.qsize(),
                'monitored_positions': len(self._position_tracker),
            }
    
    def get_audit_trail(self, order_id: Optional[str] = None, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get comprehensive audit trail for orders.
        
        Args:
            order_id: Optional specific order ID to filter by
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of audit trail entries
        """
        audit_entries = []
        
        with self._lock:
            for oid, record in self._orders.items():
                # Filter by order ID if specified
                if order_id and oid != order_id:
                    continue
                
                # Add order submission entry
                if record.submitted_at:
                    if self._time_in_range(record.submitted_at, start_time, end_time):
                        audit_entries.append({
                            'timestamp': record.submitted_at,
                            'order_id': oid,
                            'event_type': 'ORDER_SUBMITTED',
                            'details': {
                                'instrument': record.order.instrument,
                                'transaction_type': record.order.transaction_type.value,
                                'quantity': record.order.quantity,
                                'order_type': record.order.order_type.value,
                                'price': record.order.price,
                                'trigger_price': record.order.trigger_price,
                                'strategy_id': record.order.strategy_id
                            }
                        })
                
                # Add status updates
                for update in record.status_history:
                    if self._time_in_range(update.timestamp, start_time, end_time):
                        audit_entries.append({
                            'timestamp': update.timestamp,
                            'order_id': oid,
                            'event_type': 'STATUS_UPDATE',
                            'details': {
                                'status': update.status.value,
                                'filled_quantity': update.filled_quantity,
                                'average_price': update.average_price,
                                'message': update.message,
                                'exchange_order_id': update.exchange_order_id
                            }
                        })
                
                # Add fills
                for fill in record.fills:
                    if self._time_in_range(fill.timestamp, start_time, end_time):
                        audit_entries.append({
                            'timestamp': fill.timestamp,
                            'order_id': oid,
                            'event_type': 'FILL',
                            'details': {
                                'fill_id': fill.fill_id,
                                'quantity': fill.quantity,
                                'price': fill.price,
                                'exchange_order_id': fill.exchange_order_id,
                                'trade_id': fill.trade_id
                            }
                        })
        
        # Sort by timestamp
        audit_entries.sort(key=lambda x: x['timestamp'])
        return audit_entries
    
    def _time_in_range(self, timestamp: datetime, start_time: Optional[datetime], end_time: Optional[datetime]) -> bool:
        """Check if timestamp is within the specified range."""
        if start_time and timestamp < start_time:
            return False
        if end_time and timestamp > end_time:
            return False
        return True
    
    def get_execution_summary(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get execution summary for a time period.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            Dictionary containing execution summary
        """
        summary = {
            'total_orders': 0,
            'completed_orders': 0,
            'cancelled_orders': 0,
            'rejected_orders': 0,
            'total_volume': 0.0,
            'total_commission': 0.0,
            'instruments_traded': set(),
            'strategies_active': set(),
            'average_fill_time': 0.0,
            'fill_rate': 0.0,
            'partial_fills': 0,
            'slippage_stats': {
                'total_slippage': 0.0,
                'average_slippage': 0.0,
                'max_slippage': 0.0,
                'min_slippage': 0.0
            }
        }
        
        fill_times = []
        slippages = []
        
        with self._lock:
            for record in self._orders.values():
                # Filter by time if specified
                if record.submitted_at:
                    if not self._time_in_range(record.submitted_at, start_time, end_time):
                        continue
                
                summary['total_orders'] += 1
                summary['instruments_traded'].add(record.order.instrument)
                if record.order.strategy_id:
                    summary['strategies_active'].add(record.order.strategy_id)
                
                # Count by status
                if record.order.status == OrderStatus.COMPLETE:
                    summary['completed_orders'] += 1
                    summary['total_volume'] += record.filled_quantity * record.average_price
                    summary['total_commission'] += record.total_commission
                    
                    # Calculate fill time
                    if record.submitted_at and record.first_fill_at:
                        fill_time = (record.first_fill_at - record.submitted_at).total_seconds()
                        fill_times.append(fill_time)
                    
                    # Track partial fills
                    if len(record.fills) > 1:
                        summary['partial_fills'] += 1
                    
                    # Calculate slippage for market orders
                    if record.order.order_type == OrderType.MARKET and record.order.price and record.average_price:
                        if record.order.transaction_type == TransactionType.BUY:
                            slippage = record.average_price - record.order.price
                        else:
                            slippage = record.order.price - record.average_price
                        slippages.append(slippage)
                
                elif record.order.status == OrderStatus.CANCELLED:
                    summary['cancelled_orders'] += 1
                elif record.order.status == OrderStatus.REJECTED:
                    summary['rejected_orders'] += 1
        
        # Calculate derived metrics
        if summary['total_orders'] > 0:
            summary['fill_rate'] = summary['completed_orders'] / summary['total_orders']
        
        if fill_times:
            summary['average_fill_time'] = sum(fill_times) / len(fill_times)
        
        if slippages:
            summary['slippage_stats']['total_slippage'] = sum(slippages)
            summary['slippage_stats']['average_slippage'] = sum(slippages) / len(slippages)
            summary['slippage_stats']['max_slippage'] = max(slippages)
            summary['slippage_stats']['min_slippage'] = min(slippages)
        
        # Convert sets to lists for JSON serialization
        summary['instruments_traded'] = list(summary['instruments_traded'])
        summary['strategies_active'] = list(summary['strategies_active'])
        
        return summary
    
    def export_execution_data(self, filepath: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> bool:
        """
        Export execution data to file for analysis.
        
        Args:
            filepath: Path to export file
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            import json
            
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'start_time': start_time.isoformat() if start_time else None,
                'end_time': end_time.isoformat() if end_time else None,
                'summary': self.get_execution_summary(start_time, end_time),
                'audit_trail': []
            }
            
            # Get audit trail and convert timestamps to ISO format
            audit_trail = self.get_audit_trail(start_time=start_time, end_time=end_time)
            for entry in audit_trail:
                entry_copy = entry.copy()
                entry_copy['timestamp'] = entry_copy['timestamp'].isoformat()
                export_data['audit_trail'].append(entry_copy)
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Execution data exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export execution data: {e}")
            return False
    
    def _update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        message: str = ""
    ) -> None:
        """Update order status and create status update."""
        update = OrderUpdate(
            order_id=order_id,
            status=status,
            timestamp=datetime.now(),
            message=message
        )
        
        with self._lock:
            if order_id in self._orders:
                self._orders[order_id].order.status = status
                self._orders[order_id].updated_at = update.timestamp
                self._add_status_update(order_id, update)
        
        self._notify_callbacks(update)
    
    def _add_status_update(self, order_id: str, update: OrderUpdate) -> None:
        """Add status update to order history."""
        with self._lock:
            if order_id in self._orders:
                self._orders[order_id].status_history.append(update)
    
    def _process_status_update(self, update: OrderUpdate) -> None:
        """Process a status update from monitoring."""
        with self._lock:
            if update.order_id not in self._orders:
                return
            
            record = self._orders[update.order_id]
            old_status = record.order.status
            
            # Update order status
            record.order.status = update.status
            record.updated_at = update.timestamp
            
            # Update statistics based on status change
            if old_status != update.status:
                if update.status == OrderStatus.COMPLETE:
                    self._stats['total_completed'] += 1
                    self._pending_orders.discard(update.order_id)
                elif update.status == OrderStatus.CANCELLED:
                    self._stats['total_cancelled'] += 1
                    self._pending_orders.discard(update.order_id)
                elif update.status == OrderStatus.REJECTED:
                    self._stats['total_rejected'] += 1
                    self._pending_orders.discard(update.order_id)
            
            # Add to history
            self._add_status_update(update.order_id, update)
        
        # Notify callbacks
        self._notify_callbacks(update)
    
    def _notify_callbacks(self, update: OrderUpdate) -> None:
        """Notify all registered callbacks of order update."""
        for callback in self._order_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Error in order callback {callback.__name__}: {e}")
    
    def _notify_fill_callbacks(self, fill: Fill) -> None:
        """Notify all registered fill callbacks."""
        for callback in self._fill_callbacks:
            try:
                callback(fill)
            except Exception as e:
                logger.error(f"Error in fill callback {callback.__name__}: {e}")
    
    def _notify_execution_callbacks(self, report: ExecutionReport) -> None:
        """Notify all registered execution callbacks."""
        for callback in self._execution_callbacks:
            try:
                callback(report)
            except Exception as e:
                logger.error(f"Error in execution callback {callback.__name__}: {e}")
    
    def _notify_position_callbacks(self, position: PositionUpdate) -> None:
        """Notify all registered position callbacks."""
        for callback in self._position_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"Error in position callback {callback.__name__}: {e}")
    
    def _get_exchange_order_id(self, order_id: str) -> Optional[str]:
        """Get exchange order ID from internal order ID."""
        with self._lock:
            if order_id not in self._orders:
                return None
            
            # Check status history for exchange order ID
            record = self._orders[order_id]
            for update in reversed(record.status_history):
                if update.exchange_order_id:
                    return update.exchange_order_id
            
            # Fallback to order's order_id if it was updated
            return record.order.order_id if record.order.order_id != order_id else None
    
    def _generate_order_id(self) -> str:
        """Generate unique internal order ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"ORD_{timestamp}"
    
    def shutdown(self) -> None:
        """Shutdown the order manager gracefully."""
        logger.info("Shutting down OrderManager")
        
        # Stop queue processing
        if self._enable_queue_processing:
            self.stop_queue_processing()
        
        # Stop execution monitoring
        if self._monitoring_enabled:
            self.stop_execution_monitoring()
        
        # Wait for pending orders to complete (with timeout)
        timeout = 10.0
        start_time = time.time()
        
        while self._pending_orders and (time.time() - start_time) < timeout:
            time.sleep(0.5)
        
        if self._pending_orders:
            logger.warning(
                f"Shutdown with {len(self._pending_orders)} pending orders"
            )
        
        logger.info("OrderManager shutdown complete")
