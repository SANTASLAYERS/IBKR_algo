import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, call
from datetime import datetime
from src.rule.linked_order_actions import (
    LinkedCreateOrderAction, 
    LinkedOrderManager,
    LinkedDoubleDownFillManager
)
from src.order import OrderType
from src.event.order import FillEvent


class TestDoubleDownFillUpdate:
    """Test that stop/target orders are updated when double down orders fill."""
    
    def setup_method(self):
        """Setup test context with required components."""
        self.context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "indicator_manager": AsyncMock(),
            "price_service": AsyncMock(),
            "position_sizer": MagicMock(),
            "event_bus": AsyncMock()
        }
        
        # Mock price service
        self.context["price_service"].get_price.return_value = 150.0
        
        # Mock indicator manager for ATR
        self.context["indicator_manager"].get_atr.return_value = 2.5
        
        # Mock position sizer
        self.context["position_sizer"].calculate_shares.return_value = 100
    
    @pytest.mark.asyncio
    async def test_doubledown_fill_updates_stop_target_long(self):
        """Test that filling a double down buy order updates stop/target quantities for long position."""
        symbol = "AAPL"
        
        # Setup initial position with orders
        self.context[symbol] = {
            "side": "BUY",
            "main_orders": ["MAIN_001"],
            "stop_orders": ["STOP_001"],
            "target_orders": ["TARGET_001"],
            "doubledown_orders": ["DD_001"],
            "status": "active",
            "quantity": 100,  # Original position size
            "entry_price": 150.0
        }
        
        # Mock position tracker to return current position
        mock_position = MagicMock()
        mock_position.quantity = 100
        mock_position.entry_price = 150.0
        mock_position.current_price = 145.0  # Price dropped
        mock_position.is_long = True
        self.context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
        
        # Create double down fill manager
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        # Simulate double down order fill at $142.50
        fill_event = FillEvent(
            order_id="DD_001",
            symbol=symbol,
            quantity=100,  # Double down quantity
            fill_price=142.50,
            fill_time=datetime.now()
        )
        
        # Process the fill
        await dd_manager.on_order_fill(fill_event)
        
        # Verify old stop/target orders were cancelled
        cancel_calls = self.context["order_manager"].cancel_order.call_args_list
        assert len(cancel_calls) >= 2  # At least stop and target
        assert call("STOP_001", "Double down fill - updating protective orders") in cancel_calls
        assert call("TARGET_001", "Double down fill - updating protective orders") in cancel_calls
        
        # Verify new stop/target orders were created with updated quantities
        create_calls = self.context["order_manager"].create_order.call_args_list
        
        # Find stop order creation
        stop_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        stop_call = stop_calls[0]
        assert stop_call[1]["quantity"] == -200  # Negative 200 shares (doubled)
        
        # New average price: (100*150 + 100*142.50) / 200 = 146.25
        # Stop should be at new_avg - (ATR * 6) = 146.25 - 15 = 131.25
        assert stop_call[1]["stop_price"] == pytest.approx(131.25, rel=0.01)
        
        # Find target order creation
        target_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        target_call = target_calls[0]
        assert target_call[1]["quantity"] == -200  # Negative 200 shares
        # Target should be at new_avg + (ATR * 3) = 146.25 + 7.5 = 153.75
        assert target_call[1]["limit_price"] == pytest.approx(153.75, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_doubledown_fill_updates_stop_target_short(self):
        """Test that filling a double down sell order updates stop/target quantities for short position."""
        symbol = "TSLA"
        
        # Setup initial short position with orders
        self.context[symbol] = {
            "side": "SELL",
            "main_orders": ["MAIN_002"],
            "stop_orders": ["STOP_002"],
            "target_orders": ["TARGET_002"],
            "doubledown_orders": ["DD_002"],
            "status": "active",
            "quantity": -100,  # Short position
            "entry_price": 150.0
        }
        
        # Mock position tracker
        mock_position = MagicMock()
        mock_position.quantity = -100
        mock_position.entry_price = 150.0
        mock_position.current_price = 155.0  # Price went up (bad for short)
        mock_position.is_long = False
        self.context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
        
        # Create manager
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        # Simulate double down fill at $157.50 (adding to short)
        fill_event = FillEvent(
            order_id="DD_002",
            symbol=symbol,
            quantity=-100,  # Negative for short
            fill_price=157.50,
            fill_time=datetime.now()
        )
        
        await dd_manager.on_order_fill(fill_event)
        
        # Verify updates
        create_calls = self.context["order_manager"].create_order.call_args_list
        
        # Stop order for short (buy to cover)
        stop_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.STOP]
        assert len(stop_calls) == 1
        assert stop_calls[0][1]["quantity"] == 200  # Positive to close short
        
        # New average: (100*150 + 100*157.50) / 200 = 153.75
        # Stop for short: new_avg + (ATR * 6) = 153.75 + 15 = 168.75
        assert stop_calls[0][1]["stop_price"] == pytest.approx(168.75, rel=0.01)
        
        # Target order
        target_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.LIMIT]
        assert len(target_calls) == 1
        assert target_calls[0][1]["quantity"] == 200  # Positive to close short
        # Target for short: new_avg - (ATR * 3) = 153.75 - 7.5 = 146.25
        assert target_calls[0][1]["limit_price"] == pytest.approx(146.25, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_multiple_doubledown_levels(self):
        """Test handling multiple double down levels."""
        symbol = "NVDA"
        
        # Setup with multiple double down orders
        self.context[symbol] = {
            "side": "BUY",
            "main_orders": ["MAIN_003"],
            "stop_orders": ["STOP_003"],
            "target_orders": ["TARGET_003"],
            "doubledown_orders": ["DD1_003", "DD2_003", "DD3_003"],
            "status": "active",
            "quantity": 100,
            "entry_price": 150.0
        }
        
        mock_position = MagicMock()
        mock_position.quantity = 100
        mock_position.entry_price = 150.0
        mock_position.is_long = True
        self.context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
        
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        # Fill first double down
        fill_event1 = FillEvent(
            order_id="DD1_003",
            symbol=symbol,
            quantity=50,  # Smaller first level
            fill_price=145.0,
            fill_time=datetime.now()
        )
        
        await dd_manager.on_order_fill(fill_event1)
        
        # Verify stop/target updated for 150 shares
        create_calls = self.context["order_manager"].create_order.call_args_list
        stop_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.STOP]
        assert stop_calls[-1][1]["quantity"] == -150  # 100 + 50
        
        # Clear mock calls
        self.context["order_manager"].create_order.reset_mock()
        
        # Update position for next fill
        mock_position.quantity = 150
        mock_position.entry_price = 148.33  # New average after first DD
        
        # Fill second double down
        fill_event2 = FillEvent(
            order_id="DD2_003",
            symbol=symbol,
            quantity=100,
            fill_price=140.0,
            fill_time=datetime.now()
        )
        
        await dd_manager.on_order_fill(fill_event2)
        
        # Verify stop/target updated for 250 shares total
        create_calls = self.context["order_manager"].create_order.call_args_list
        stop_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.STOP]
        assert stop_calls[-1][1]["quantity"] == -250  # 150 + 100
    
    @pytest.mark.asyncio
    async def test_non_doubledown_fills_ignored(self):
        """Test that non-double down order fills are ignored."""
        symbol = "AMD"
        
        self.context[symbol] = {
            "side": "BUY",
            "main_orders": ["MAIN_004"],
            "stop_orders": ["STOP_004"],
            "target_orders": ["TARGET_004"],
            "doubledown_orders": ["DD_004"],
            "status": "active"
        }
        
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        # Fill main order (not double down)
        fill_event = FillEvent(
            order_id="MAIN_004",
            symbol=symbol,
            quantity=100,
            fill_price=150.0,
            fill_time=datetime.now()
        )
        
        await dd_manager.on_order_fill(fill_event)
        
        # Should not trigger any order updates
        self.context["order_manager"].cancel_order.assert_not_called()
        self.context["order_manager"].create_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_doubledown_fill_with_no_position(self):
        """Test graceful handling when position data is missing."""
        symbol = "GOOGL"
        
        self.context[symbol] = {
            "side": "BUY",
            "main_orders": ["MAIN_005"],
            "stop_orders": ["STOP_005"],
            "target_orders": ["TARGET_005"],
            "doubledown_orders": ["DD_005"],
            "status": "active"
        }
        
        # No position returned
        self.context["position_tracker"].get_positions_for_symbol.return_value = []
        
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        fill_event = FillEvent(
            order_id="DD_005",
            symbol=symbol,
            quantity=100,
            fill_price=145.0,
            fill_time=datetime.now()
        )
        
        # Should handle gracefully without crashing
        await dd_manager.on_order_fill(fill_event)
        
        # Should not update orders without position data
        self.context["order_manager"].cancel_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_doubledown_fill_preserves_atr_multipliers(self):
        """Test that ATR multipliers are preserved when updating orders."""
        symbol = "SPY"
        
        # Store ATR multipliers in context
        self.context[symbol] = {
            "side": "BUY",
            "main_orders": ["MAIN_006"],
            "stop_orders": ["STOP_006"],
            "target_orders": ["TARGET_006"],
            "doubledown_orders": ["DD_006"],
            "status": "active",
            "quantity": 100,
            "entry_price": 150.0,
            "atr_stop_multiplier": 6.0,
            "atr_target_multiplier": 3.0
        }
        
        mock_position = MagicMock()
        mock_position.quantity = 100
        mock_position.entry_price = 150.0
        mock_position.is_long = True
        self.context["position_tracker"].get_positions_for_symbol.return_value = [mock_position]
        
        # Set specific ATR value
        self.context["indicator_manager"].get_atr.return_value = 1.0
        
        dd_manager = LinkedDoubleDownFillManager(
            context=self.context,
            event_bus=self.context["event_bus"]
        )
        await dd_manager.initialize()
        
        fill_event = FillEvent(
            order_id="DD_006",
            symbol=symbol,
            quantity=100,
            fill_price=145.0,
            fill_time=datetime.now()
        )
        
        await dd_manager.on_order_fill(fill_event)
        
        # Verify ATR was used with correct multipliers
        # New avg = 147.5, ATR = 1.0
        create_calls = self.context["order_manager"].create_order.call_args_list
        
        stop_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.STOP]
        # Stop = 147.5 - (1.0 * 6) = 141.5
        assert stop_calls[0][1]["stop_price"] == pytest.approx(141.5, rel=0.01)
        
        target_calls = [c for c in create_calls if c[1].get("order_type") == OrderType.LIMIT]
        # Target = 147.5 + (1.0 * 3) = 150.5
        assert target_calls[0][1]["limit_price"] == pytest.approx(150.5, rel=0.01) 