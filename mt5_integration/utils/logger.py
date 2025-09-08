"""
Enhanced logging configuration for MT5 trading bot.
Implements rotating file handlers and structured logging.
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent.parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Configure root logger
def setup_logging(bot_name="MT5Bot"):
    """Configure the logging system with console and file handlers"""
    logger = logging.getLogger(bot_name)
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
        
    # Formatter for detailed logging
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with color coding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    logger.addHandler(console_handler)
    
    # File handlers with rotation
    # Main log file - 7 days retention
    main_handler = logging.handlers.TimedRotatingFileHandler(
        logs_dir / 'mt5_bot.log',
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(detailed_formatter)
    logger.addHandler(main_handler)
    
    # Error log file - 30 days retention
    error_handler = logging.handlers.TimedRotatingFileHandler(
        logs_dir / 'mt5_bot_errors.log',
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Trade log file - 90 days retention
    trade_handler = logging.handlers.TimedRotatingFileHandler(
        logs_dir / 'mt5_trades.log',
        when='midnight',
        interval=1,
        backupCount=90,
        encoding='utf-8'
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.setFormatter(detailed_formatter)
    logger.addHandler(trade_handler)
    
    return logger

# Trading specific logger
def log_trade(logger, trade_type, **kwargs):
    """Log trade related information in a structured format"""
    trade_info = {
        'timestamp': datetime.now().isoformat(),
        'type': trade_type,
        **kwargs
    }
    logger.info(f"TRADE | {trade_info}")

# System health logger
def log_health_check(logger, status, **kwargs):
    """Log system health check information"""
    health_info = {
        'timestamp': datetime.now().isoformat(),
        'status': status,
        **kwargs
    }
    level = logging.ERROR if status == 'UNHEALTHY' else logging.INFO
    logger.log(level, f"HEALTH | {health_info}")

# Get the main logger instance
logger = setup_logging()
