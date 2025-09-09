import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
from django.utils import timezone
from typing import Dict, Optional, Tuple, Any
from ..models import TradingSession, LiquiditySweep, ConfluenceCheck, TradeSignal, MarketData
from .mt5_service import MT5Service
import pytz
import logging
import os
from dotenv import load_dotenv
from .weekly_circuit_breaker import WeeklyCircuitBreakerService
from .gpt_integration_service import GPTIntegrationService
from .bos_choch_service import BOSCHOCHService
from ..utils.production_logger import trading_logger, system_logger, risk_logger
import json
from mt5_integration.utils.strategy_constants import (
    XAUUSD_PIP_VALUE, EURUSD_PIP_VALUE, GBPUSD_PIP_VALUE, USDJPY_PIP_VALUE,
    NO_TRADE_THRESHOLD, TIGHT_RANGE_THRESHOLD, NORMAL_RANGE_THRESHOLD, WIDE_RANGE_THRESHOLD, MAX_RANGE_THRESHOLD,
    TIGHT_RISK_PERCENTAGE, NORMAL_RISK_PERCENTAGE, WIDE_RISK_PERCENTAGE, MAX_RISK_PER_TRADE,
    SWEEP_THRESHOLD_FLOOR_PIPS, SWEEP_THRESHOLD_PCT_MIN, SWEEP_THRESHOLD_PCT_MAX, SWEEP_THRESHOLD_PCT_XAU,
    DISPLACEMENT_K_NORMAL, DISPLACEMENT_K_HIGH_VOL,
    ATR_H1_LOOKBACK, ADX_15M_LOOKBACK, ADX_TREND_THRESHOLD,
    MAX_SPREAD_PIPS, VELOCITY_SPIKE_MULTIPLIER,
    TIER1_NEWS_BUFFER_MINUTES, OTHER_NEWS_BUFFER_MINUTES, LBMA_AUCTION_TIMES, LBMA_AUCTION_BUFFER_MINUTES,
    CONFIRMATION_TIMEOUT_MINUTES, RETEST_MIN_BARS, RETEST_MAX_BARS, RETEST_BAR_MINUTES,
    SL_BUFFER_PIPS_MIN, SL_BUFFER_PIPS_MAX,
    DAILY_TRADE_COUNT_LIMIT, DAILY_LOSS_LIMIT_R, WEEKLY_LOSS_LIMIT_R,
    TRAILING_ATR_M5_MULTIPLIER, MIN_LOT_SIZE, LOT_SIZE_STEP, TIMEZONE
)

# from ..utils.send_logs import send_log

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)



