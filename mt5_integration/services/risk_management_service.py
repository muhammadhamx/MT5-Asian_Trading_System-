"""Risk management and position sizing service.
Enhanced risk controls for production trading.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from ..models import TradingSession, TradeSignal
from ..utils.logger import setup_logging, log_trade
from ..utils.error_handler import ProductionErrorHandler
from mt5_integration.utils.strategy_constants import (
    XAUUSD_PIP_VALUE, EURUSD_PIP_VALUE, GBPUSD_PIP_VALUE, USDJPY_PIP_VALUE,
    TIGHT_RISK_PERCENTAGE, NORMAL_RISK_PERCENTAGE, WIDE_RISK_PERCENTAGE, MAX_RISK_PER_TRADE,
    DAILY_TRADE_COUNT_LIMIT, DAILY_LOSS_LIMIT_R, WEEKLY_LOSS_LIMIT_R,
    MIN_LOT_SIZE, LOT_SIZE_STEP
)

logger = setup_logging('RiskManager')
error_handler = ProductionErrorHandler()

class RiskManagementService:
    """Manages risk limits, position sizing, and trade management"""
    
    def __init__(self):
        # Load risk parameters from environment
        self.max_risk_per_trade = MAX_RISK_PER_TRADE  # 0.5%
        self.max_daily_loss = DAILY_LOSS_LIMIT_R * 100  # 2% max daily loss
        self.max_weekly_loss = WEEKLY_LOSS_LIMIT_R * 100  # 6% max weekly loss
        self.max_daily_trades = DAILY_TRADE_COUNT_LIMIT
        self.max_concurrent_trades = int(os.getenv('MAX_CONCURRENT_TRADES', '1'))
        self.min_reward_risk = float(os.getenv('MIN_REWARD_RISK', '1.5'))
        
        # Dynamic risk adjustment thresholds
        self.drawdown_threshold = float(os.getenv('DRAWDOWN_THRESHOLD', '4.0'))  # 4% drawdown triggers risk reduction
        self.volatility_threshold = float(os.getenv('VOLATILITY_THRESHOLD', '1.5'))  # 1.5x normal volatility
        
        # Position sizing constraints
        self.min_stop_distance = float(os.getenv('MIN_STOP_DISTANCE', '10.0'))  # Minimum 10 pip stop
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', '1.0'))  # Maximum 1.0 lot
        
    @error_handler.handle_trading_error
    def validate_trade_parameters(self, signal: TradeSignal) -> Dict:
        """
        Validate all trade parameters before execution
        Returns success status and validation details
        """
        try:
            validation = {
                'success': True,
                'checks': {},
                'risk_level': 'NORMAL'
            }
            
            # 1. Check risk percentage
            if signal.risk_percentage > MAX_RISK_PER_TRADE:
                validation['success'] = False
                validation['checks']['risk_percentage'] = {
                    'status': 'FAILED',
                    'reason': f'Risk {signal.risk_percentage}% exceeds max {MAX_RISK_PER_TRADE}%'
                }
            
            # 2. Validate stop loss distance
            sl_distance = abs(signal.entry_price - signal.stop_loss)
            if sl_distance < self.min_stop_distance:
                validation['success'] = False
                validation['checks']['stop_loss'] = {
                    'status': 'FAILED',
                    'reason': f'Stop distance {sl_distance} below minimum {self.min_stop_distance}'
                }
            
            # 3. Check reward/risk ratio
            if signal.take_profit_1 and signal.stop_loss:
                rr_ratio = self._calculate_reward_risk_ratio(signal)
                if rr_ratio < self.min_reward_risk:
                    validation['success'] = False
                    validation['checks']['reward_risk'] = {
                        'status': 'FAILED',
                        'reason': f'R:R ratio {rr_ratio:.2f} below minimum {self.min_reward_risk}'
                    }
            
            # 4. Check daily limits
            daily_validation = self._validate_daily_limits(signal.session)
            validation['checks']['daily_limits'] = daily_validation
            if not daily_validation['status']:
                validation['success'] = False
            
            # 5. Check weekly limits
            weekly_validation = self._validate_weekly_limits(signal.session)
            validation['checks']['weekly_limits'] = weekly_validation
            if not weekly_validation['status']:
                validation['success'] = False
            
            # 6. Validate position size
            size_validation = self._validate_position_size(signal)
            validation['checks']['position_size'] = size_validation
            if not size_validation['status']:
                validation['success'] = False
            
            # Log validation results
            log_trade(logger, 'VALIDATION', 
                signal_id=signal.id,
                validation_status=validation['success'],
                checks=validation['checks']
            )
            
            return validation
            
        except Exception as e:
            logger.error(f"Trade validation error: {e}")
            return {
                'success': False,
                'error': str(e),
                'checks': {'system_error': {'status': 'FAILED', 'reason': str(e)}}
            }
    
    def _calculate_reward_risk_ratio(self, signal: TradeSignal) -> float:
        """Calculate reward to risk ratio"""
        if not (signal.take_profit_1 and signal.stop_loss):
            return 0.0
            
        risk = abs(signal.entry_price - signal.stop_loss)
        if risk == 0:
            return 0.0
            
        reward = abs(signal.take_profit_1 - signal.entry_price)
        return reward / risk
    
    def _validate_daily_limits(self, session: TradingSession) -> Dict:
        """Validate daily trading limits"""
        try:
            # Check number of trades
            daily_trades = TradeSignal.objects.filter(
                session__session_date=session.session_date
            ).count()
            
            if daily_trades >= DAILY_TRADE_COUNT_LIMIT:
                return {
                    'status': False,
                    'reason': f'Daily trade limit ({DAILY_TRADE_COUNT_LIMIT}) reached'
                }
            
            # Check daily loss
            daily_loss = float(session.current_daily_loss)
            if daily_loss >= DAILY_LOSS_LIMIT_R * 100:
                return {
                    'status': False,
                    'reason': f'Daily loss limit ({DAILY_LOSS_LIMIT_R * 100}%) reached: {daily_loss:.2f}%'
                }
            
            return {'status': True, 'trades': daily_trades, 'loss': daily_loss}
            
        except Exception as e:
            logger.error(f"Daily limit validation error: {e}")
            return {'status': False, 'reason': str(e)}
    
    def _validate_weekly_limits(self, session: TradingSession) -> Dict:
        """Validate weekly trading limits"""
        try:
            # Calculate week start
            week_start = session.session_date - timedelta(days=session.session_date.weekday())
            
            # Get weekly loss
            weekly_loss = float(session.weekly_realized_r * 0.5)  # Convert R to percentage
            
            if weekly_loss >= WEEKLY_LOSS_LIMIT_R * 100:
                return {
                    'status': False,
                    'reason': f'Weekly loss limit ({WEEKLY_LOSS_LIMIT_R * 100}%) reached: {weekly_loss:.2f}%'
                }
            
            return {'status': True, 'loss': weekly_loss}
            
        except Exception as e:
            logger.error(f"Weekly limit validation error: {e}")
            return {'status': False, 'reason': str(e)}
    
    def _validate_position_size(self, signal: TradeSignal) -> Dict:
        """Validate position size against limits"""
        try:
            # Check absolute size limit
            if signal.volume > self.max_position_size:
                return {
                    'status': False,
                    'reason': f'Position size {signal.volume} exceeds maximum {self.max_position_size}'
                }
            
            # Check concurrent positions
            active_positions = TradeSignal.objects.filter(
                exit_time__isnull=True,
                state='IN_TRADE'
            ).count()
            
            if active_positions >= self.max_concurrent_trades:
                return {
                    'status': False,
                    'reason': f'Maximum concurrent trades ({self.max_concurrent_trades}) reached'
                }
            
            return {'status': True, 'size': signal.volume, 'active_positions': active_positions}
            
        except Exception as e:
            logger.error(f"Position size validation error: {e}")
            return {'status': False, 'reason': str(e)}
    
    @error_handler.handle_trading_error
    def adjust_risk_for_conditions(self, signal: TradeSignal) -> Dict:
        """
        Dynamically adjust risk based on market conditions and account state
        Returns adjusted risk parameters
        """
        try:
            adjustments = {
                'original_risk': signal.risk_percentage,
                'adjusted_risk': signal.risk_percentage,
                'reasons': []
            }
            
            # 1. Check drawdown
            weekly_loss = float(signal.session.weekly_realized_r * 0.5)
            if weekly_loss >= self.drawdown_threshold:
                reduction = min(0.5, weekly_loss / self.max_weekly_loss)  # Up to 50% reduction
                adjustments['adjusted_risk'] *= (1 - reduction)
                adjustments['reasons'].append(f'Drawdown adjustment: -{reduction*100:.1f}%')
            
            # 2. Check volatility (implementation depends on your volatility calculation)
            # This is a placeholder - implement your volatility check
            volatility_factor = 1.0  # Calculate this based on your metrics
            if volatility_factor > self.volatility_threshold:
                adjustments['adjusted_risk'] *= 0.75  # Reduce risk by 25% in high volatility
                adjustments['reasons'].append('High volatility adjustment: -25%')
            
            # 3. Apply time-based restrictions
            now = timezone.now().time()
            if now.hour in [14, 15]:  # High-impact news hours
                adjustments['adjusted_risk'] *= 0.5  # Reduce risk by 50%
                adjustments['reasons'].append('High-impact news hours: -50%')
            
            # Apply minimum risk floor
            min_risk = float(os.getenv('MIN_RISK_PERCENTAGE', '0.1'))
            adjustments['adjusted_risk'] = max(min_risk, adjustments['adjusted_risk'])
            
            # Log risk adjustment
            logger.info(f"Risk adjusted from {adjustments['original_risk']}% to {adjustments['adjusted_risk']}%")
            for reason in adjustments['reasons']:
                logger.info(f"Risk adjustment reason: {reason}")
            
            return adjustments
            
        except Exception as e:
            logger.error(f"Risk adjustment error: {e}")
            return {
                'original_risk': signal.risk_percentage,
                'adjusted_risk': signal.risk_percentage,
                'reasons': [f'Error in risk adjustment: {e}']
            }
    
    @error_handler.handle_trading_error
    def calculate_position_size(self, signal: TradeSignal, account_balance: float) -> Dict:
        """
        Calculate safe position size based on risk parameters
        Returns position size and calculations
        """
        try:
            # Get risk adjustments
            risk_adj = self.adjust_risk_for_conditions(signal)
            risk_percentage = risk_adj['adjusted_risk']
            
            # Calculate dollar risk
            risk_amount = account_balance * (risk_percentage / 100)
            
            # Calculate pip value and position size
            pip_value = self._get_pip_value(signal.symbol)
            if not pip_value:
                return {
                    'success': False,
                    'reason': 'Could not determine pip value'
                }
            
            # Calculate stop loss in pips
            sl_pips = abs(signal.entry_price - signal.stop_loss) / pip_value
            
            # Calculate position size
            if sl_pips > 0:
                position_size = risk_amount / (sl_pips * pip_value)
            else:
                return {
                    'success': False,
                    'reason': 'Invalid stop loss distance'
                }
            
            # Apply position size limits
            position_size = min(position_size, self.max_position_size)
            
            # Round to valid lot size
            position_size = self._round_lot_size(position_size)
            
            return {
                'success': True,
                'position_size': position_size,
                'calculations': {
                    'risk_percentage': risk_percentage,
                    'risk_amount': risk_amount,
                    'sl_pips': sl_pips,
                    'pip_value': pip_value,
                    'adjustments': risk_adj['reasons']
                }
            }
            
        except Exception as e:
            logger.error(f"Position size calculation error: {e}")
            return {
                'success': False,
                'reason': str(e)
            }
    
    def _get_pip_value(self, symbol: str) -> Optional[float]:
        """Get pip value for symbol"""
        try:
            pip_values = {
                'XAUUSD': XAUUSD_PIP_VALUE,
                'EURUSD': EURUSD_PIP_VALUE,
                'GBPUSD': GBPUSD_PIP_VALUE,
                'USDJPY': USDJPY_PIP_VALUE
            }
            return pip_values.get(symbol.upper())
        except Exception as e:
            logger.error(f"Error getting pip value: {e}")
            return None
    
    def _round_lot_size(self, size: float) -> float:
        """Round position size to valid lot size"""
        min_lot = MIN_LOT_SIZE
        lot_step = LOT_SIZE_STEP
        
        # Round down to nearest valid lot size
        lots = round(size / lot_step) * lot_step
        
        # Ensure minimum lot size
        return max(min_lot, lots)
