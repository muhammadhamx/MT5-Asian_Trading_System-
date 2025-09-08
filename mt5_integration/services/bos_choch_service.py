"""
BOS/CHOCH Service - Break of Structure / Change of Character Detection
Critical component for micro-trigger detection and market structure analysis
"""

import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class BOSCHOCHService:
    """
    Break of Structure (BOS) and Change of Character (CHOCH) Detection Service
    
    BOS: Price breaks previous structure (higher high/lower low)
    CHOCH: Market character changes from bullish to bearish or vice versa
    """
    
    def __init__(self, mt5_service):
        self.mt5_service = mt5_service
        self.swing_lookback = int(os.getenv('SWING_LOOKBACK_PERIODS', '5'))
        self.structure_confirmation_bars = int(os.getenv('STRUCTURE_CONFIRMATION_BARS', '2'))
        
    def detect_market_structure_change(self, symbol: str, timeframe: str = 'M1', 
                                     lookback_periods: int = 50) -> Dict:
        """
        Detect BOS/CHOCH on specified timeframe
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Chart timeframe ('M1', 'M5', 'M15', etc.)
            lookback_periods: Number of bars to analyze
            
        Returns:
            Dict with structure analysis results
        """
        try:
            # Get historical data
            end_time = timezone.now()
            start_time = end_time - timedelta(minutes=lookback_periods * self._get_timeframe_minutes(timeframe))
            
            data = self.mt5_service.get_historical_data(symbol, timeframe, start_time, end_time)
            
            if data is None or len(data) < 20:
                return {
                    'success': False,
                    'error': 'Insufficient data for structure analysis',
                    'bos_detected': False,
                    'choch_detected': False
                }
            
            # Identify swing highs and lows
            swing_highs, swing_lows = self._identify_swing_points(data)
            
            # Detect BOS (Break of Structure)
            bos_result = self._detect_bos(data, swing_highs, swing_lows)
            
            # Detect CHOCH (Change of Character)
            choch_result = self._detect_choch(data, swing_highs, swing_lows)
            
            # Determine current market bias
            market_bias = self._determine_market_bias(data, swing_highs, swing_lows)
            
            return {
                'success': True,
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': timezone.now().isoformat(),
                'bos_detected': bos_result['detected'],
                'bos_type': bos_result.get('type'),
                'bos_price': bos_result.get('price'),
                'bos_time': bos_result.get('time'),
                'choch_detected': choch_result['detected'],
                'choch_type': choch_result.get('type'),
                'choch_price': choch_result.get('price'),
                'choch_time': choch_result.get('time'),
                'market_bias': market_bias,
                'swing_highs': swing_highs[-5:] if len(swing_highs) > 5 else swing_highs,
                'swing_lows': swing_lows[-5:] if len(swing_lows) > 5 else swing_lows,
                'current_price': float(data['close'].iloc[-1])
            }
            
        except Exception as e:
            logger.error(f"Market structure detection failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'bos_detected': False,
                'choch_detected': False
            }
    
    def check_micro_trigger(self, symbol: str, entry_zone_low: float, entry_zone_high: float,
                          expected_direction: str = 'BUY') -> Dict:
        """
        Check for M1 micro-trigger within entry zone
        Used for retest confirmation in signal detection
        
        Args:
            symbol: Trading symbol
            entry_zone_low: Lower boundary of entry zone
            entry_zone_high: Upper boundary of entry zone
            expected_direction: Expected trade direction ('BUY' or 'SELL')
            
        Returns:
            Dict with micro-trigger analysis
        """
        try:
            # Get recent M1 data
            end_time = timezone.now()
            start_time = end_time - timedelta(minutes=15)  # Last 15 minutes
            
            m1_data = self.mt5_service.get_historical_data(symbol, 'M1', start_time, end_time)
            
            if m1_data is None or len(m1_data) < 3:
                return {
                    'success': False,
                    'micro_trigger_detected': False,
                    'reason': 'Insufficient M1 data'
                }
            
            # Check for price action within entry zone
            in_zone_bars = m1_data[
                (m1_data['low'] >= entry_zone_low) & 
                (m1_data['high'] <= entry_zone_high)
            ]
            
            if len(in_zone_bars) == 0:
                return {
                    'success': True,
                    'micro_trigger_detected': False,
                    'reason': 'No price action in entry zone yet'
                }
            
            # Detect structure change within entry zone
            structure_result = self._analyze_micro_structure(in_zone_bars, expected_direction)
            
            return {
                'success': True,
                'micro_trigger_detected': structure_result['trigger_detected'],
                'trigger_type': structure_result.get('trigger_type'),
                'trigger_price': structure_result.get('trigger_price'),
                'trigger_time': structure_result.get('trigger_time'),
                'confidence': structure_result.get('confidence', 0),
                'entry_zone_low': entry_zone_low,
                'entry_zone_high': entry_zone_high,
                'bars_in_zone': len(in_zone_bars),
                'expected_direction': expected_direction
            }
            
        except Exception as e:
            logger.error(f"Micro-trigger check failed: {e}")
            return {
                'success': False,
                'micro_trigger_detected': False,
                'error': str(e)
            }
    
    def _identify_swing_points(self, data: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """Identify swing highs and lows in price data"""
        swing_highs = []
        swing_lows = []
        
        if len(data) < self.swing_lookback * 2 + 1:
            return swing_highs, swing_lows
        
        for i in range(self.swing_lookback, len(data) - self.swing_lookback):
            # Check for swing high
            is_swing_high = True
            current_high = data['high'].iloc[i]
            
            for j in range(i - self.swing_lookback, i + self.swing_lookback + 1):
                if j != i and data['high'].iloc[j] >= current_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append({
                    'index': i,
                    'price': float(current_high),
                    'time': data.index[i].isoformat() if hasattr(data.index[i], 'isoformat') else str(data.index[i])
                })
            
            # Check for swing low
            is_swing_low = True
            current_low = data['low'].iloc[i]
            
            for j in range(i - self.swing_lookback, i + self.swing_lookback + 1):
                if j != i and data['low'].iloc[j] <= current_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append({
                    'index': i,
                    'price': float(current_low),
                    'time': data.index[i].isoformat() if hasattr(data.index[i], 'isoformat') else str(data.index[i])
                })
        
        return swing_highs, swing_lows
    
    def _detect_bos(self, data: pd.DataFrame, swing_highs: List[Dict], 
                   swing_lows: List[Dict]) -> Dict:
        """Detect Break of Structure"""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {'detected': False}
        
        current_price = float(data['close'].iloc[-1])
        latest_time = data.index[-1]
        
        # Check for bullish BOS (break above previous swing high)
        if len(swing_highs) >= 2:
            previous_high = swing_highs[-2]['price']
            latest_high = swing_highs[-1]['price']
            
            if current_price > previous_high and latest_high > previous_high:
                return {
                    'detected': True,
                    'type': 'BULLISH_BOS',
                    'price': float(current_price),
                    'time': latest_time.isoformat() if hasattr(latest_time, 'isoformat') else str(latest_time),
                    'broken_level': previous_high
                }
        
        # Check for bearish BOS (break below previous swing low)
        if len(swing_lows) >= 2:
            previous_low = swing_lows[-2]['price']
            latest_low = swing_lows[-1]['price']
            
            if current_price < previous_low and latest_low < previous_low:
                return {
                    'detected': True,
                    'type': 'BEARISH_BOS',
                    'price': float(current_price),
                    'time': latest_time.isoformat() if hasattr(latest_time, 'isoformat') else str(latest_time),
                    'broken_level': previous_low
                }
        
        return {'detected': False}
    
    def _detect_choch(self, data: pd.DataFrame, swing_highs: List[Dict], 
                     swing_lows: List[Dict]) -> Dict:
        """Detect Change of Character"""
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return {'detected': False}
        
        # Analyze recent swing pattern for character change
        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        
        # Check for bullish to bearish CHOCH
        if (len(recent_highs) >= 2 and len(recent_lows) >= 2):
            # Was making higher highs, now making lower highs
            if (recent_highs[-2]['price'] > recent_highs[-3]['price'] and 
                recent_highs[-1]['price'] < recent_highs[-2]['price']):
                
                return {
                    'detected': True,
                    'type': 'BEARISH_CHOCH',
                    'price': recent_highs[-1]['price'],
                    'time': recent_highs[-1]['time']
                }
        
        # Check for bearish to bullish CHOCH
        if (len(recent_lows) >= 2):
            # Was making lower lows, now making higher lows
            if (recent_lows[-2]['price'] < recent_lows[-3]['price'] and 
                recent_lows[-1]['price'] > recent_lows[-2]['price']):
                
                return {
                    'detected': True,
                    'type': 'BULLISH_CHOCH',
                    'price': recent_lows[-1]['price'],
                    'time': recent_lows[-1]['time']
                }
        
        return {'detected': False}
    
    def _determine_market_bias(self, data: pd.DataFrame, swing_highs: List[Dict], 
                              swing_lows: List[Dict]) -> str:
        """Determine current market bias based on structure"""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 'NEUTRAL'
        
        # Check recent swing pattern
        recent_highs = swing_highs[-2:]
        recent_lows = swing_lows[-2:]
        
        higher_highs = recent_highs[-1]['price'] > recent_highs[-2]['price']
        higher_lows = recent_lows[-1]['price'] > recent_lows[-2]['price']
        lower_highs = recent_highs[-1]['price'] < recent_highs[-2]['price']
        lower_lows = recent_lows[-1]['price'] < recent_lows[-2]['price']
        
        if higher_highs and higher_lows:
            return 'BULLISH'
        elif lower_highs and lower_lows:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _analyze_micro_structure(self, data: pd.DataFrame, expected_direction: str) -> Dict:
        """Analyze micro-structure for trigger confirmation"""
        if len(data) < 2:
            return {'trigger_detected': False}
        
        # Look for engulfing patterns or strong directional moves
        for i in range(1, len(data)):
            current = data.iloc[i]
            previous = data.iloc[i-1]
            
            if expected_direction == 'BUY':
                # Look for bullish engulfing or strong bullish close
                bullish_engulfing = (
                    current['close'] > current['open'] and
                    previous['close'] < previous['open'] and
                    current['close'] > previous['open'] and
                    current['open'] < previous['close']
                )
                
                strong_bullish = (
                    current['close'] > current['open'] and
                    current['close'] > previous['high']
                )
                
                if bullish_engulfing or strong_bullish:
                    return {
                        'trigger_detected': True,
                        'trigger_type': 'BULLISH_ENGULFING' if bullish_engulfing else 'BULLISH_BREAKOUT',
                        'trigger_price': float(current['close']),
                        'trigger_time': current.name.isoformat() if hasattr(current.name, 'isoformat') else str(current.name),
                        'confidence': 85 if bullish_engulfing else 70
                    }
            
            elif expected_direction == 'SELL':
                # Look for bearish engulfing or strong bearish close
                bearish_engulfing = (
                    current['close'] < current['open'] and
                    previous['close'] > previous['open'] and
                    current['close'] < previous['open'] and
                    current['open'] > previous['close']
                )
                
                strong_bearish = (
                    current['close'] < current['open'] and
                    current['close'] < previous['low']
                )
                
                if bearish_engulfing or strong_bearish:
                    return {
                        'trigger_detected': True,
                        'trigger_type': 'BEARISH_ENGULFING' if bearish_engulfing else 'BEARISH_BREAKOUT',
                        'trigger_price': float(current['close']),
                        'trigger_time': current.name.isoformat() if hasattr(current.name, 'isoformat') else str(current.name),
                        'confidence': 85 if bearish_engulfing else 70
                    }
        
        return {'trigger_detected': False}
    
    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        timeframe_map = {
            'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
            'H1': 60, 'H4': 240, 'D1': 1440
        }
        return timeframe_map.get(timeframe, 1)
