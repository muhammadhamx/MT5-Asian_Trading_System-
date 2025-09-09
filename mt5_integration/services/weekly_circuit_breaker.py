"""
Weekly Circuit Breaker Service - Phase 3 Implementation
Client Spec: Track realized weekly R; if weekly loss ≥ 6R, stop trading
"""

import os
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from typing import Dict, Tuple
from dotenv import load_dotenv
from mt5_integration.utils.strategy_constants import WEEKLY_LOSS_LIMIT_R

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class WeeklyCircuitBreakerService:
    """Manages weekly R tracking and circuit breaker functionality"""
    
    def __init__(self):
        self.weekly_loss_limit_r = WEEKLY_LOSS_LIMIT_R
        
    def check_weekly_circuit_breaker(self, session) -> Dict:
        """Check if weekly circuit breaker should be triggered"""
        try:
            # Get current week boundaries
            week_start, week_end = self._get_current_week_boundaries()
            
            # Calculate current weekly R
            weekly_r = self._calculate_weekly_realized_r(session.symbol, week_start, week_end)
            
            # Check if circuit breaker should trigger
            circuit_breaker_active = weekly_r <= -self.weekly_loss_limit_r
            
            # Update session with weekly data
            session.weekly_realized_r = weekly_r
            session.week_reset_at = week_start
            session.save()
            
            result = {
                'success': True,
                'weekly_realized_r': weekly_r,
                'weekly_loss_limit_r': self.weekly_loss_limit_r,
                'circuit_breaker_active': circuit_breaker_active,
                'week_start': week_start,
                'week_end': week_end,
                'remaining_r_budget': self.weekly_loss_limit_r + weekly_r if weekly_r < 0 else self.weekly_loss_limit_r
            }
            
            if circuit_breaker_active:
                logger.warning(f"Weekly circuit breaker triggered: {weekly_r:.2f}R loss >= {self.weekly_loss_limit_r}R limit")
                result['message'] = f"Weekly circuit breaker active: {weekly_r:.2f}R loss exceeds {self.weekly_loss_limit_r}R limit"
            else:
                logger.info(f"Weekly R tracking: {weekly_r:.2f}R (limit: -{self.weekly_loss_limit_r}R)")
                
            return result
            
        except Exception as e:
            logger.error(f"Weekly circuit breaker check failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'circuit_breaker_active': False  # Fail safe
            }
    
    def _get_current_week_boundaries(self) -> Tuple[datetime, datetime]:
        """Get current week start (Monday) and end (Sunday)"""
        now = timezone.now()
        
        # Get Monday of current week (weekday 0 = Monday)
        days_since_monday = now.weekday()
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        
        # Get Sunday of current week
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return week_start, week_end
    
    def _calculate_weekly_realized_r(self, symbol: str, week_start: datetime, week_end: datetime) -> float:
        """Calculate realized R for the current week"""
        try:
            from ..models import TradeSignal
            
            # Get all completed trades for the week
            weekly_trades = TradeSignal.objects.filter(
                symbol=symbol,
                created_at__gte=week_start,
                created_at__lte=week_end,
                state__in=['CLOSED', 'COMPLETED']
            )
            
            total_r = 0.0
            
            for trade in weekly_trades:
                if trade.calculated_r is not None:
                    total_r += float(trade.calculated_r)
                else:
                    # Calculate R if not stored
                    r_value = self._calculate_trade_r(trade)
                    total_r += r_value
                    
                    # Update trade record
                    trade.calculated_r = r_value
                    trade.save()
            
            return total_r
            
        except Exception as e:
            logger.error(f"Failed to calculate weekly R: {e}")
            return 0.0
    
    def _calculate_trade_r(self, trade) -> float:
        """Calculate R value for a trade"""
        try:
            if not trade.entry_price or not trade.stop_loss:
                return 0.0
                
            # Calculate risk (entry to SL distance)
            risk_distance = abs(float(trade.entry_price) - float(trade.stop_loss))
            
            if risk_distance == 0:
                return 0.0
                
            # Calculate actual P&L distance
            if trade.state == 'CLOSED' and hasattr(trade, 'exit_price') and trade.exit_price:
                pnl_distance = float(trade.exit_price) - float(trade.entry_price)
                
                # Adjust for trade direction
                if trade.signal_type == 'SELL':
                    pnl_distance = -pnl_distance
                    
                # Calculate R
                r_value = pnl_distance / risk_distance
                return r_value
            else:
                return 0.0  # Trade not closed yet
                
        except Exception as e:
            logger.error(f"Failed to calculate R for trade {trade.id}: {e}")
            return 0.0
    
    def reset_weekly_tracking(self, session) -> Dict:
        """Reset weekly tracking (called at start of new week)"""
        try:
            week_start, week_end = self._get_current_week_boundaries()
            
            session.weekly_realized_r = 0.0
            session.week_reset_at = week_start
            session.save()
            
            logger.info(f"Weekly tracking reset for new week starting {week_start.strftime('%Y-%m-%d')}")
            
            return {
                'success': True,
                'message': 'Weekly tracking reset',
                'week_start': week_start,
                'week_end': week_end
            }
            
        except Exception as e:
            logger.error(f"Failed to reset weekly tracking: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_weekly_summary(self, symbol: str) -> Dict:
        """Get weekly trading summary"""
        try:
            week_start, week_end = self._get_current_week_boundaries()
            
            from ..models import TradeSignal, TradingSession
            
            # Get weekly trades
            weekly_trades = TradeSignal.objects.filter(
                symbol=symbol,
                created_at__gte=week_start,
                created_at__lte=week_end
            )
            
            # Get weekly sessions
            weekly_sessions = TradingSession.objects.filter(
                symbol=symbol,
                session_date__gte=week_start.date(),
                session_date__lte=week_end.date()
            )
            
            # Calculate statistics
            total_trades = weekly_trades.count()
            completed_trades = weekly_trades.filter(state__in=['CLOSED', 'COMPLETED']).count()
            winning_trades = weekly_trades.filter(calculated_r__gt=0).count()
            losing_trades = weekly_trades.filter(calculated_r__lt=0).count()
            
            # Calculate total R
            total_r = sum(float(trade.calculated_r or 0) for trade in weekly_trades)
            
            # Win rate
            win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0
            
            return {
                'success': True,
                'week_start': week_start,
                'week_end': week_end,
                'total_trades': total_trades,
                'completed_trades': completed_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'total_r': total_r,
                'win_rate': win_rate,
                'weekly_loss_limit_r': self.weekly_loss_limit_r,
                'circuit_breaker_active': total_r <= -self.weekly_loss_limit_r,
                'remaining_r_budget': self.weekly_loss_limit_r + total_r if total_r < 0 else self.weekly_loss_limit_r
            }
            
        except Exception as e:
            logger.error(f"Failed to get weekly summary: {e}")
            return {
                'success': False,
                'error': str(e)
            }