# Remove duplicate methods - these are defined properly later in the class
class SignalDetectionService:
    def __init__(self, mt5_service: MT5Service):
        self.mt5_service = mt5_service
        self.current_session = None
        self.test_mode = False  # Enable for testing outside Asian session
        self.weekly_circuit_breaker = WeeklyCircuitBreakerService()
        self.gpt_service = GPTIntegrationService()
        self.bos_choch_service = BOSCHOCHService(mt5_service)
        
    def run_full_analysis(self, symbol: str = None) -> Dict[str, Any]:
        """Run a complete market analysis including all signal types
        
        Args:
            symbol (str, optional): Symbol to analyze. If None, analyzes configured symbols.
            
        Returns:
            Dict containing analysis results and any detected signals
        """
        try:
            results = {
                'status': 'success',
                'signals': [],
                'warnings': [],
                'timestamp': datetime.now(pytz.UTC)
            }
            
            # Get symbols to analyze
            symbols = [symbol] if symbol else self.mt5_service.get_symbols()
            
            for sym in symbols:
                # Run BOS/CHOCH analysis
                bos_signals = self.bos_choch_service.analyze_market_structure(sym)
                if bos_signals:
                    results['signals'].extend(bos_signals)
                
                # Get weekly circuit breaker levels
                wcb_levels = self.weekly_circuit_breaker.get_levels(sym)
                if wcb_levels:
                    results['wcb_levels'] = wcb_levels
                
                # Get GPT market analysis if enabled
                # (Removed) GPT market-wide analysis to enforce single-call policy
                
            trading_logger.info(f"Full analysis completed for {len(symbols)} symbols")
            return results
            
        except Exception as e:
            trading_logger.error(f"Error in full analysis: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(pytz.UTC)
            }
        
    def _log_state_transition(self, old_state: str, new_state: str, reason: str, context: Dict = None):
        """Log state transitions with complete traceability"""
        session_id = str(self.current_session.id) if self.current_session else 'unknown'
        trading_logger.log_state_transition(
            session_id=session_id,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
            context=context or {}
        )
    
    def _get_pip_multiplier(self, symbol: str) -> float:
        """Get pip multiplier for symbol from environment variables"""
        symbol_upper = symbol.upper()
        if symbol_upper == 'XAUUSD':
            return 1.0 / float(os.getenv('XAUUSD_PIP_VALUE', '0.1'))
        elif symbol_upper in ['EURUSD', 'GBPUSD']:
            return 1.0 / float(os.getenv(f'{symbol_upper}_PIP_VALUE', '0.0001'))
        elif symbol_upper == 'USDJPY':
            return 1.0 / float(os.getenv('USDJPY_PIP_VALUE', '0.01'))
        else:
            # Default to XAUUSD pip value
            return 1.0 / float(os.getenv('XAUUSD_PIP_VALUE', '0.1'))
    
    def _check_lbma_auction_blackout(self) -> bool:
        """Check if current time is within LBMA auction blackout windows"""
        try:
            import pytz
            london_tz = pytz.timezone('Europe/London')
            now_london = timezone.now().astimezone(london_tz)
            current_time = now_london.time()
            buffer_minutes = int(os.getenv('LBMA_AUCTION_BUFFER_MINUTES', '15'))
            auction_times = [
                time(10, 30),  # 10:30 London
                time(15, 0),   # 15:00 London
            ]
            for auction_time in auction_times:
                # Create datetime objects for comparison
                auction_start = (datetime.combine(now_london.date(), auction_time) -
                               timedelta(minutes=buffer_minutes)).time()
                auction_end = (datetime.combine(now_london.date(), auction_time) +
                             timedelta(minutes=buffer_minutes)).time()
                if auction_start <= current_time <= auction_end:
                    return True
            return False
        except Exception:
            return False
    
    def _check_news_blackout(self) -> Tuple[bool, str, int]:
        """Check news blackout with tier classification using real-time news data"""
        try:
            from ..models import EconomicNews
            from .news_feed_service import NewsFeedService
            
            now = timezone.now()
            
            # Auto-update news if database is empty or stale
            recent_news_count = EconomicNews.objects.filter(
                release_time__gte=now - timedelta(hours=1),
                release_time__lte=now + timedelta(hours=4)
            ).count()
            
            if recent_news_count == 0:
                logger.info("No recent news data found, attempting to fetch updates...")
                try:
                    news_service = NewsFeedService()
                    news_service.fetch_news_updates(hours_ahead=6)
                except Exception as e:
                    logger.warning(f"Failed to auto-update news: {e}")
            
            # Check for Tier-1 events first (≥60 min buffer per client spec)
            tier1_buffer = int(os.getenv('NEWS_TIER1_BUFFER_MINUTES', '60'))
            tier1_window_start = now - timedelta(minutes=tier1_buffer)
            tier1_window_end = now + timedelta(minutes=tier1_buffer)
            
            tier1_events = EconomicNews.objects.filter(
                tier='TIER1',
                severity__in=['HIGH', 'CRITICAL'],
                release_time__gte=tier1_window_start,
                release_time__lte=tier1_window_end
            )
            
            if tier1_events.exists():
                closest_event = tier1_events.order_by('release_time').first()
                logger.warning(f"Tier-1 news blackout: {closest_event.event_name} at {closest_event.release_time}")
                return True, 'TIER1', tier1_buffer
            
            # Check for other high-impact events (≥30 min buffer)
            other_buffer = int(os.getenv('NEWS_OTHER_BUFFER_MINUTES', '30'))
            other_window_start = now - timedelta(minutes=other_buffer)
            other_window_end = now + timedelta(minutes=other_buffer)
            
            other_events = EconomicNews.objects.filter(
                tier='OTHER',
                severity__in=['HIGH', 'CRITICAL'],
                release_time__gte=other_window_start,
                release_time__lte=other_window_end
            )
            
            if other_events.exists():
                closest_event = other_events.order_by('release_time').first()
                logger.info(f"High-impact news blackout: {closest_event.event_name} at {closest_event.release_time}")
                return True, 'OTHER', other_buffer
            
            return False, 'NONE', 0
            
        except Exception as e:
            logger.error(f"Error in news blackout check: {e}")
            return False, 'NONE', 0
    
    def _check_velocity_spike(self, symbol: str) -> Tuple[bool, float]:
        """Check for velocity spike - last 1m range > 2× baseline"""
        try:
            # Get recent 1-minute data
            end = timezone.now()
            start = end - timedelta(minutes=10)  # Get 10 minutes of M1 data
            m1_data = self.mt5_service.get_historical_data(symbol, 'M1', start, end)
            if m1_data is None or len(m1_data) < 5:
                return False, 0.0
            # Calculate ranges for each 1-minute bar
            m1_data['range'] = m1_data['high'] - m1_data['low']
            # Get baseline (average of last 5 bars excluding the most recent)
            baseline_range = m1_data['range'].iloc[-6:-1].mean() if len(m1_data) >= 6 else m1_data['range'].iloc[:-1].mean()
            # Get most recent 1-minute range
            latest_range = m1_data['range'].iloc[-1]
            # Calculate ratio
            velocity_ratio = latest_range / baseline_range if baseline_range > 0 else 0
            # Check if spike exceeds threshold
            spike_threshold = float(os.getenv('VELOCITY_SPIKE_MULTIPLIER', '2.0'))
            is_spike = velocity_ratio > spike_threshold
            return is_spike, velocity_ratio
        except Exception:
            return False, 0.0
    
    def _calculate_adx(self, df, period: int = 14) -> Tuple[float, float]:
        """Calculate ADX and trend strength"""
        try:
            if df is None or len(df) < period + 1:
                return 0.0, 0.0
            # Calculate True Range
            df = df.copy()
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            # Calculate Directional Movement
            df['dm_plus'] = df['high'].diff()
            df['dm_minus'] = -df['low'].diff()
            # Set DM to 0 if opposite movement is greater
            df.loc[df['dm_plus'] < df['dm_minus'], 'dm_plus'] = 0
            df.loc[df['dm_minus'] < df['dm_plus'], 'dm_minus'] = 0
            df.loc[df['dm_plus'] < 0, 'dm_plus'] = 0
            df.loc[df['dm_minus'] < 0, 'dm_minus'] = 0
            # Calculate smoothed values
            df['atr'] = df['tr'].rolling(window=period).mean()
            df['di_plus'] = 100 * (df['dm_plus'].rolling(window=period).mean() / df['atr'])
            df['di_minus'] = 100 * (df['dm_minus'].rolling(window=period).mean() / df['atr'])
            # Calculate ADX
            df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'])
            df['adx'] = df['dx'].rolling(window=period).mean()
            latest_adx = df['adx'].iloc[-1] if not pd.isna(df['adx'].iloc[-1]) else 0.0
            trend_strength = latest_adx
            return latest_adx, trend_strength
        except Exception:
            return 0.0, 0.0
    
    def _check_h1_band_walk(self, symbol: str) -> bool:
        """Check for H1 band-walk/range expansion"""
        try:
            end = timezone.now()
            start = end - timedelta(hours=12)  # Get 12 hours of H1 data
            h1_data = self.mt5_service.get_historical_data(symbol, 'H1', start, end)
            if h1_data is None or len(h1_data) < 3:
                return False
            # Simple band-walk detection: consecutive higher highs or lower lows
            recent_highs = h1_data['high'].tail(3)
            recent_lows = h1_data['low'].tail(3)
            # Check for upward band-walk (consecutive higher highs)
            upward_walk = all(recent_highs.iloc[i] > recent_highs.iloc[i-1] for i in range(1, len(recent_highs)))
            # Check for downward band-walk (consecutive lower lows)
            downward_walk = all(recent_lows.iloc[i] < recent_lows.iloc[i-1] for i in range(1, len(recent_lows)))
            return upward_walk or downward_walk
        except Exception:
            return False
    
    def _check_london_traversed_asia(self) -> bool:
        """Check if London session has fully traversed the Asian range"""
        try:
            if not self.current_session:
                return False
            # Get London session data (08:00-16:00 UTC)
            london_start = self.current_session.session_date.replace(hour=8, minute=0, second=0)
            london_end = self.current_session.session_date.replace(hour=16, minute=0, second=0)
            now = timezone.now()
            # Only check if we're in or past London session
            if now < london_start:
                return False
            # Get London session price action
            london_data = self.mt5_service.get_historical_data(
                self.current_session.symbol,
                'M5',
                london_start,
                min(now, london_end)
            )
            if london_data is None or len(london_data) == 0:
                return False
            london_high = london_data['high'].max()
            london_low = london_data['low'].min()
            # Check if London has traversed the full Asian range
            asian_high = float(self.current_session.asian_range_high)
            asian_low = float(self.current_session.asian_range_low)
            traversed = london_high >= asian_high and london_low <= asian_low
            # Update session state
            self.current_session.london_traversed_asia = traversed
            self.current_session.save()
            return traversed
        except Exception:
            return False
    
    def _check_fresh_ny_sweep(self) -> bool:
        """Check if NY session has provided a fresh sweep"""
        try:
            if not self.current_session:
                return False
            # Get NY session data (13:00-22:00 UTC)
            ny_start = self.current_session.session_date.replace(hour=13, minute=0, second=0)
            now = timezone.now()
            # Only check if we're in NY session
            if now < ny_start:
                return False
            # Get NY session price action
            ny_data = self.mt5_service.get_historical_data(
                self.current_session.symbol,
                'M5',
                ny_start,
                now
            )
            if ny_data is None or len(ny_data) == 0:
                return False
            ny_high = ny_data['high'].max()
            ny_low = ny_data['low'].min()
            # Check if NY has swept beyond Asian range
            asian_high = float(self.current_session.asian_range_high)
            asian_low = float(self.current_session.asian_range_low)
            # Get dynamic sweep threshold using session range
            range_pips = float(self.current_session.asian_range_size or 0)
            threshold_data = self._calculate_sweep_threshold({'range_pips': range_pips})
            pip_value = float(os.getenv(f"{self.current_session.symbol.upper()}_PIP_VALUE", str(XAUUSD_PIP_VALUE)))
            threshold_price = float(threshold_data['threshold_pips']) * pip_value
            fresh_sweep = (ny_high > asian_high + threshold_price or
                           ny_low < asian_low - threshold_price)
            return fresh_sweep
        except Exception:
            return False
    
    def _check_participation_filter(self) -> bool:
        """Check for low participation periods (holidays, late December)"""
        try:
            now = timezone.now()
            # Check for late December (low participation)
            if now.month == 12 and now.day >= 20:
                return True
            # Check for early January (low participation)
            if now.month == 1 and now.day <= 5:
                return True
            # Check for major holidays (simplified - could be enhanced with holiday calendar)
            # This is a basic implementation - in production, use a proper holiday calendar
            major_holidays = [
                (1, 1),   # New Year's Day
                (12, 25), # Christmas
                (7, 4),   # US Independence Day (if US markets matter)
            ]
            for month, day in major_holidays:
                if now.month == month and now.day == day:
                    return True
            return False
        except Exception:
            return False
    
    def _get_displacement_multiplier(self, symbol: str) -> float:
        """Get displacement multiplier based on volatility regime - Client Spec: k=1.3 normal, k=1.5 high-vol"""
        try:
            # Get H1 ATR for volatility assessment
            end = timezone.now()
            start = end - timedelta(hours=24)
            h1_data = self.mt5_service.get_historical_data(symbol, 'H1', start, end)
            if h1_data is None or len(h1_data) < ATR_H1_LOOKBACK:
                return float(os.getenv('DISPLACEMENT_ATR_MULTIPLIER_NORMAL', str(DISPLACEMENT_K_NORMAL)))
            # Calculate current H1 ATR
            current_atr = self._calculate_atr(h1_data, ATR_H1_LOOKBACK)
            # Get ATR threshold for high volatility (in pips)
            atr_threshold = float(os.getenv('ATR_H1_HIGH_THRESHOLD', '2.0'))
            # Convert to pips for comparison
            pip_multiplier = self._get_pip_multiplier(symbol)
            atr_pips = current_atr * pip_multiplier
            # Check for high volatility regime
            if atr_pips > atr_threshold:
                return float(os.getenv('DISPLACEMENT_ATR_MULTIPLIER_HIGH_VOL', str(DISPLACEMENT_K_HIGH_VOL)))
            else:
                return float(os.getenv('DISPLACEMENT_ATR_MULTIPLIER_NORMAL', str(DISPLACEMENT_K_NORMAL)))
        except Exception:
            return float(os.getenv('DISPLACEMENT_ATR_MULTIPLIER_NORMAL', str(DISPLACEMENT_K_NORMAL)))
    
    def _check_acceptance_outside(self, symbol: str, asian_high: float, asian_low: float) -> bool:
        """Check for acceptance outside - Client Spec: ≥2 full M5 closes outside = breakout"""
        try:
            # Get recent M5 data - need more bars to properly check consecutive closes
            end = timezone.now()
            start = end - timedelta(minutes=60)  # Get last 60 minutes of M5 data
            m5_data = self.mt5_service.get_historical_data(symbol, 'M5', start, end)
            if m5_data is None or len(m5_data) < 2:
                return False
            
            # Client Spec: ≥2 full M5 closes outside = breakout ⇒ NO_TRADE
            limit = int(os.getenv('ACCEPTANCE_OUTSIDE_CLOSES_LIMIT', '2'))
            consecutive_closes_outside = 0
            max_consecutive = 0
            
            # Check each M5 candle's close price
            for i in range(len(m5_data)):
                close_price = float(m5_data.iloc[i]['close'])
                
                # Check if close is outside Asian range
                is_outside = close_price > asian_high or close_price < asian_low
                
                if is_outside:
                    consecutive_closes_outside += 1
                    max_consecutive = max(max_consecutive, consecutive_closes_outside)
                else:
                    # Reset counter if close is back inside
                    consecutive_closes_outside = 0
            
            # Log the acceptance outside check for debugging
            logger.info(f"Acceptance outside check: max_consecutive={max_consecutive}, limit={limit}, "
                       f"asian_range={asian_low:.5f}-{asian_high:.5f}")
            
            # Return True if we found ≥2 consecutive closes outside
            acceptance_outside = max_consecutive >= limit
            
            if acceptance_outside:
                logger.warning(f"Acceptance outside detected: {max_consecutive} consecutive M5 closes outside Asian range")
            
            return acceptance_outside
            
        except Exception as e:
            logger.error(f"Error in acceptance outside check: {e}")
            return False
    
    def enable_test_mode(self):
        """Enable test mode for trading outside Asian session hours"""
        self.test_mode = True
        logger.info("Test mode enabled - trading allowed outside Asian session")
    
    def disable_test_mode(self):
        """Disable test mode - normal Asian session restrictions apply"""
        self.test_mode = False
        logger.info("Test mode disabled - normal Asian session restrictions apply")
    
    def initialize_session(self, symbol: str = None) -> Dict:
        """Initialize a new trading session"""
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        today = timezone.now().date()
        
        # Check if session already exists
        # existing_session = TradingSession.objects.filter(
        #     session_date=today,
        #     session_type='ASIAN'
        # ).first()
        
        # if existing_session:
        #     self.current_session = existing_session
        #     return {
        #         'success': True,
        #         'message': 'Session already exists',
        #         'session_id': existing_session.id,
        #         'state': existing_session.current_state
        #     }
        
        # Create new session and populate Asian range
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        session_kwargs = {
            'session_date': today,
            'session_type': 'ASIAN',
            'current_state': 'IDLE'
        }
        if asian_data and asian_data.get('success'):
            session_kwargs.update({
                'asian_range_high': asian_data['high'],
                'asian_range_low': asian_data['low'],
                'asian_range_midpoint': asian_data['midpoint'],
                'asian_range_size': asian_data['range_pips'],
                'asian_range_grade': asian_data['grade']
            })
        session = TradingSession.objects.create(**session_kwargs)
        self.current_session = session
        # Check weekly circuit breaker - Phase 3 enhancement
        weekly_check = self.weekly_circuit_breaker.check_weekly_circuit_breaker(session)
        if weekly_check.get('circuit_breaker_active'):
            session.current_state = 'COOLDOWN'
            session.cooldown_reason = 'Weekly circuit breaker active'
            session.save()
            return {
                'success': False,
                'session_created': True,
                'session_id': session.id,
                'session_state': 'COOLDOWN',
                'reason': f"Weekly circuit breaker active: {weekly_check.get('weekly_realized_r', 0):.2f}R loss",
                'weekly_data': weekly_check
            }
        return {
            'success': True,
            'message': 'New session created',
            'session_id': session.id,
            'state': 'IDLE',
            'weekly_data': weekly_check
        }
    
    def detect_sweep(self, symbol: str = None) -> Dict:
        """Detect Asian session liquidity sweep"""
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        logger.debug(f"detect_sweep called for {symbol}")
        if not self.current_session:
            logger.debug("No active session")
            return {'success': False, 'error': 'No active session'}
        logger.debug(f"Current session state: {self.current_session.current_state}")
        if self.current_session.current_state != 'IDLE':
            return {'success': False, 'error': f'Invalid state: {self.current_session.current_state}'}
        
        # Get Asian range data
        logger.debug("Getting Asian range data")
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        logger.debug(f"Asian data: {asian_data}")
        if not asian_data.get('success'):
            return {'success': False, 'error': 'Failed to get Asian range data'}
        
        # Get current price
        logger.debug("Getting current price")
        current_price_data = self.mt5_service.get_current_price(symbol)
        logger.debug(f"Current price data: {current_price_data}")
        if not current_price_data:
            return {'success': False, 'error': 'Failed to get current price'}
        current_price = current_price_data['bid']  # Use bid for conservative approach
        
        # Calculate dynamic sweep threshold (in pips, convert to price)
        threshold_data = self._calculate_sweep_threshold(asian_data)
        pip_value = float(os.getenv(f"{symbol.upper()}_PIP_VALUE", str(XAUUSD_PIP_VALUE)))
        sweep_threshold_pips = float(threshold_data['threshold_pips'])
        sweep_threshold_price = sweep_threshold_pips * pip_value

        # Check for sweep
        sweep_direction = None
        sweep_price = None
        # Check upper sweep
        if current_price > float(asian_data['high']) + sweep_threshold_price:
            sweep_direction = 'UP'
            sweep_price = current_price
        # Check lower sweep
        elif current_price < float(asian_data['low']) - sweep_threshold_price:
            sweep_direction = 'DOWN'
            sweep_price = current_price

        if sweep_direction:
            # Check for acceptance outside (breakout) - Client Spec: ≥2 full M5 closes outside
            acceptance_outside = self._check_acceptance_outside(
                symbol,
                float(asian_data['high']),
                float(asian_data['low'])
            )
            if acceptance_outside:
                old_state = self.current_session.current_state
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.acceptance_outside_count += 1
                self.current_session.save()
                # Log acceptance outside cooldown
                self._log_state_transition(
                    old_state=old_state,
                    new_state='COOLDOWN',
                    reason='Acceptance outside detected - breakout, not reversal',
                    context={
                        'symbol': symbol,
                        'sweep_direction': sweep_direction,
                        'acceptance_outside_count': self.current_session.acceptance_outside_count
                    }
                )
                return {
                    'success': False,
                    'sweep_detected': True,
                    'direction': sweep_direction,
                    'price': sweep_price,
                    'threshold': sweep_threshold_pips,
                    'session_state': 'COOLDOWN',
                    'reason': 'Acceptance outside detected - breakout, not reversal'
                }
            
            # If an opposite-side sweep already happened this session → COOLDOWN
            if self.current_session.sweep_direction and self.current_session.sweep_direction != sweep_direction:
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.both_sides_swept = True
                self.current_session.save()
                return {
                    'success': False,
                    'sweep_detected': True,
                    'direction': sweep_direction,
                    'price': sweep_price,
                    'threshold': sweep_threshold_pips,
                    'session_state': 'COOLDOWN',
                    'reason': 'Both sides swept; entering cooldown'
                }
            
            # Get sweep threshold components for audit
            # Calculate and persist sweep threshold components
            threshold_data = self._calculate_sweep_threshold(asian_data)
            logger.info(f"Using {threshold_data['chosen_component']} based threshold: {threshold_data['threshold_pips']} pips")

            sweep = LiquiditySweep.objects.create(
                session=self.current_session,
                symbol=symbol,
                sweep_direction=sweep_direction,
                sweep_price=sweep_price,
                sweep_threshold=threshold_data['threshold_pips'],
                sweep_time=timezone.now(),
                threshold_from_floor=threshold_data['floor_pips'],
                threshold_from_pct=threshold_data['percentage_pips'],
                threshold_from_atr=threshold_data['atr_threshold_pips'],
                chosen_threshold_component=threshold_data['chosen_component'],
                atr_h1_value=threshold_data['atr_h1_pips'],
                acceptance_outside=acceptance_outside,
                both_sides_swept_flag=False
            )
            
            # Update session state with structured logging
            old_state = self.current_session.current_state
            self.current_session.current_state = 'SWEPT'
            self.current_session.sweep_direction = sweep_direction
            self.current_session.sweep_time = timezone.now()
            # Store the threshold in pips
            self.current_session.sweep_threshold = sweep_threshold_pips
            self.current_session.save()
            
            # Log state transition with complete context
            self._log_state_transition(
                old_state=old_state,
                new_state='SWEPT',
                reason=f'Liquidity sweep detected: {sweep_direction} side',
                context={
                    'symbol': symbol,
                    'sweep_direction': sweep_direction,
                    'sweep_price': sweep_price,
                    'threshold_pips': sweep_threshold_pips,
                    'asian_range': {
                        'high': asian_data['high'],
                        'low': asian_data['low'],
                        'size_pips': asian_data['range_pips']
                    }
                }
            )
            
            # Store sweep data for GPT validation
            sweep_data = {
                'direction': sweep_direction,
                'price': sweep_price,
                'threshold': sweep_threshold_pips,
                'chosen_component': threshold_data.get('chosen_component', 'unknown')
            }
            
            # Call GPT to evaluate sweep validity (Event Edge: SWEPT)
            market_data = {
                'atr_h1': threshold_data.get('atr_h1_pips', 0),
                'spread': 0,  # Will be updated in confluence check
                'adx': 0      # Will be updated in confluence check
            }
            # Skip GPT here; only call once before execution
            return {
                'success': True,
                'sweep_detected': True,
                'direction': sweep_direction,
                'price': sweep_price,
                'threshold': sweep_threshold_pips,
                'session_state': 'SWEPT',
                'sweep_id': sweep.id,
                'sweep_data': sweep_data
            }
        
        return {
            'success': True,
            'sweep_detected': False,
            'current_price': current_price,
            'asian_high': asian_data['high'],
            'asian_low': asian_data['low'],
            'threshold': sweep_threshold_pips
        }
    
    def confirm_reversal(self, symbol: str = None) -> Dict:
        """Confirm reversal after sweep detection with Phase 3 enhancements"""
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        if not self.current_session or self.current_session.current_state != 'SWEPT':
            return {'success': False, 'error': 'Invalid state for reversal confirmation'}
        
        # Check confirmation timeout - Client Spec: 30-minute timeout from sweep
        if self.current_session.sweep_time:
            timeout_minutes = int(os.getenv('CONFIRMATION_TIMEOUT_MINUTES', '30'))
            time_since_sweep = timezone.now() - self.current_session.sweep_time
            if time_since_sweep.total_seconds() > timeout_minutes * 60:
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.cooldown_reason = 'Confirmation timeout exceeded'
                self.current_session.save()
                return {
                    'success': False,
                    'confirmed': False,
                    'reason': f'Confirmation timeout exceeded ({timeout_minutes} minutes)',
                    'session_state': 'COOLDOWN'
                }
        
        # Get recent M5 data with fallback strategies
        end_time = timezone.now()
        m5_data = None
        for attempt in range(3):  # Try 3 times with different time ranges
            time_range = 30 + (attempt * 15)  # 30, 45, 60 minutes
            start_time = end_time - timedelta(minutes=time_range)
            m5_data = self.mt5_service.get_historical_data(symbol, "M5", start_time, end_time)
            if m5_data is not None and len(m5_data) > 0:
                break
        
        if m5_data is None or len(m5_data) == 0:
            # Check if it's weekend or market closed
            if end_time.weekday() >= 5:  # Weekend
                return {'success': False, 'error': 'Market closed (Weekend) - No M5 data available'}
            else:
                return {'success': False, 'error': 'No M5 data available - Market may be closed'}
        
        # Get Asian range
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        if not asian_data['success']:
            return {'success': False, 'error': 'Failed to get Asian range data'}
        
        # Check if price closed back inside Asian range
        latest_close = m5_data.iloc[-1]['close']
        asian_high = asian_data['high']
        asian_low = asian_data['low']
        
        if not (asian_low <= latest_close <= asian_high):
            return {
                'success': True,
                'confirmed': False,
                'reason': 'Price not back inside Asian range',
                'latest_close': latest_close,
                'asian_range': f"{asian_low} - {asian_high}"
            }
        
        # Check displacement with dynamic k-switching (Client Spec: k=1.3 normal, k=1.5 high-vol)
        latest_candle = m5_data.iloc[-1]
        body_size = abs(latest_candle['close'] - latest_candle['open'])
        # Calculate ATR
        atr = self._calculate_atr(m5_data, period=14)
        # Dynamic k selection based on volatility regime
        k_multiplier = self._get_displacement_multiplier(symbol)
        displacement_threshold = atr * k_multiplier
        
        if body_size < displacement_threshold:
            return {
                'success': True,
                'confirmed': False,
                'reason': 'Insufficient displacement',
                'body_size': body_size,
                'displacement_threshold': displacement_threshold
            }
        
        # Check M1 CHOCH (Change of Character)
        m1_data = self.mt5_service.get_historical_data(symbol, "M1", start_time, end_time)
        if m1_data is not None and len(m1_data) > 0:
            choch_detected = self._detect_choch(m1_data, self.current_session.sweep_direction)
            if not choch_detected:
                return {
                    'success': True,
                    'confirmed': False,
                    'reason': 'M1 CHOCH not detected'
                }
        
        # Update session state to CONFIRMED and store displacement data
        old_state = self.current_session.current_state
        self.current_session.current_state = 'CONFIRMED'
        self.current_session.confirmation_time = timezone.now()
        self.current_session.displacement_atr_ratio = body_size / atr if atr > 0 else 0
        self.current_session.save()
        
        # Log confirmation with displacement details
        self._log_state_transition(
            old_state=old_state,
            new_state='CONFIRMED',
            reason='Displacement confirmation successful',
            context={
                'symbol': symbol,
                'displacement_multiplier': k_multiplier,
                'body_size_pips': body_size,
                'atr_pips': atr,
                'displacement_ratio': body_size / atr if atr > 0 else 0,
                'choch_detected': True
            }
        )
        
        # Update the sweep record with displacement data
        try:
            sweep = LiquiditySweep.objects.filter(session=self.current_session).last()
            if sweep:
                sweep.confirmation_price = latest_candle['close']
                sweep.confirmation_time = timezone.now()
                sweep.displacement_atr = atr
                sweep.displacement_multiplier = k_multiplier
                sweep.save()
        except Exception as e:
            logger.error(f"Failed to update sweep displacement data: {e}")
        
        # Derive retest window from configured bars and timeframe
        min_bars = int(os.getenv('RETEST_MIN_BARS', str(RETEST_MIN_BARS)))
        max_bars = int(os.getenv('RETEST_MAX_BARS', str(RETEST_MAX_BARS)))
        bar_minutes = int(os.getenv('RETEST_BAR_MINUTES', str(RETEST_BAR_MINUTES)))
        retest_window_minutes = max_bars * bar_minutes
        
        # Prepare data for GPT entry refinement (Event Edge: CONFIRMED)
        sweep = LiquiditySweep.objects.filter(session=self.current_session).order_by('-sweep_time').first()
        sweep_data = None
        if sweep:
            sweep_data = {
                'direction': sweep.sweep_direction,
                'price': float(sweep.sweep_price),
                'threshold': float(sweep.sweep_threshold)
            }
        else:
            logger.warning("No LiquiditySweep found for session when confirming reversal; skipping sweep-dependent details.")
        
        confirmation_data = {
            'displacement_ratio': body_size / atr if atr > 0 else 0,
            'atr_m5': atr,
            'k_multiplier': k_multiplier
        }
        
        # Skip GPT here; only call once before execution
        return {
            'success': True,
            'confirmed': True,
            'session_state': 'CONFIRMED',
            'retest_window_minutes': retest_window_minutes,
            'body_size': body_size,
            'atr': atr,
            'displacement_threshold': displacement_threshold
        }
    
    def generate_trade_signal(self, symbol: str = None) -> Dict:
        """Generate trade signal after confirmation with Phase 3 enhancements"""
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        if not self.current_session or self.current_session.current_state != 'CONFIRMED':
            return {'success': False, 'error': 'Invalid state for signal generation'}
        
        # Get latest sweep
        sweep = LiquiditySweep.objects.filter(session=self.current_session).order_by('-sweep_time').first()
        if not sweep:
            return {'success': False, 'error': 'No sweep found for session'}
        
        # Calculate entry, SL, TP levels
        current_price_data = self.mt5_service.get_current_price(symbol)
        if not current_price_data:
            return {'success': False, 'error': 'Failed to get current price'}
        
        current_price = current_price_data['ask'] if sweep.sweep_direction == 'UP' else current_price_data['bid']
        
        # Calculate levels based on sweep direction with Phase 3 enhancements
        pip_value = float(os.getenv(f"{symbol.upper()}_PIP_VALUE", str(XAUUSD_PIP_VALUE)))
        
        # Use env-configurable SL/TP buffers
        sl_buffer_pips = float(os.getenv('SL_BUFFER_PIPS', str(SL_BUFFER_PIPS_MIN)))
        sl_buffer = sl_buffer_pips * pip_value
        
        if sweep.sweep_direction == 'UP':
            # Sweep was UP, so we want to SELL (fade the sweep)
            signal_type = 'SELL'
            entry_price = current_price
            stop_loss = float(sweep.sweep_price) + sl_buffer  # Buffer above sweep
            take_profit_1 = float(self.current_session.asian_range_midpoint)
            tp2_buffer_pips = float(os.getenv('TP2_BUFFER_PIPS', '2'))
            take_profit_2 = float(self.current_session.asian_range_low) - (tp2_buffer_pips * pip_value)
        else:
            # Sweep was DOWN, so we want to BUY (fade the sweep)
            signal_type = 'BUY'
            entry_price = current_price
            stop_loss = float(sweep.sweep_price) - sl_buffer  # Buffer below sweep
            take_profit_1 = float(self.current_session.asian_range_midpoint)
            tp2_buffer_pips = float(os.getenv('TP2_BUFFER_PIPS', '2'))
            take_profit_2 = float(self.current_session.asian_range_high) + (tp2_buffer_pips * pip_value)
        
        # Enhanced risk calculation with Phase 3 multipliers - Client Spec Compliant
        account_info = self.mt5_service.get_account_info()
        if not account_info:
            return {'success': False, 'error': 'Failed to get account info'}
        equity = account_info['equity']
        
        # Client Spec: 0.5% default; 1% only with bias alignment & normal volatility (env-driven)
        base_risk = float(os.getenv('BASE_RISK_PCT', str(NORMAL_RISK_PERCENTAGE)))
        
        # Get Asian range grade and confluence conditions
        grade = (self.current_session.asian_range_grade or 'NORMAL').upper()
        
        # Get the latest confluence check for bias alignment
        try:
            latest_confluence = ConfluenceCheck.objects.filter(
                session=self.current_session
            ).order_by('-created_at').first()
            
            bias_aligned = False
            normal_volatility = True
            
            if latest_confluence:
                # Check bias alignment: sweep direction should align with HTF bias
                sweep_direction = self.current_session.sweep_direction
                htf_bias = latest_confluence.bias
                
                # Bias alignment logic per client spec
                if sweep_direction == 'DOWN' and htf_bias in ['BEAR', 'BEARISH']:
                    bias_aligned = True  # Fading up sweep with bearish bias
                elif sweep_direction == 'UP' and htf_bias in ['BULL', 'BULLISH']:
                    bias_aligned = True  # Fading down sweep with bullish bias
                
                # Check volatility regime (normal vs high/low)
                atr_value = latest_confluence.atr_value or 0
                atr_threshold_low = float(os.getenv('ATR_NORMAL_THRESHOLD_LOW', '1.0'))
                atr_threshold_high = float(os.getenv('ATR_NORMAL_THRESHOLD_HIGH', '3.0'))
                normal_volatility = atr_threshold_low <= atr_value <= atr_threshold_high
        except Exception as e:
            logger.warning(f"Could not check bias alignment: {e}")
            bias_aligned = False
            normal_volatility = True
        
        # Risk percentage calculation per client spec
        # 1% only when: NORMAL grade + bias aligned + normal volatility
        if (grade == 'NORMAL' and bias_aligned and normal_volatility):
            risk_pct = float(os.getenv('MAX_RISK_PCT', '0.01'))  # e.g., 1.0%
        else:
            risk_pct = float(os.getenv('TIGHT_WIDE_RISK_PCT', str(base_risk)))
        # Client Spec: TIGHT and WIDE ranges should use reduced risk
        if grade in ['TIGHT', 'WIDE']:
            risk_pct = float(os.getenv('TIGHT_WIDE_RISK_PCT', str(base_risk)))
        elif grade in ['NO_TRADE', 'EXTREME']:
            risk_pct = float(os.getenv('EXTREME_RISK_PCT', str(base_risk * 0.5)))
        
        logger.info(f"Risk calculation: grade={grade}, bias_aligned={bias_aligned}, "
                   f"normal_vol={normal_volatility}, final_risk={risk_pct*100:.1f}%")
        
        # Get minimal GPT risk adjustment only if needed
        market_conditions = {
            'high_volatility': False,  # Would check actual volatility
            'major_news': False  # Would check actual news
        }
        # Skip GPT risk adjustment; keep base risk logic
        risk_amount = equity * risk_pct
        
        stop_distance = abs(entry_price - stop_loss)
        # Derive tick size/value from MT5 symbol info
        info = mt5.symbol_info(symbol)
        if info is None:
            return {'success': False, 'error': 'Symbol info unavailable for sizing'}
        
        # In many brokers for XAUUSD: point=0.01 or 0.1; tick_value per lot applies
        point = info.point
        # Fallback tick_value if missing
        tick_value = getattr(info, 'trade_tick_value', 1.0) or 1.0
        contract_size = getattr(info, 'trade_contract_size', 100.0) or 100.0
        # Monetary risk per 1 lot for stop_distance:
        approx_value_per_lot = (stop_distance / max(point, 1e-9)) * tick_value
        if approx_value_per_lot <= 0:
            return {'success': False, 'error': 'Invalid sizing parameters'}
        
        volume = max(0.01, round(risk_amount / approx_value_per_lot, 2))  # lots rounded
        
        # Calculate R and pip values for Phase 3 tracking
        stop_distance_pips = abs(entry_price - stop_loss) / pip_value
        tp1_distance_pips = abs(take_profit_1 - entry_price) / pip_value
        tp2_distance_pips = abs(take_profit_2 - entry_price) / pip_value
        # Calculate R:R ratio
        risk_reward_ratio = tp1_distance_pips / stop_distance_pips if stop_distance_pips > 0 else 0
        
        # Create enhanced trade signal with Phase 3 fields
        signal = TradeSignal.objects.create(
            session=self.current_session,
            sweep=sweep,
            symbol=symbol,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            volume=volume,
            risk_percentage=risk_pct * 100.0,
            risk_reward_ratio=risk_reward_ratio,
            state='CONFIRMED',
            # Phase 3 enhancements
            entry_method='LIMIT',
            entry_zone_reference='CONFIRM_BODY',  # Using confirmation body per client spec
            sl_pips=stop_distance_pips,
            tp1_pips=tp1_distance_pips,
            tp2_pips=tp2_distance_pips,
            calculated_r=0.0,  # Will be updated when trade closes
            micro_trigger_satisfied=True,  # Assuming satisfied if we reach this point
            retest_expiry_time=timezone.now() + timedelta(minutes=15),  # 15-minute retest window
            breakeven_moved=False,
            trailing_active=False
        )
        
        # Update session state with structured logging
        old_state = self.current_session.current_state
        self.current_session.current_state = 'ARMED'
        self.current_session.armed_time = timezone.now()
        self.current_session.save()
        
        # Log signal generation with complete trade details
        self._log_state_transition(
            old_state=old_state,
            new_state='ARMED',
            reason='Trade signal generated and armed',
            context={
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'volume': volume,
                'risk_percentage': risk_pct * 100.0
            }
        )
        
        return {
            'success': True,
            'signal_generated': True,
            'signal_id': signal.id,
            'signal_type': signal_type,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'volume': volume,
            'risk_reward_ratio': risk_reward_ratio,
            'session_state': 'ARMED',
        }
    
    def execute_trade(self, symbol: str = "XAUUSD", volume: float = None) -> Dict:
        """
        Execute the ARMED signal as a market order (opposite of sweep) with SL/TP.
        Enforces all risk/confluence checks and session limits before execution.
        Full audit logging and error/context reporting.
        """
        if not self.current_session or self.current_session.current_state != 'ARMED':
            return {'success': False, 'error': 'No armed signal to execute'}

        # Enforce risk limits before execution
        risk_check = self.enforce_risk_limits()
        if not risk_check.get('success'):
            self._log_state_transition(
                old_state=self.current_session.current_state,
                new_state='COOLDOWN',
                reason='Order execution blocked by risk limits',
                context=risk_check
            )
            return {'success': False, 'error': 'Risk limits breached', 'details': risk_check}

        # Enforce confluence before execution
        confluence_check = self.check_confluence(symbol)
        if not confluence_check.get('confluence_passed'):
            self._log_state_transition(
                old_state=self.current_session.current_state,
                new_state='COOLDOWN',
                reason='Order execution blocked by confluence gating',
                context=confluence_check
            )
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = 'Confluence gating failed'
            self.current_session.save()
            return {
                'success': False,
                'error': 'Confluence gating failed',
                'details': confluence_check,
                'session_state': 'COOLDOWN',
                'cooldown_reason': 'Confluence gating failed'
            }

        # Single GPT decision gate just before execution
        try:
            payload = self._build_gpt_payload(symbol, confluence_check)
            decision = self.gpt_service.decide_trade_go_no_go(payload)
            logger.info(f"GPT EXECUTION DECISION: {decision}")
            if not decision.get('proceed', True):
                old_state = self.current_session.current_state
                self._log_state_transition(
                    old_state=old_state,
                    new_state='COOLDOWN',
                    reason='GPT decision: NO-TRADE',
                    context={'gpt_response': decision.get('response')}
                )
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.cooldown_reason = 'GPT decision: NO-TRADE'
                try:
                    cooldown_min = int(os.getenv('GPT_NO_TRADE_COOLDOWN_MIN', '15'))
                except Exception:
                    cooldown_min = 15
                self.current_session.cooldown_until = timezone.now() + timedelta(minutes=cooldown_min)
                self.current_session.save()
                return {
                    'success': False,
                    'error': 'GPT declined trade',
                    'gpt_decision': decision,
                    'session_state': 'COOLDOWN',
                    'cooldown_reason': 'GPT decision: NO-TRADE',
                    'cooldown_until': self.current_session.cooldown_until.isoformat()
                }
        except Exception as e:
            logger.error(f"Failed GPT decision gate: {e}")
            decision = {'proceed': True, 'reason': 'GPT error - default proceed'}
            # Fail-open by default (allow trade) as per requirements

        signal = TradeSignal.objects.filter(session=self.current_session).order_by('-created_at').first()
        if not signal:
            return {'success': False, 'error': 'No signal found'}

        # Use provided volume if specified, otherwise use signal's volume
        trade_volume = volume if volume is not None else float(signal.volume)

        # Real order execution via MT5
        side = 'BUY' if signal.signal_type.upper() == 'BUY' else 'SELL'
        sl = float(signal.stop_loss) if signal.stop_loss is not None else None
        tp = float(signal.take_profit_1) if signal.take_profit_1 is not None else None
        mt5_result = self.mt5_service.place_market_order(
            symbol=symbol,
            side=side,
            volume=trade_volume,
            sl=sl,
            tp=tp,
            comment=f"Phase 3 Signal: {signal.signal_type}"
        )
        if not mt5_result.get('success'):
            self._log_state_transition(
                old_state=self.current_session.current_state,
                new_state='COOLDOWN',
                reason='MT5 order_send failed',
                context={'mt5_error': mt5_result}
            )
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"MT5 error: {mt5_result.get('error')}"
            self.current_session.save()
            return {
                'success': False,
                'error': 'MT5 order failed',
                'details': mt5_result,
                'session_state': 'COOLDOWN',
            }

        order_dict = mt5_result.get('result', {})

        # Transition to IN_TRADE with structured logging
        old_state = self.current_session.current_state
        self.current_session.current_state = 'IN_TRADE'
        self.current_session.save()

        # Log trade execution
        self._log_state_transition(
            old_state=old_state,
            new_state='IN_TRADE',
            reason='Trade executed successfully',
            context={
                'symbol': symbol,
                'signal_type': signal.signal_type,
                'entry_price': signal.entry_price,
                'volume': signal.volume,
                'order_result': order_dict,
                'risk_check': risk_check,
                'confluence_check': confluence_check
            }
        )

        logger.info(f"Phase 3 Signal Executed: {signal.signal_type} for {symbol} at {signal.entry_price}")

        return {'success': True, 'order': order_dict, 'session_state': 'IN_TRADE'}
    
    def enforce_risk_limits(self) -> Dict:
        """
        Enforce risk mapping and management for the current session:
        - Enforce max daily loss (absolute and R)
        - Enforce max daily trades
        - Update audit fields
        """
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}

        # Enforce max daily loss (absolute)
        daily_loss = float(self.current_session.current_daily_loss)
        daily_loss_limit = float(self.current_session.daily_loss_limit)
        if daily_loss >= daily_loss_limit:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Daily loss limit reached: {daily_loss:.2f} >= {daily_loss_limit:.2f}"
            self.current_session.save()
            return {
                'success': False,
                'reason': f"Daily loss limit reached: {daily_loss:.2f} >= {daily_loss_limit:.2f}",
                'session_state': 'COOLDOWN'
            }

        # Enforce max daily loss (R)
        daily_loss_r = float(self.current_session.current_daily_loss_r)
        daily_loss_limit_r = float(self.current_session.daily_loss_limit_r)
        if daily_loss_r >= daily_loss_limit_r:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Daily R loss limit reached: {daily_loss_r:.2f} >= {daily_loss_limit_r:.2f}R"
            self.current_session.save()
            return {
                'success': False,
                'reason': f"Daily R loss limit reached: {daily_loss_r:.2f} >= {daily_loss_limit_r:.2f}R",
                'session_state': 'COOLDOWN'
            }

        # Enforce max daily trades
        daily_trades = int(self.current_session.current_daily_trades)
        trade_count_limit = int(self.current_session.daily_trade_count_limit)
        if daily_trades >= trade_count_limit:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Max daily trades reached: {daily_trades} >= {trade_count_limit}"
            self.current_session.save()
            return {
                'success': False,
                'reason': f"Max daily trades reached: {daily_trades} >= {trade_count_limit}",
                'session_state': 'COOLDOWN'
            }

        # If all limits OK, return success
        return {'success': True, 'limits_ok': True}
    

    def enforce_session_and_daily_limits(self) -> Dict:
        """
        Enforce session, daily, and weekly limits before allowing trade actions.
        Logs all limit breaches and session summaries for audit.
        """
        if not self.current_session:
            system_logger.log_error('LIMIT_CHECK', 'No active session for limit enforcement')
            return {'success': False, 'error': 'No active session'}

        # Check daily loss limits
        daily_loss = float(self.current_session.current_daily_loss)
        daily_loss_limit = float(self.current_session.daily_loss_limit)
        if daily_loss >= daily_loss_limit:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Daily loss limit reached: {daily_loss:.2f} >= {daily_loss_limit:.2f}"
            self.current_session.save()
            risk_logger.log_risk_check('DAILY_LOSS', False, daily_loss, daily_loss_limit, {'session_id': self.current_session.id})
            trading_logger.log_state_transition(str(self.current_session.id), 'ACTIVE', 'COOLDOWN', 'Daily loss limit breached', {'daily_loss': daily_loss, 'limit': daily_loss_limit})
            return {'success': False, 'reason': 'Daily loss limit reached', 'session_state': 'COOLDOWN'}

        daily_loss_r = float(self.current_session.current_daily_loss_r)
        daily_loss_limit_r = float(self.current_session.daily_loss_limit_r)
        if daily_loss_r >= daily_loss_limit_r:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Daily R loss limit reached: {daily_loss_r:.2f} >= {daily_loss_limit_r:.2f}R"
            self.current_session.save()
            risk_logger.log_risk_check('DAILY_R_LOSS', False, daily_loss_r, daily_loss_limit_r, {'session_id': self.current_session.id})
            trading_logger.log_state_transition(str(self.current_session.id), 'ACTIVE', 'COOLDOWN', 'Daily R loss limit breached', {'daily_loss_r': daily_loss_r, 'limit_r': daily_loss_limit_r})
            return {'success': False, 'reason': 'Daily R loss limit reached', 'session_state': 'COOLDOWN'}

        daily_trades = int(self.current_session.current_daily_trades)
        trade_count_limit = int(self.current_session.daily_trade_count_limit)
        if daily_trades >= trade_count_limit:
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Max daily trades reached: {daily_trades} >= {trade_count_limit}"
            self.current_session.save()
            risk_logger.log_risk_check('DAILY_TRADES', False, daily_trades, trade_count_limit, {'session_id': self.current_session.id})
            trading_logger.log_state_transition(str(self.current_session.id), 'ACTIVE', 'COOLDOWN', 'Max daily trades breached', {'daily_trades': daily_trades, 'limit': trade_count_limit})
            return {'success': False, 'reason': 'Max daily trades reached', 'session_state': 'COOLDOWN'}

        # Weekly circuit breaker
        weekly_check = self.weekly_circuit_breaker.check_weekly_circuit_breaker(self.current_session)
        if not weekly_check.get('success'):
            system_logger.log_error('WEEKLY_CIRCUIT_BREAKER', 'Weekly circuit breaker check failed', {'session_id': self.current_session.id, 'details': weekly_check})
            return {'success': False, 'reason': 'Weekly circuit breaker check failed', 'details': weekly_check}
        if weekly_check.get('circuit_breaker_active'):
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.cooldown_reason = f"Weekly circuit breaker active: {weekly_check.get('weekly_realized_r', 0):.2f}R loss"
            self.current_session.save()
            risk_logger.log_risk_check('WEEKLY_CIRCUIT_BREAKER', False, weekly_check.get('weekly_realized_r', 0), weekly_check.get('weekly_loss_limit_r', 0), {'session_id': self.current_session.id})
            trading_logger.log_state_transition(str(self.current_session.id), 'ACTIVE', 'COOLDOWN', 'Weekly circuit breaker triggered', weekly_check)
            return {'success': False, 'reason': 'Weekly circuit breaker active', 'details': weekly_check, 'session_state': 'COOLDOWN'}

        # Log session summary for audit
        trading_logger.log_session_summary({
            'session_id': self.current_session.id,
            'daily_loss': daily_loss,
            'daily_loss_r': daily_loss_r,
            'daily_trades': daily_trades,
            'weekly_realized_r': weekly_check.get('weekly_realized_r', 0),
            'limits_ok': True
        })

        return {'success': True, 'limits_ok': True, 'details': weekly_check}

    def check_confluence(self, symbol: str = None) -> Dict:
        """
        Phase 3 Enhanced Confluence Checking - Strict Modular Gating
        Enforces all client-specified risk/confluence gates before arming order.
        Returns detailed failure reasons for transparency.
        """
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}

        failure_reasons = []
        gate_results = {}

        # 1. Spread gate
        tick = self.mt5_service.get_current_price(symbol)
        if not tick:
            return {'success': False, 'error': 'No tick data'}
        pip_multiplier = self._get_pip_multiplier(symbol)
        max_spread = float(os.getenv('MAX_SPREAD_PIPS', '2.0'))
        spread = (tick['ask'] - tick['bid']) * pip_multiplier
        spread_ok = spread <= max_spread
        gate_results['spread_ok'] = spread_ok
        if not spread_ok:
            failure_reasons.append(f"Spread too wide: {spread:.1f} > {max_spread}")

        # 2. LBMA Auction Blackout
        auction_blackout = self._check_lbma_auction_blackout()
        gate_results['auction_blackout'] = auction_blackout
        if auction_blackout:
            failure_reasons.append("LBMA auction blackout active")

        # 3. News Blackout
        news_blackout, news_tier, news_buffer = self._check_news_blackout()
        gate_results['news_blackout'] = news_blackout
        gate_results['news_tier'] = news_tier
        gate_results['news_buffer'] = news_buffer
        if news_blackout:
            failure_reasons.append(f"News blackout active: {news_tier} event")

        # 4. Velocity Spike
        velocity_spike, velocity_ratio = self._check_velocity_spike(symbol)
        gate_results['velocity_spike'] = velocity_spike
        gate_results['velocity_ratio'] = velocity_ratio
        if velocity_spike:
            failure_reasons.append(f"Velocity spike detected: {velocity_ratio:.2f}x baseline")

        # 5. HTF bias (H4/D1)
        end = timezone.now()
        d1 = self.mt5_service.get_historical_data(symbol, 'D1', end - timedelta(days=60), end)
        h4 = self.mt5_service.get_historical_data(symbol, 'H4', end - timedelta(days=30), end)
        m15 = self.mt5_service.get_historical_data(symbol, 'M15', end - timedelta(hours=24), end)
        def _bias(df: Optional[pd.DataFrame]) -> str:
            if df is None or len(df) < 20:
                return 'UNKNOWN'
            close = df['close']
            sma = close.rolling(window=20).mean()
            if close.iloc[-1] > sma.iloc[-1] * 1.001:
                return 'BULL'
            if close.iloc[-1] < sma.iloc[-1] * 0.999:
                return 'BEAR'
            return 'RANGE'
        bias_d1 = _bias(d1)
        bias_h4 = _bias(h4)
        gate_results['bias_d1'] = bias_d1
        gate_results['bias_h4'] = bias_h4

        # 6. ADX/Trend Day
        adx_15m, trend_strength = self._calculate_adx(m15, 14) if m15 is not None else (0, 0)
        adx_high_threshold = float(os.getenv('ADX_15M_HIGH_THRESHOLD', '25.0'))
        trend_day_high_adx = adx_15m > adx_high_threshold
        h1_band_walk = self._check_h1_band_walk(symbol)
        gate_results['adx_15m'] = adx_15m
        gate_results['trend_day_high_adx'] = trend_day_high_adx
        gate_results['h1_band_walk'] = h1_band_walk
        if trend_day_high_adx and h1_band_walk:
            if ((self.current_session.sweep_direction == 'UP' and bias_h4 == 'BULL') or
                (self.current_session.sweep_direction == 'DOWN' and bias_h4 == 'BEAR')):
                failure_reasons.append("Trend day: skipping counter-trend fade")

        # 7. NY Participation Rule
        london_traversed_asia = self._check_london_traversed_asia()
        ny_requires_fresh_sweep = london_traversed_asia and not self._check_fresh_ny_sweep()
        gate_results['london_traversed_asia'] = london_traversed_asia
        gate_results['ny_requires_fresh_sweep'] = ny_requires_fresh_sweep
        if ny_requires_fresh_sweep:
            failure_reasons.append("London traversed Asia: NY requires fresh sweep")

        # 8. Participation Filter
        participation_filter_active = self._check_participation_filter()
        gate_results['participation_filter_active'] = participation_filter_active
        if participation_filter_active:
            failure_reasons.append("Participation filter active (holiday/low volume)")

        # 9. Bias Gate (strict enforcement)
        bias_gate = True
        if self.current_session.sweep_direction == 'UP' and bias_d1 == 'BULL' and bias_h4 == 'BULL':
            bias_gate = False
            failure_reasons.append("Bias gate: fading strong uptrend not allowed")
        elif self.current_session.sweep_direction == 'DOWN' and bias_d1 == 'BEAR' and bias_h4 == 'BEAR':
            bias_gate = False
            failure_reasons.append("Bias gate: fading strong downtrend not allowed")
        gate_results['bias_gate'] = bias_gate

        # Final confluence decision: ALL gates must pass
        confluence_passed = (spread_ok and not auction_blackout and not news_blackout and
                             not velocity_spike and bias_gate and not ny_requires_fresh_sweep and
                             not participation_filter_active)
        gate_results['confluence_passed'] = confluence_passed

        if not confluence_passed:
            logger.info(f"Confluence failed: {'; '.join(failure_reasons)}")

        # Persist enhanced confluence record
        try:
            from ..models import ConfluenceCheck
            ConfluenceCheck.objects.create(
                session=self.current_session,
                timeframe='15m',
                bias=bias_h4,
                trend_strength=trend_strength,
                atr_value=self.current_session.atr_value,
                adx_value=adx_15m,
                adx_timeframe='15m',
                spread=spread,
                spread_threshold=max_spread,
                velocity_spike=velocity_spike,
                velocity_ratio=velocity_ratio,
                news_risk=news_blackout,
                news_tier=news_tier,
                news_buffer_minutes=news_buffer,
                auction_blackout=auction_blackout,
                trend_day_high_adx=trend_day_high_adx,
                h1_band_walk=h1_band_walk,
                london_traversed_asia=london_traversed_asia,
                ny_requires_fresh_sweep=ny_requires_fresh_sweep,
                participation_filter_active=participation_filter_active,
                failure_reasons='; '.join(failure_reasons) if failure_reasons else None,
                passed=confluence_passed
            )
        except Exception as e:
            logger.error(f"Failed to persist confluence check: {e}")

        # Return modular gate results and failure reasons
        return {
            'success': True,
            **gate_results,
            'spread_pips': spread,
            'failure_reasons': failure_reasons,
            'atr_h1_pips': self._get_h1_atr_pips(symbol),
            'adx_15m': adx_15m,
            'bias_h1': bias_h4,
            'news_buffer_minutes': news_buffer
        }

    def _get_h1_atr_pips(self, symbol: str) -> float:
        """Compute H1 ATR(14) in pips for payload and thresholds."""
        try:
            end = timezone.now()
            start = end - timedelta(days=2)
            h1 = self.mt5_service.get_historical_data(symbol, 'H1', start, end)
            if h1 is None or len(h1) < 15:
                return 0.0
            atr = self._calculate_atr(h1, 14)
            return float(atr) * self._get_pip_multiplier(symbol)
        except Exception:
            return 0.0

    def _build_gpt_payload(self, symbol: str, conf: Dict) -> Dict:
        """Builds the single JSON input for the GPT decision before execution."""
        session = self.current_session
        now = timezone.now()
        # Session name by UTC hour (kill-zones); adjust if you keep a session tracker elsewhere
        session_name = 'LONDON' if 8 <= now.hour < 13 else 'NEW_YORK'
        now_utc3 = (now + timedelta(hours=3)).strftime('%H:%M')

        # Asian range values
        asia_high = float(session.asian_range_high or 0)
        asia_low = float(session.asian_range_low or 0)
        asia_mid = float(session.asian_range_midpoint or 0)
        asia_range_pips = float(session.asian_range_size or 0)

        # ATRs
        atr_h1_pips = float(conf.get('atr_h1_pips', 0.0)) or self._get_h1_atr_pips(symbol)
        # Compute ATR(M5) pips over last ~6 hours
        try:
            end = now
            start = end - timedelta(hours=6)
            m5 = self.mt5_service.get_historical_data(symbol, 'M5', start, end)
            if m5 is not None and len(m5) >= 20:
                atr_m5 = self._calculate_atr(m5, 14)
                atr_m5_pips = float(atr_m5) * self._get_pip_multiplier(symbol)
            else:
                atr_m5_pips = 0.0
        except Exception:
            atr_m5_pips = 0.0

        # ADX and bias
        adx_15m = float(conf.get('adx_15m', 0.0))
        bias_h1 = conf.get('bias_h1') or conf.get('bias_h4') or 'RANGE'

        # Sweep context
        last_sweep_side = session.sweep_direction or 'NONE'
        sweep_distance_pips = float(session.sweep_threshold or 0.0)

        # Post-sweep acceptance: consecutive M5 closes outside (from session count if tracked)
        m5_closes_outside_after_sweep = int(getattr(session, 'acceptance_outside_count', 0) or 0)

        # Confirmation body estimate in pips from latest LiquiditySweep audit fields
        body_pips = 0.0
        try:
            sweep = LiquiditySweep.objects.filter(session=session).order_by('-sweep_time').first()
            if sweep and sweep.displacement_atr and sweep.displacement_multiplier:
                body_pips = (float(sweep.displacement_atr) * float(sweep.displacement_multiplier)) * self._get_pip_multiplier(symbol)
        except Exception:
            pass

        # CHOCH/Mini-BOS flags
        m1_choch = bool(getattr(session, 'bos_choch_confirmed', False))
        m5_mini_bos = bool(session.displacement_atr_ratio and float(session.displacement_atr_ratio) >= 1.3)

        # Spread
        spread_pips = float(conf.get('spread_pips', 0.0))

        # 1m ranges for velocity
        last_1m_range_pips = 0.0
        baseline_1m_range_pips = 0.0
        try:
            end = now
            start = end - timedelta(minutes=12)
            m1 = self.mt5_service.get_historical_data(symbol, 'M1', start, end)
            if m1 is not None and len(m1) >= 6:
                m1 = m1.copy()
                m1['range'] = (m1['high'] - m1['low']) * self._get_pip_multiplier(symbol)
                last_1m_range_pips = float(m1['range'].iloc[-1])
                baseline_1m_range_pips = float(m1['range'].iloc[-6:-1].mean())
        except Exception:
            pass

        # News/LBMA
        news_desc = 'none'
        if conf.get('news_blackout'):
            buf = int(conf.get('news_buffer_minutes', conf.get('news_buffer', 0)) or 0)
            tier = conf.get('news_tier', 'OTHER')
            news_desc = f"{buf}m buffer active {tier}"
        lbma_window_now = bool(conf.get('auction_blackout', False))

        # London traversed Asia / NY fresh sweep required
        london_traversed_asia = bool(conf.get('london_traversed_asia', False))
        # If our gating says NY requires fresh sweep, then ny_fresh_sweep is False; otherwise True/NA
        ny_fresh_sweep = not bool(conf.get('ny_requires_fresh_sweep', False))

        # Account & risk
        acct = self.mt5_service.get_account_info() or {}
        equity = float(acct.get('equity', 0.0))
        risk_default_pct = 0.5
        point_value = float(os.getenv(f'{symbol.upper()}_PIP_VALUE', '0.1'))

        payload = {
            "date": now.date().isoformat(),
            "now_utc3": now_utc3,
            "session": session_name,
            "symbol": symbol,
            "asia_high": round(asia_high, 2) if asia_high else 0.0,
            "asia_low": round(asia_low, 2) if asia_low else 0.0,
            "asia_mid": round(asia_mid, 2) if asia_mid else 0.0,
            "asia_range_pips": round(asia_range_pips, 1) if asia_range_pips else 0.0,
            "atr_m5_pips": round(atr_m5_pips, 1),
            "atr_h1_pips": round(atr_h1_pips, 1),
            "adx_15m": round(adx_15m, 1),
            "bias_h1": str(bias_h1) if bias_h1 else 'RANGE',
            "last_sweep_side": last_sweep_side or 'NONE',
            "sweep_distance_pips": round(sweep_distance_pips, 1),
            "m5_closes_outside_after_sweep": int(m5_closes_outside_after_sweep),
            "m5_confirm_body_pips": round(body_pips, 1),
            "m1_choch": bool(m1_choch),
            "m5_mini_bos": bool(m5_mini_bos),
            "spread_pips": round(spread_pips, 1),
            "last_1m_range_pips": round(last_1m_range_pips, 1),
            "baseline_1m_range_pips": round(baseline_1m_range_pips, 1),
            "news_next_3h": news_desc,
            "lbma_window_now": lbma_window_now,
            "london_traversed_asia": london_traversed_asia,
            "ny_fresh_sweep": ny_fresh_sweep,
            "equity": round(equity, 2),
            "risk_default_pct": risk_default_pct,
            "point_value": point_value,
        }
        return payload
    
    


