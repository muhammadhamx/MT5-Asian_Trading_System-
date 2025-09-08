"""
Mock MT5 Service for development and testing
"""
import random
import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone
from typing import Dict, List, Tuple, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger('api_requests')

class MockMT5Service:
    """Mock implementation of MT5Service for development and testing"""
    
    def __init__(self):
        self.connected = False
        self.account = None  # Add missing account attribute for production compatibility
        self.account_info = {
            'login': int(os.getenv('MOCK_ACCOUNT_LOGIN', '12345678')),
            'server': os.getenv('MOCK_ACCOUNT_SERVER', 'Demo-Server'),
            'currency': os.getenv('MOCK_ACCOUNT_CURRENCY', 'USD'),
            'leverage': int(os.getenv('MOCK_ACCOUNT_LEVERAGE', '100')),
            'margin_free': float(os.getenv('MOCK_ACCOUNT_BALANCE', '10000.0')),
            'balance': float(os.getenv('MOCK_ACCOUNT_BALANCE', '10000.0')),
            'equity': float(os.getenv('MOCK_ACCOUNT_BALANCE', '10000.0')),
            'margin': 0.0,
            'margin_level': 0.0,
        }
        self.positions = []
        self.orders = []
        self.symbols = os.getenv('AVAILABLE_SYMBOLS', 'XAUUSD,EURUSD,GBPUSD,USDJPY').split(',')
        self.current_prices = {
            'XAUUSD': {
                'bid': float(os.getenv('MOCK_XAUUSD_BASE_PRICE', '2000.0')),
                'ask': float(os.getenv('MOCK_XAUUSD_BASE_PRICE', '2000.0')) + 0.5
            },
            'EURUSD': {
                'bid': float(os.getenv('MOCK_EURUSD_BASE_PRICE', '1.1000')),
                'ask': float(os.getenv('MOCK_EURUSD_BASE_PRICE', '1.1000')) + 0.0002
            },
            'GBPUSD': {
                'bid': float(os.getenv('MOCK_GBPUSD_BASE_PRICE', '1.3000')),
                'ask': float(os.getenv('MOCK_GBPUSD_BASE_PRICE', '1.3000')) + 0.0002
            },
            'USDJPY': {
                'bid': float(os.getenv('MOCK_USDJPY_BASE_PRICE', '110.00')),
                'ask': float(os.getenv('MOCK_USDJPY_BASE_PRICE', '110.00')) + 0.02
            },
        }
        
        # Mock Asian range data from environment variables
        mock_high = float(os.getenv('MOCK_ASIAN_RANGE_HIGH', '2005.0'))
        mock_low = float(os.getenv('MOCK_ASIAN_RANGE_LOW', '1995.0'))
        mock_pips = float(os.getenv('MOCK_ASIAN_RANGE_PIPS', '100'))

        self.asian_range = {
            'XAUUSD': {
                'high': mock_high,
                'low': mock_low,
                'midpoint': (mock_high + mock_low) / 2,
                'range_pips': mock_pips,
                'grade': 'NORMAL',
            }
        }
        
        logger.info("Mock MT5 Service initialized")
    
    def connect(self, account: int, password: Optional[str] = None, server: str = "MetaQuotes-Demo") -> Tuple[bool, Union[str, Tuple[int, str]]]:
        """Mock connection to MT5"""
        logger.info(f"Mock MT5 connect called with account: {account}, server: {server}")
        self.connected = True
        self.account = account  # Set account attribute for production compatibility
        self.account_info['login'] = account
        self.account_info['server'] = server
        return True, None
    
    def disconnect(self) -> None:
        """Mock disconnect from MT5"""
        logger.info("Mock MT5 disconnect called")
        self.connected = False
    
    def get_account_info(self) -> Dict:
        """Get mock account information"""
        if not self.connected:
            logger.warning("Attempted to get account info while not connected")
            return {}
        
        # Simulate some random changes to make it look real
        self.account_info['equity'] = self.account_info['balance'] + random.uniform(-100, 100)
        self.account_info['margin_free'] = self.account_info['equity'] - self.account_info['margin']
        
        logger.info(f"Mock account info: {self.account_info}")
        return self.account_info
    
    def get_positions(self) -> List[Dict]:
        """Get mock open positions"""
        if not self.connected:
            logger.warning("Attempted to get positions while not connected")
            return []
        
        # Update position profits
        for pos in self.positions:
            # Simulate profit/loss changes
            pos['profit'] = random.uniform(-50, 50)
        
        logger.info(f"Mock positions: {self.positions}")
        return self.positions
    
    def get_symbol_info_tick(self, symbol: str) -> Dict:
        """Get mock current price for a symbol"""
        if not self.connected:
            logger.warning(f"Attempted to get symbol info for {symbol} while not connected")
            return {}

        if symbol not in self.current_prices:
            logger.warning(f"Symbol {symbol} not found in mock data")
            return {}

        # Simulate price movements with occasional larger moves to trigger sweeps
        # 50% chance of small movements, 50% chance of larger movements (for testing)
        if random.random() < 0.5:
            # Small movements within Asian range
            movement = random.uniform(-0.5, 0.5)
        else:
            # Larger movements that could trigger sweeps
            # For XAUUSD with Asian range 1995-2005, we need moves beyond ±10 pips from range
            if random.random() < 0.5:
                # Upward sweep: move above 2005 + 10 = 2015
                movement = random.uniform(15, 25)  # Move to 2015-2025 range
            else:
                # Downward sweep: move below 1995 - 10 = 1985
                movement = random.uniform(-25, -15)  # Move to 1975-1985 range

        bid = self.current_prices[symbol]['bid'] + movement
        ask = bid + random.uniform(0.1, 0.5)

        self.current_prices[symbol] = {'bid': bid, 'ask': ask}

        logger.info(f"Mock price for {symbol}: bid={bid}, ask={ask} (movement: {movement:+.2f})")
        return {
            'symbol': symbol,
            'bid': bid,
            'ask': ask,
            'time': timezone.now().timestamp(),
        }
        
    def get_current_price(self, symbol: str) -> Dict:
        """Get current price for a symbol"""
        tick = self.get_symbol_info_tick(symbol)
        if tick and 'bid' in tick:
            return {
                'symbol': symbol,
                'bid': tick['bid'],
                'ask': tick['ask'],
                'last': tick['bid'],  # Use bid as last for simplicity
                'volume': 100,
                'time': timezone.now().isoformat()
            }
        return None
    
    def get_asian_session_data(self, symbol: str) -> Dict:
        """Get mock Asian session data with enhanced payload"""
        if not self.connected:
            logger.warning(f"Attempted to get Asian session data for {symbol} while not connected")
            return {'success': False, 'error': 'Not connected to MT5'}

        if symbol not in self.asian_range:
            logger.warning(f"Symbol {symbol} not found in mock Asian range data")
            return {'success': False, 'error': f'No data for {symbol}'}

        from datetime import datetime
        now_utc = datetime.utcnow()
        today_utc = now_utc.date()

        result = self.asian_range[symbol].copy()
        result.update({
            'success': True,
            'session_date': today_utc.isoformat(),
            'start_time': datetime.combine(today_utc, datetime.min.time().replace(hour=0)),
            'end_time': datetime.combine(today_utc, datetime.min.time().replace(hour=6)),
            'timezone': 'UTC',
            'data_points': 72,  # Mock 72 M5 candles for 6 hours
            'calculation_timestamp': now_utc.isoformat(),
            'pip_multiplier': 10.0 if symbol == 'XAUUSD' else 10000.0,
            'sweep_threshold': {
                'threshold_pips': 10.0,
                'chosen_component': 'floor_minimum',
                'components': {
                    'floor_pips': 10.0,
                    'range_percentage': 9.0,
                    'atr_component': 8.5
                }
            },
            'traceability': {
                'method': 'get_asian_session_data',
                'service': 'MockMT5Service',
                'data_source': 'mock_data',
                'calculation_time': now_utc.isoformat(),
                'session_window': f"{today_utc.isoformat()}T00:00:00_to_{today_utc.isoformat()}T06:00:00"
            }
        })

        logger.info(f"Mock Asian range for {symbol}: {result}")
        return result
    
    def place_market_order(self, symbol: str, trade_type: str, volume: float, 
                          stop_loss: float = 0.0, take_profit: float = 0.0, 
                          deviation: int = 10, comment: str = "") -> Dict:
        """Place a mock market order"""
        if not self.connected:
            logger.warning(f"Attempted to place order for {symbol} while not connected")
            return {'success': False, 'error': 'Not connected to MT5'}
        
        # Get current price
        price_info = self.get_symbol_info_tick(symbol)
        if not price_info:
            return {'success': False, 'error': f'Failed to get price for {symbol}'}
        
        # Use appropriate price based on trade type
        price = price_info['ask'] if trade_type == 'BUY' else price_info['bid']
        
        # Create a new position
        position_id = random.randint(10000000, 99999999)
        position = {
            'ticket': position_id,
            'symbol': symbol,
            'type': trade_type,
            'volume': volume,
            'price_open': price,
            'sl': stop_loss,
            'tp': take_profit,
            'profit': 0.0,
            'time': timezone.now().timestamp(),
            'comment': comment,
        }
        
        self.positions.append(position)
        
        logger.info(f"Mock order placed: {position}")
        return {
            'success': True,
            'order_id': position_id,
            'price': price,
            'volume': volume,
            'type': trade_type,
        }
    
    def close_position(self, ticket: int) -> Dict:
        """Close a mock position"""
        if not self.connected:
            logger.warning(f"Attempted to close position {ticket} while not connected")
            return {'success': False, 'error': 'Not connected to MT5'}
        
        # Find the position
        position = None
        for pos in self.positions:
            if pos['ticket'] == ticket:
                position = pos
                break
        
        if not position:
            logger.warning(f"Position {ticket} not found")
            return {'success': False, 'error': f'Position {ticket} not found'}
        
        # Remove from positions list
        self.positions = [pos for pos in self.positions if pos['ticket'] != ticket]
        
        # Simulate profit/loss
        profit = random.uniform(-50, 50)
        
        logger.info(f"Mock position {ticket} closed with profit {profit}")
        return {
            'success': True,
            'ticket': ticket,
            'profit': profit,
        }
    
    def get_historical_data(self, symbol: str, timeframe: str, start_time, end_time):
        """Get mock historical data"""
        import pandas as pd

        if not self.connected:
            logger.warning(f"Attempted to get historical data for {symbol} while not connected")
            return None

        # Generate mock historical data from environment variables
        periods = int(os.getenv('MOCK_DATA_PERIODS', '20'))
        base_price = float(os.getenv(f'MOCK_{symbol.upper()}_BASE_PRICE', '2000.0'))

        data = []
        for i in range(periods):
            # Generate realistic OHLC data
            open_price = base_price + random.uniform(-5, 5)
            high_price = open_price + random.uniform(0, 3)
            low_price = open_price - random.uniform(0, 3)
            close_price = open_price + random.uniform(-2, 2)

            interval_minutes = int(os.getenv('MOCK_DATA_INTERVAL_MINUTES', '5'))
            data.append({
                'time': start_time + pd.Timedelta(minutes=i*interval_minutes),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': random.randint(100, 1000)
            })

        df = pd.DataFrame(data)
        logger.info(f"Mock historical data generated for {symbol}: {len(df)} records")
        return df

    def get_error_description(self, code: int) -> str:
        """Get mock error description"""
        error_codes = {
            0: 'No error',
            1: 'Generic error',
            2: 'Invalid parameters',
            3: 'Connection error',
            4: 'Not enough money',
            5: 'Server error',
        }
        return error_codes.get(code, f'Unknown error code: {code}')