import os
from dotenv import load_dotenv

load_dotenv()

# Asian Session
ASIAN_SESSION_START_UTC = os.getenv('ASIAN_SESSION_START_UTC', '00:00')
ASIAN_SESSION_END_UTC = os.getenv('ASIAN_SESSION_END_UTC', '06:00')

# Pip values
XAUUSD_PIP_VALUE = float(os.getenv('XAUUSD_PIP_VALUE', '0.1'))
EURUSD_PIP_VALUE = float(os.getenv('EURUSD_PIP_VALUE', '0.0001'))
GBPUSD_PIP_VALUE = float(os.getenv('GBPUSD_PIP_VALUE', '0.0001'))
USDJPY_PIP_VALUE = float(os.getenv('USDJPY_PIP_VALUE', '0.01'))

# Asian Range Grading
NO_TRADE_THRESHOLD = float(os.getenv('NO_TRADE_THRESHOLD', '30'))
TIGHT_RANGE_THRESHOLD = float(os.getenv('TIGHT_RANGE_THRESHOLD', '49'))
NORMAL_RANGE_THRESHOLD = float(os.getenv('NORMAL_RANGE_THRESHOLD', '150'))
WIDE_RANGE_THRESHOLD = float(os.getenv('WIDE_RANGE_THRESHOLD', '180'))
MAX_RANGE_THRESHOLD = float(os.getenv('MAX_RANGE_THRESHOLD', '180'))

# Risk mapping
TIGHT_RISK_PERCENTAGE = float(os.getenv('TIGHT_RISK_PERCENTAGE', '0.005'))  # 0.5%
NORMAL_RISK_PERCENTAGE = float(os.getenv('NORMAL_RISK_PERCENTAGE', '0.005'))  # 0.5%
WIDE_RISK_PERCENTAGE = float(os.getenv('WIDE_RISK_PERCENTAGE', '0.005'))  # 0.5%
MAX_RISK_PER_TRADE = float(os.getenv('MAX_RISK_PER_TRADE', '0.5'))  # 0.5%

# Sweep threshold formula
SWEEP_THRESHOLD_FLOOR_PIPS = float(os.getenv('SWEEP_THRESHOLD_FLOOR_PIPS', '10'))
SWEEP_THRESHOLD_PCT_MIN = float(os.getenv('SWEEP_THRESHOLD_PCT_MIN', '0.075'))  # 7.5%
SWEEP_THRESHOLD_PCT_MAX = float(os.getenv('SWEEP_THRESHOLD_PCT_MAX', '0.10'))   # 10%
SWEEP_THRESHOLD_PCT_XAU = float(os.getenv('SWEEP_THRESHOLD_PCT_XAU', '0.09'))   # 9% for XAU
SWEEP_THRESHOLD_PIPS = int(os.getenv('SWEEP_THRESHOLD_PIPS', '5'))

# Displacement multiplier
DISPLACEMENT_K_NORMAL = float(os.getenv('DISPLACEMENT_K_NORMAL', '1.3'))
DISPLACEMENT_K_HIGH_VOL = float(os.getenv('DISPLACEMENT_K_HIGH_VOL', '1.5'))

# ATR/ADX
ATR_H1_LOOKBACK = int(os.getenv('ATR_H1_LOOKBACK', '14'))
ADX_15M_LOOKBACK = int(os.getenv('ADX_15M_LOOKBACK', '14'))
ADX_TREND_THRESHOLD = float(os.getenv('ADX_TREND_THRESHOLD', '25'))

# Spread & Volatility
MAX_SPREAD_PIPS = float(os.getenv('MAX_SPREAD_PIPS', '2.0'))
VELOCITY_SPIKE_MULTIPLIER = float(os.getenv('VELOCITY_SPIKE_MULTIPLIER', '2.0'))

# News & LBMA
TIER1_NEWS_BUFFER_MINUTES = int(os.getenv('TIER1_NEWS_BUFFER_MINUTES', '60'))
OTHER_NEWS_BUFFER_MINUTES = int(os.getenv('OTHER_NEWS_BUFFER_MINUTES', '30'))
LBMA_AUCTION_TIMES = os.getenv('LBMA_AUCTION_TIMES', '10:30,15:00')
LBMA_AUCTION_BUFFER_MINUTES = int(os.getenv('LBMA_AUCTION_BUFFER_MINUTES', '15'))

# Retest/Timeouts
CONFIRMATION_TIMEOUT_MINUTES = int(os.getenv('CONFIRMATION_TIMEOUT_MINUTES', '30'))
RETEST_MIN_BARS = int(os.getenv('RETEST_MIN_BARS', '1'))
RETEST_MAX_BARS = int(os.getenv('RETEST_MAX_BARS', '3'))
RETEST_BAR_MINUTES = int(os.getenv('RETEST_BAR_MINUTES', '5'))

# SL/TP buffers
SL_BUFFER_PIPS_MIN = float(os.getenv('SL_BUFFER_PIPS_MIN', '2'))
SL_BUFFER_PIPS_MAX = float(os.getenv('SL_BUFFER_PIPS_MAX', '5'))

# Daily/Weekly limits
DAILY_TRADE_COUNT_LIMIT = int(os.getenv('DAILY_TRADE_COUNT_LIMIT', '2'))
DAILY_LOSS_LIMIT_R = float(os.getenv('DAILY_LOSS_LIMIT_R', '2.0'))
WEEKLY_LOSS_LIMIT_R = float(os.getenv('WEEKLY_LOSS_LIMIT_R', '6.0'))

# Trailing stop
TRAILING_ATR_M5_MULTIPLIER = float(os.getenv('TRAILING_ATR_M5_MULTIPLIER', '0.75'))

# Misc
MIN_LOT_SIZE = float(os.getenv('MIN_LOT_SIZE', '0.01'))
LOT_SIZE_STEP = float(os.getenv('LOT_SIZE_STEP', '0.01'))

# Timezone
TIMEZONE = os.getenv('TIMEZONE', 'UTC')

# Add more as needed for full strategy coverage