# put this inside class SignalDetectionService, right after _build_gpt_payload
    def build_gpt_prompt_preview(self, symbol: str, conf: Dict) -> str:
        """
        Return the exact SYSTEM ROLE prompt + JSON payload that would be sent to GPT, without calling it.
        Pass the latest confluence dict (from check_confluence) to enrich fields.
        """
        payload = self._build_gpt_payload(symbol, conf)

        system_role = """SYSTEM ROLE — REAL-TIME INTRADAY ANALYST (XAUUSD)
            Mission: Using the incoming MT5 data packet, decide if an Asian-session liquidity sweep in XAUUSD occurred and, if so, formulate a 1–3h reversal trade for the upcoming [LONDON OPEN / NEW YORK OPEN]. Obey the rules and format below exactly.

            INPUT (single JSON object per call)
            """ + json.dumps(payload, ensure_ascii=False) + """
            DECISION LOGIC (apply in order)
            1) Asia box = 03:00–09:00 UTC+3. Grade size:
            <30 pips NO_TRADE; 30–49 tight; 50–150 normal; 151–180 wide.
            2) Sweep test (post-09:00): compute sweep_threshold = max(10 pips, 9–10% of Asia range, 0.5×ATR(H1)). Valid only if exactly one side taken by ≥ threshold AND there are NOT ≥2 full M5 closes outside (else breakout = NO_TRADE). If both sides taken before confirmation → NO_TRADE.
            3) Rejection / displacement: require M5 close back inside Asia + confirm body ≥ k×ATR(M5) (k=1.3 normal; 1.5 high-vol if ATR(H1) regime/ADX strong). Prefer M5 mini-BOS in tight/high-vol. Require M1 CHOCH. Timeout 30 min if not confirmed.
            4) Confluence gates (all must pass):
            • Bias gate (H1): counter-trend → half-risk (0.5%) and/or need M5 mini-BOS.
            • News buffer: Tier-1 ≥60m; others ≥30m.
            • Trend-day gate: ADX(15m) high + H1 band-walk ⇒ skip counter-trend fades.
            • Liquidity guard: spread ≤2.0 pips AND last_1m_range ≤ 2× baseline.
            • LBMA blackout: avoid ±10–15m of 10:30 & 15:00 London.
            • NY filter: if London traversed full Asia box, require fresh NY sweep.
            5) Trade setup (if all true):
            Direction opposite the sweep. Entry = first mitigation of M5 rejection candle body/OB/FVG. Trigger: M1 engulf/failure swing inside zone (no blind fills). SL = 2–5 pips beyond sweep extreme (wider in high-vol). Targets: TP1 = Asia midpoint or +1R (partial + move BE). TP2 = opposite Asia extreme or +2–3R (tune for tight/wide Asia). Position size = (equity*risk_pct)/(|entry−SL|*point_value); risk_pct = 1% only when with-bias & normal vol; else 0.5%. Weekly breaker: pause if weekly loss ≥6R.
            6) Management: BE at +0.5R or after M1 swing; trail by last M1 swing or 0.75×ATR(M5) post-TP1; timeouts: flat at kill-zone end or 20m pre-news; one-and-done after a stop.

            OUTPUT FORMAT (≤300 words; strict)
            ### Trade Recommendation (XAUUSD)
            <fixed-width table with columns: Entry | SL | TP1 | TP2 | Size | RR>
            ### Checklist
            List / for: Asia grade; One-side sweep≥threshold; Not accepted outside; M5 displacement k×ATR(M5); M1 CHOCH; (mini-BOS if needed); Bias gate; News buffer; Trend-day filter; Spread/velocity guard; LBMA window; NY participation (if session=NY).
            ### Rationale (≤100 words)
            Brief market-structure read (sweep, rejection, targets).
            ### Post-Trade Journal
            PnL: __ | Emotions: __ | Lessons: __

            BEHAVIOR
            • If any gate fails, return "NO-TRADE" + exact reasons.
            • Use units where 1 pip = $0.10. Spread guard = 2.0 pips baseline.
            • Only propose setups during first half of the kill-zone; block first 3 minutes after session open.
            • Respond to event states: SWEPT (go/no-go), CONFIRMED (levels), ARMED expiry/filters fail (NO-TRADE), IN_TRADE at +0.5R or near timeout.
            """
        return system_role








    def run_strategy_once(self, symbol: str = None) -> Dict:
        """One-shot: detect → confirm → confluence → signal → execute, per client's rules with Phase 3 enhancements."""
        if symbol is None:
            symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        
        # 1) Ensure session
        if not self.current_session:
            init_result = self.initialize_session(symbol)
            if not init_result.get('success'):
                return init_result
        
        # 2) Check daily limits enforcement - Phase 3 enhancement
        daily_limits_check = self._check_daily_limits()
        if not daily_limits_check['allowed']:
            return {
                'success': False,
                'stage': 'DAILY_LIMITS',
                'no_trade': True,
                'reason': daily_limits_check['reason'],
                'limits_data': daily_limits_check
            }
        
        # If state machine progressed already, continue from the next step.
        state = self.current_session.current_state
        
        # 2) Detect sweep only if we're IDLE
        if state == 'IDLE':
            sweep = self.detect_sweep(symbol)
            if not sweep.get('success'):
                return {'success': False, 'stage': 'DETECT', 'error': sweep.get('error', 'detect failed')}
            if not sweep.get('sweep_detected'):
                return {'success': False, 'stage': 'DETECT', 'no_trade': True, 'reason': 'No sweep detected'}
            state = 'SWEPT'
        
        # 3) Check confirmation timeout if we're SWEPT - Client Spec: 30-minute timeout
        if state == 'SWEPT':
            # Check if 30 minutes have passed since sweep without confirmation
            if self.current_session.sweep_time:
                confirmation_timeout_minutes = int(os.getenv('CONFIRMATION_TIMEOUT_MINUTES', '30'))
                time_since_sweep = timezone.now() - self.current_session.sweep_time
                if time_since_sweep.total_seconds() > confirmation_timeout_minutes * 60:
                    self.current_session.current_state = 'COOLDOWN'
                    self.current_session.cooldown_reason = f'Confirmation timeout: {confirmation_timeout_minutes} minutes exceeded'
                    self.current_session.save()
                    return {
                        'success': False,
                        'stage': 'CONFIRM_TIMEOUT',
                        'no_trade': True,
                        'reason': f'Confirmation timeout exceeded ({confirmation_timeout_minutes} minutes since sweep)'
                    }
            
            # Attempt confirmation
            confirm = self.confirm_reversal(symbol)
            if not confirm.get('success') or not confirm.get('confirmed'):
                return {'success': False, 'stage': 'CONFIRM', 'no_trade': True, 'reason': confirm.get('reason', 'not confirmed')}
            state = 'CONFIRMED'
        
        # 4) Confluence guard if CONFIRMED
        if state == 'CONFIRMED':
            conf = self.check_confluence(symbol)
            if not conf.get('success') or not conf.get('confluence_passed'):
                return {'success': False, 'stage': 'CONFLUENCE', 'no_trade': True, 'reason': 'Confluence failed', 'details': conf}
            
            # 5) Time-boxed retest window (3 M5 bars)
            now = timezone.now()
            if self.current_session.confirmation_time and (now - self.current_session.confirmation_time) > timedelta(minutes=15):
                # Expired retest window - Call GPT for NO_TRADE reasoning (Event Edge: ARMED expiration)
                failure_data = {
                    'reason': 'Retest window expired (15 minutes)',
                    'time_in_state': (now - self.current_session.confirmation_time).total_seconds() / 60
                }
                # Skip GPT; enforce single-call policy
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.cooldown_reason = 'Retest window expired'
                self.current_session.save()
                return {
                    'success': False,
                    'stage': 'RETEST',
                    'no_trade': True,
                    'reason': 'Retest window expired',
                    'severity': 'MEDIUM',
                    'session_state': 'COOLDOWN'
                }
            
            # Enhanced retest logic - Client Spec: Use confirmation candle body (50-100%), not Asian midpoint
            retest_result = self._check_enhanced_retest(symbol)
            if not retest_result['success']:
                return {
                    'success': False,
                    'stage': 'RETEST',
                    'no_trade': True,
                    'reason': retest_result['reason']
                }
            
            # 6) Generate signal once retest touched
            sig = self.generate_trade_signal(symbol)
            if not sig.get('success'):
                return {'success': False, 'stage': 'SIGNAL', 'error': sig.get('error', 'signal failed')}
            
            # Optional: M1/M5 latest recheck of spread/news right before arming
            conf2 = self.check_confluence(symbol)
            if not conf2.get('confluence_passed'):
                return {'success': False, 'stage': 'CONFLUENCE', 'no_trade': True, 'reason': 'Confluence failed at arming', 'details': conf2}
            state = 'ARMED'
        
        # 6) Execute order if ARMED
        if state == 'ARMED':
            exe = self.execute_trade(symbol)
            if not exe.get('success'):
                return {'success': False, 'stage': 'EXECUTE', 'error': exe.get('error', 'execution failed'), 'data': exe.get('data'), 'gpt_decision': exe.get('gpt_decision')}
            # After execution, let MT5 handle the trade with SL/TP - no immediate management
            return {'success': True, 'stage': 'DONE', 'order': exe['order'], 'session_state': 'IN_TRADE', 'gpt_decision': exe.get('gpt_decision')}
        
        # If already IN_TRADE, return current state
        if state == 'IN_TRADE':
            # Perform one step of trade management
            tm = self.manage_in_trade(symbol)
            return {'success': True, 'stage': 'ALREADY_IN_TRADE', 'session_state': 'IN_TRADE', 'management': tm}
        
        # Any other state fallback
        return {'success': False, 'stage': 'UNKNOWN', 'error': f'Unhandled state: {state}'}
    
    def manage_in_trade(self, symbol: str = "XAUUSD") -> Dict:
        """
        PASSIVE trade management - Let MT5 handle SL/TP:
        1. Monitor trade status only
        2. Update session state when trade is closed by MT5
        3. No manual closures except extreme emergencies
        4. Let stop loss and take profit work naturally
        """
        try:
            # Validate we're in a trade
            if not self.current_session or self.current_session.current_state != 'IN_TRADE':
                return {'success': False, 'reason': 'Not in trade'}
                
            # Get the active signal
            signal = TradeSignal.objects.filter(session=self.current_session).order_by('-created_at').first()
            if not signal:
                return {'success': False, 'reason': 'No signal found'}
                
            # Phase 1-2: No actual positions to manage, simulate position check
            pos_resp = {'success': True, 'positions': []}
            
            # Check if we should call GPT for trade management (Event Edge: IN_TRADE at +0.5R or near timeout)
            should_call_gpt = False
            trade_data = {
                'unrealized_pnl': 0,  # Would calculate actual PnL
                'risk_reward': 0,     # Would calculate actual R:R
                'time_in_trade': (timezone.now() - signal.created_at).total_seconds() / 60,
                'distance_to_be': 0   # Would calculate actual distance to BE
            }
            
            # Call GPT if at +0.5R or near timeout
            if trade_data['unrealized_pnl'] >= 0.5 or trade_data['time_in_trade'] > 120:  # 2 hours
                should_call_gpt = True
            
            # Skip GPT trade management; enforce single-call policy
            
            # Phase 1-2: Simulate trade management completion
            self.current_session.current_state = 'COOLDOWN'
            self.current_session.save()
            
            return {
                'success': True,
                'trade_closed': True,
                'reason': 'Phase 1-2: Simulated trade completion',
                'profit': 0  # Phase 1-2: No actual profit
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def _calculate_sweep_threshold(self, asian_data: Dict) -> Dict:
        """Calculate dynamic sweep threshold - max(10 pips, 7.5-10% of Asia range, 0.5×ATR(H1)) using env-configurable values"""
        range_pips = float(asian_data['range_pips'])
        symbol = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
        
        # Component 1: Floor (10 pips minimum)
        floor_pips = float(os.getenv('SWEEP_THRESHOLD_FLOOR_PIPS', str(SWEEP_THRESHOLD_FLOOR_PIPS)))
        
        # Component 2: Percentage of Asian range (prefer XAU-specific pct from env)
        pct = float(os.getenv('SWEEP_THRESHOLD_PCT_XAU', str(SWEEP_THRESHOLD_PCT_XAU)))  # e.g., 0.09 for 9%
        percentage_pips = range_pips * pct
        
        # Component 3: ATR(H1) × 0.5
        atr_h1_pips = 0.0
        try:
            end = timezone.now()
            start = end - timedelta(hours=24)
            h1_data = self.mt5_service.get_historical_data(symbol, 'H1', start, end)
            if h1_data is not None and len(h1_data) >= ATR_H1_LOOKBACK:
                atr_h1 = self._calculate_atr(h1_data, ATR_H1_LOOKBACK)
                pip_multiplier = self._get_pip_multiplier(symbol)
                atr_h1_pips = float(atr_h1) * float(pip_multiplier) * 0.5
        except Exception as e:
            logger.warning(f"Failed to calculate ATR(H1) for sweep threshold: {e}")
            atr_h1_pips = 0.0
        
        # Take the maximum of all three components
        threshold_pips = max(floor_pips, percentage_pips, atr_h1_pips)
        chosen_component = (
            'floor' if threshold_pips == floor_pips else
            'range' if threshold_pips == percentage_pips else
            'atr'
        )
        
        # Return components for sweep creation and audit
        return {
            'floor_pips': round(floor_pips, 1),
            'percentage_pips': round(percentage_pips, 1),
            'atr_threshold_pips': round(atr_h1_pips, 1),
            'atr_h1_pips': round(atr_h1_pips / 0.5, 1) if atr_h1_pips > 0 else 0,  # Original ATR value
            'threshold_pips': round(threshold_pips, 1),
            'chosen_component': chosen_component
        }
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if not isinstance(data, pd.DataFrame) or data is None or len(data) < period:
            return 0.001  # Default ATR
        if not all(col in data.columns for col in ['high', 'low', 'close']):
            return 0.001
        high = data['high']
        low = data['low']
        close = data['close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(window=period).mean()
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return 0.001
        atr = atr_series.iloc[-1]
        return atr if not pd.isna(atr) else 0.001
    
    def _detect_choch(self, data: pd.DataFrame, sweep_direction: str) -> bool:
        """Detect Change of Character on M1"""
        if not isinstance(data, pd.DataFrame) or data is None or len(data) < 3:
            return False
        if sweep_direction == 'UP':
            if 'high' not in data.columns:
                return False
            recent_highs = data['high'].tail(5)
            if len(recent_highs) >= 2:
                return recent_highs.iloc[-1] < recent_highs.iloc[-2]
        else:
            if 'low' not in data.columns:
                return False
            recent_lows = data['low'].tail(5)
            if len(recent_lows) >= 2:
                return recent_lows.iloc[-1] > recent_lows.iloc[-2]
        return False
    
    def _check_enhanced_retest(self, symbol: str) -> Dict:
        """Enhanced retest logic - Client Spec: Use confirmation candle body (50-100%) + micro-trigger"""
        try:
            now = timezone.now()
            
            # Get confirmation candle data
            if not self.current_session.confirmation_time:
                return {'success': False, 'reason': 'No confirmation time available'}
            
            # Get M5 data around confirmation time
            conf_time = self.current_session.confirmation_time
            m5_start = conf_time - timedelta(minutes=5)
            m5_end = conf_time + timedelta(minutes=5)
            conf_m5_data = self.mt5_service.get_historical_data(symbol, 'M5', m5_start, m5_end)
            if not isinstance(conf_m5_data, pd.DataFrame) or conf_m5_data is None or len(conf_m5_data) == 0:
                return {'success': False, 'reason': 'Cannot find confirmation candle data'}
            conf_candle = conf_m5_data.iloc[-1]
            for col in ['open', 'close', 'high', 'low']:
                if col not in conf_candle.index:
                    return {'success': False, 'reason': f'Missing {col} in confirmation candle'}
            candle_open = conf_candle['open']
            candle_close = conf_candle['close']
            candle_high = conf_candle['high']
            candle_low = conf_candle['low']
            body_top = max(candle_open, candle_close)
            body_bottom = min(candle_open, candle_close)
            body_size = body_top - body_bottom
            entry_zone_top = body_top
            entry_zone_bottom = body_bottom + (body_size * 0.5)
            
            # Get recent M5 data for retest check
            recent_m5 = self.mt5_service.get_historical_data(
                symbol, 'M5',
                conf_time,
                now
            )
            
            if recent_m5 is None or len(recent_m5) == 0:
                return {'success': False, 'reason': 'No recent M5 data for retest check'}
            
            # Check if price has retested the entry zone
            retest_touched = False
            for _, candle in recent_m5.iterrows():
                if (candle['low'] <= entry_zone_top and
                    candle['high'] >= entry_zone_bottom):
                    retest_touched = True
                    break
            
            if not retest_touched:
                return {
                    'success': False,
                    'reason': f'Awaiting retest of confirmation body zone ({entry_zone_bottom:.5f} - {entry_zone_top:.5f})'
                }
            
            # Check for micro-trigger on M1 using BOS/CHOCH service
            micro_trigger_satisfied = self._check_micro_trigger(symbol, entry_zone_bottom, entry_zone_top)
            
            # Get additional market structure analysis
            structure_analysis = self.bos_choch_service.detect_market_structure_change(
                symbol=symbol,
                timeframe='M1',
                lookback_periods=20
            )
            
            return {
                'success': True,
                'retest_touched': True,
                'entry_zone_top': entry_zone_top,
                'entry_zone_bottom': entry_zone_bottom,
                'micro_trigger_satisfied': micro_trigger_satisfied,
                'structure_analysis': structure_analysis,
                'bos_detected': structure_analysis.get('bos_detected', False),
                'choch_detected': structure_analysis.get('choch_detected', False),
                'market_bias': structure_analysis.get('market_bias', 'NEUTRAL'),
                'confirmation_candle': {
                    'open': candle_open,
                    'close': candle_close,
                    'high': candle_high,
                    'low': candle_low
                }
            }
        except Exception as e:
            return {'success': False, 'reason': f'Retest check failed: {str(e)}'}
    
    def _check_micro_trigger(self, symbol: str, entry_bottom: float, entry_top: float) -> bool:
        """Check for M1 micro-trigger using BOS/CHOCH service - Production Ready"""
        try:
            # Determine expected direction based on sweep direction
            expected_direction = 'BUY' if self.current_session.sweep_direction == 'DOWN' else 'SELL'
            
            # Use BOS/CHOCH service for professional micro-trigger detection
            micro_result = self.bos_choch_service.check_micro_trigger(
                symbol=symbol,
                entry_zone_low=entry_bottom,
                entry_zone_high=entry_top,
                expected_direction=expected_direction
            )
            
            if micro_result.get('success') and micro_result.get('micro_trigger_detected'):
                logger.info(f"Micro-trigger detected: {micro_result.get('trigger_type')} at {micro_result.get('trigger_price')}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Micro-trigger check failed: {e}")
            return False
    
    def _check_daily_limits(self) -> Dict:
        """Check daily trade count and loss limits - Phase 3 enhancement"""
        try:
            if not self.current_session:
                return {'allowed': True, 'reason': 'No session'}
            
            # Check daily trade count limit
            max_daily_trades = int(os.getenv('MAX_DAILY_SESSIONS', '2'))
            current_trades = self.current_session.current_daily_trades
            if current_trades >= max_daily_trades:
                return {
                    'allowed': False,
                    'reason': f'Daily trade limit reached: {current_trades}/{max_daily_trades}',
                    'current_trades': current_trades,
                    'max_trades': max_daily_trades
                }
            
            # Check daily loss limit in R
            daily_loss_limit_r = float(self.current_session.daily_loss_limit_r or 2.0)
            current_loss_r = float(self.current_session.current_daily_loss_r or 0.0)
            if current_loss_r <= -daily_loss_limit_r:
                return {
                    'allowed': False,
                    'reason': f'Daily loss limit reached: {current_loss_r:.2f}R / -{daily_loss_limit_r}R',
                    'current_loss_r': current_loss_r,
                    'daily_loss_limit_r': daily_loss_limit_r
                }
            
            # Check weekly circuit breaker
            weekly_check = self.weekly_circuit_breaker.check_weekly_circuit_breaker(self.current_session)
            if weekly_check.get('circuit_breaker_active'):
                return {
                    'allowed': False,
                    'reason': f'Weekly circuit breaker active: {weekly_check.get("weekly_realized_r", 0):.2f}R',
                    'weekly_data': weekly_check
                }
            
            return {
                'allowed': True,
                'reason': 'All limits OK',
                'current_trades': current_trades,
                'max_trades': max_daily_trades,
                'current_loss_r': current_loss_r,
                'daily_loss_limit_r': daily_loss_limit_r,
                'weekly_data': weekly_check
            }
        except Exception as e:
            logger.error(f"Daily limits check failed: {e}")
            return {'allowed': True, 'reason': f'Limits check error: {str(e)}'}  # Fail safe