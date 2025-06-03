import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, call
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedOrderManager
from src.order import OrderType


class TestAutoDoubleDown:
    """Test that double down orders are automatically created with entry orders."""
    
    def setup_method(self):
        """Setup test context with required components."""
        self.context = {
            "order_manager": AsyncMock(),
            "position_tracker": AsyncMock(),
            "indicator_manager": AsyncMock(),
            "price_service": AsyncMock(),
            "position_sizer": MagicMock()  # This one doesn't need to be async
        }
        
        # Mock price service
        self.context["price_service"].get_price.return_value = 150.0
        
        # Mock indicator manager for ATR
        self.context["indicator_manager"].get_atr.return_value = 2.5
        
        # Mock position sizer for dynamic sizing
        self.context["position_sizer"].calculate_shares.return_value = 100
    
    @pytest.mark.asyncio
    async def test_buy_entry_creates_double_down(self):
        """Test that BUY entry automatically creates double down buy order."""
        symbol = "AAPL"
        
        # Mock order creation - main order and double down order
        main_order = MagicMock()
        main_order.order_id = "MAIN_001"
        
        stop_order = MagicMock()
        stop_order.order_id = "STOP_001"
        
        target_order = MagicMock()
        target_order.order_id = "TARGET_001"
        
        doubledown_order = MagicMock()
        doubledown_order.order_id = "DD_001"
        
        # Set up order manager to return different orders for each call
        self.context["order_manager"].create_and_submit_order.return_value = main_order
        # Use AsyncMock for create_order since it's an async method
        self.context["order_manager"].create_order = AsyncMock(side_effect=[stop_order, target_order, doubledown_order])
        
        # Create BUY entry action with auto stops
        buy_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=10000,  # $10K allocation
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0
        )
        
        # Execute the action
        result = await buy_action.execute(self.context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify main order was created
        self.context["order_manager"].create_and_submit_order.assert_called_once()
        
        # Verify protective orders and double down were created
        assert self.context["order_manager"].create_order.call_count == 3  # stop + target + doubledown
        
        # Verify context structure
        assert symbol in self.context
        assert self.context[symbol]["side"] == "BUY"
        assert "MAIN_001" in self.context[symbol]["main_orders"]
        assert "STOP_001" in self.context[symbol]["stop_orders"]
        assert "TARGET_001" in self.context[symbol]["target_orders"]
        assert "DD_001" in self.context[symbol]["doubledown_orders"]
        
        # Verify double down order parameters
        dd_call = self.context["order_manager"].create_order.call_args_list[2]
        assert dd_call[1]["order_type"] == OrderType.LIMIT
        assert dd_call[1]["quantity"] > 0  # Positive for BUY
        assert dd_call[1]["limit_price"] < 150.0  # Below current price
    
    @pytest.mark.asyncio
    async def test_sell_entry_creates_double_down(self):
        """Test that SELL (short) entry automatically creates double down sell order."""
        symbol = "TSLA"
        
        # Mock order creation
        main_order = MagicMock()
        main_order.order_id = "MAIN_002"
        
        stop_order = MagicMock()
        stop_order.order_id = "STOP_002"
        
        target_order = MagicMock()
        target_order.order_id = "TARGET_002"
        
        doubledown_order = MagicMock()
        doubledown_order.order_id = "DD_002"
        
        # Set up order manager
        self.context["order_manager"].create_and_submit_order.return_value = main_order
        self.context["order_manager"].create_order = AsyncMock(side_effect=[stop_order, target_order, doubledown_order])
        
        # Create SELL (short) entry action
        sell_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=10000,  # $10K allocation
            side="SELL",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0
        )
        
        # Execute the action
        result = await sell_action.execute(self.context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify all orders were created
        assert self.context["order_manager"].create_order.call_count == 3
        
        # Verify context structure
        assert symbol in self.context
        assert self.context[symbol]["side"] == "SELL"
        assert "DD_002" in self.context[symbol]["doubledown_orders"]
        
        # Verify double down order parameters
        dd_call = self.context["order_manager"].create_order.call_args_list[2]
        assert dd_call[1]["order_type"] == OrderType.LIMIT
        assert dd_call[1]["quantity"] < 0  # Negative for SELL
        assert dd_call[1]["limit_price"] > 150.0  # Above current price
    
    @pytest.mark.asyncio
    async def test_entry_without_auto_stops_no_double_down(self):
        """Test that entry without auto stops does NOT create double down."""
        symbol = "NVDA"
        
        # Mock order creation
        main_order = MagicMock()
        main_order.order_id = "MAIN_003"
        
        # Set up order manager
        self.context["order_manager"].create_and_submit_order.return_value = main_order
        self.context["order_manager"].create_order = AsyncMock()
        
        # Create entry action WITHOUT auto stops
        buy_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=10000,
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=False  # No auto stops
        )
        
        # Execute the action
        result = await buy_action.execute(self.context)
        
        # Verify execution succeeded
        assert result is True
        
        # Verify NO protective orders or double down were created
        assert self.context["order_manager"].create_order.call_count == 0
        
        # Verify context structure has main order only
        assert symbol in self.context
        assert self.context[symbol]["side"] == "BUY"
        assert "MAIN_003" in self.context[symbol]["main_orders"]
        assert len(self.context[symbol]["stop_orders"]) == 0
        assert len(self.context[symbol]["target_orders"]) == 0
        assert len(self.context[symbol]["doubledown_orders"]) == 0
    
    @pytest.mark.asyncio
    async def test_double_down_calculation_accuracy(self):
        """Test that double down orders are placed at correct prices."""
        symbol = "AMD"
        
        # Current price: 150, ATR: 2.5
        # Stop distance: 2.5 * 6 = 15
        # Double down distance: 15 * 0.5 = 7.5
        # BUY DD price: 150 - 7.5 = 142.5
        # SELL DD price: 150 + 7.5 = 157.5
        
        # Mock orders
        main_order = MagicMock()
        main_order.order_id = "MAIN_004"
        
        stop_order = MagicMock()
        stop_order.order_id = "STOP_004"
        
        target_order = MagicMock()
        target_order.order_id = "TARGET_004"
        
        doubledown_order = MagicMock()
        doubledown_order.order_id = "DD_004"
        
        self.context["order_manager"].create_and_submit_order.return_value = main_order
        self.context["order_manager"].create_order = AsyncMock(side_effect=[stop_order, target_order, doubledown_order])
        
        # Test BUY entry
        buy_action = LinkedCreateOrderAction(
            symbol=symbol,
            quantity=100,  # Fixed shares
            side="BUY",
            order_type=OrderType.MARKET,
            auto_create_stops=True,
            atr_stop_multiplier=6.0,
            atr_target_multiplier=3.0
        )
        
        result = await buy_action.execute(self.context)
        assert result is True
        
        # Check double down price
        dd_call = self.context["order_manager"].create_order.call_args_list[2]
        assert dd_call[1]["limit_price"] == pytest.approx(142.5, rel=0.01)
        assert dd_call[1]["quantity"] == 100  # Same as entry 