"""Trade execution monitoring and management utilities."""

import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from ..models import TradeSignal
from ..utils.logger import setup_logging
from dotenv import load_dotenv
load_dotenv()
logger = setup_logging('TradeMonitor')

class TradeExecutionMonitor:
    """Monitors trade execution and manages order state"""
    
    def __init__(self):
        self.execution_timeout = int(os.getenv('TRADE_EXECUTION_TIMEOUT', '30'))  # seconds
        self.max_retries = int(os.getenv('TRADE_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('TRADE_RETRY_DELAY', '5'))  # seconds
        
    def verify_order_placement(self, order_id: int, mt5_service, expected_params: Dict) -> Dict:
        """
        Verify order placement and parameters
        Returns success status and details
        """
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Get order details
                order = mt5_service.get_order(order_id)
                if not order:
                    attempt += 1
                    time.sleep(1)
                    continue
                    
                # Verify order parameters
                verification = self._verify_order_parameters(order, expected_params)
                if verification['success']:
                    logger.info(f"Order {order_id} verified successfully")
                    return verification
                else:
                    logger.warning(f"Order {order_id} verification failed: {verification['reason']}")
                    attempt += 1
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Order verification error: {e}")
                attempt += 1
                time.sleep(1)
                
        return {
            'success': False,
            'reason': f'Order verification failed after {max_attempts} attempts'
        }
        
    def _verify_order_parameters(self, order: Dict, expected: Dict) -> Dict:
        """Verify order parameters match expected values"""
        try:
            # Essential parameters that must match exactly
            critical_params = ['type', 'symbol', 'volume']
            for param in critical_params:
                if param in expected and order[param] != expected[param]:
                    return {
                        'success': False,
                        'reason': f'Parameter mismatch: {param}',
                        'expected': expected[param],
                        'actual': order[param]
                    }
            
            # Price parameters - allow small deviation
            if 'price' in expected:
                price_deviation = abs(order['price'] - expected['price'])
                max_deviation = float(os.getenv('MAX_PRICE_DEVIATION', '0.1'))
                if price_deviation > max_deviation:
                    return {
                        'success': False,
                        'reason': 'Price deviation too large',
                        'deviation': price_deviation
                    }
            
            # SL/TP validation
            if 'sl' in expected and abs(order['sl'] - expected['sl']) > max_deviation:
                return {
                    'success': False,
                    'reason': 'Stop loss deviation too large'
                }
            
            if 'tp' in expected and abs(order['tp'] - expected['tp']) > max_deviation:
                return {
                    'success': False,
                    'reason': 'Take profit deviation too large'
                }
            
            return {'success': True, 'order': order}
            
        except Exception as e:
            return {'success': False, 'reason': f'Verification error: {e}'}
    
    def monitor_trade_execution(self, signal: TradeSignal, mt5_service) -> Dict:
        """
        Monitor trade execution progress and handle timeouts
        Returns execution status and details
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < self.execution_timeout:
            try:
                # Check order status
                if signal.order_ticket:
                    order_status = mt5_service.get_order_status(signal.order_ticket)
                    if order_status == 'FILLED':
                        return {
                            'success': True,
                            'status': 'FILLED',
                            'execution_time': (datetime.now() - start_time).total_seconds()
                        }
                    elif order_status in ['REJECTED', 'CANCELED']:
                        return {
                            'success': False,
                            'status': order_status,
                            'reason': 'Order rejected or canceled'
                        }
                
                # Small delay between checks
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Execution monitoring error: {e}")
                
        return {
            'success': False,
            'status': 'TIMEOUT',
            'reason': f'Execution timeout after {self.execution_timeout}s'
        }
    
    def handle_partial_fills(self, signal: TradeSignal, mt5_service) -> Dict:
        """Handle partially filled orders and adjust positions"""
        try:
            # Get filled volume
            position = mt5_service.get_position(signal.symbol)
            if not position:
                return {'success': False, 'reason': 'No position found'}
            
            filled_volume = position['volume']
            target_volume = signal.volume
            
            if filled_volume < target_volume:
                logger.warning(f"Partial fill detected: {filled_volume}/{target_volume}")
                
                # Calculate remaining volume
                remaining = target_volume - filled_volume
                
                # Attempt to fill remaining volume
                if remaining >= 0.01:  # Minimum trade size
                    complement_order = mt5_service.place_order(
                        symbol=signal.symbol,
                        order_type=signal.entry_method,
                        volume=remaining,
                        price=signal.entry_price,
                        sl=signal.stop_loss,
                        tp=signal.take_profit_1
                    )
                    
                    if complement_order['success']:
                        logger.info(f"Placed complementary order for remaining volume")
                        return {'success': True, 'filled': filled_volume, 'remaining_order': complement_order['order']}
                
            return {'success': True, 'filled': filled_volume, 'complete': True}
            
        except Exception as e:
            logger.error(f"Error handling partial fill: {e}")
            return {'success': False, 'reason': str(e)}
