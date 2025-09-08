"""
Enhanced auto trading watcher with improved error handling and logging.
Manages 24/7 operation of the MT5 trading bot.
"""

import os
import time
import threading
import signal
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mt5_drf_project.settings')
django.setup()

from mt5_integration.services.signal_detection_service import SignalDetectionService
from mt5_integration.services.mt5_service import MT5Service
from mt5_integration.utils.logger import setup_logging, log_health_check

# Configuration
AUTO_TRADING_INTERVAL = int(os.getenv('AUTO_TRADING_INTERVAL', '30'))  # seconds
ENABLE_AUTO_TRADING = os.getenv('ENABLE_AUTO_TRADING', 'True').lower() == 'true'
SYMBOL = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')
MAX_RETRY_COUNT = 3
RETRY_DELAY = 5  # seconds

# Setup logging
logger = setup_logging('AutoTrader')
mt5_service = MT5Service()
signal_service = SignalDetectionService(mt5_service)

class AutoTradingWatcher:
    def __init__(self):
        self.running = False
        self.last_health_check = datetime.now()
        self.health_check_interval = timedelta(minutes=5)
        self.error_count = 0
        self.last_error_time = None
        
    def perform_health_check(self):
        """Perform system health checks"""
        try:
            # Check MT5 connection
            mt5_connected = mt5_service.check_connection()
            if not mt5_connected:
                log_health_check(logger, 'UNHEALTHY', component='MT5', reason='Connection lost')
                self.reconnect_mt5()
                return False
                
            # Check database connection
            try:
                from django.db import connection
                connection.ensure_connection()
            except Exception as e:
                log_health_check(logger, 'UNHEALTHY', component='Database', reason=str(e))
                return False
                
            # Check system resources
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                log_health_check(logger, 'WARNING', component='System', reason='High memory usage')
            
            log_health_check(logger, 'HEALTHY', memory_usage=f"{memory.percent}%")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
            
    def reconnect_mt5(self):
        """Attempt to reconnect to MT5"""
        retry_count = 0
        while retry_count < MAX_RETRY_COUNT:
            try:
                logger.info("Attempting to reconnect to MT5...")
                mt5_service.connect()
                if mt5_service.check_connection():
                    logger.info("Successfully reconnected to MT5")
                    return True
            except Exception as e:
                retry_count += 1
                logger.error(f"MT5 reconnection attempt {retry_count} failed: {e}")
                time.sleep(RETRY_DELAY)
        return False

    def handle_error(self, error):
        """Handle errors with exponential backoff"""
        current_time = datetime.now()
        if self.last_error_time and (current_time - self.last_error_time) < timedelta(minutes=5):
            self.error_count += 1
        else:
            self.error_count = 1
        
        self.last_error_time = current_time
        wait_time = min(300, 5 * (2 ** self.error_count))  # Max 5 minutes
        
        logger.error(f"Error occurred: {error}")
        logger.info(f"Waiting {wait_time} seconds before retry...")
        return wait_time

    def trading_loop(self):
        """Main trading loop with error handling"""
        while self.running:
            try:
                # Perform periodic health check
                if datetime.now() - self.last_health_check > self.health_check_interval:
                    self.perform_health_check()
                    self.last_health_check = datetime.now()
                
                # Run trading analysis
                result = signal_service.run_full_analysis(SYMBOL)
                logger.info(f"Analysis result: {result}")
                
                # Reset error count on successful iteration
                self.error_count = 0
                time.sleep(AUTO_TRADING_INTERVAL)
                
            except Exception as e:
                wait_time = self.handle_error(e)
                time.sleep(wait_time)

    def start(self):
        """Start the auto trading watcher"""
        self.running = True
        logger.info("Starting Auto Trading Watcher...")
        
        # Perform initial health check
        if not self.perform_health_check():
            logger.error("Initial health check failed. Attempting recovery...")
            if not self.perform_health_check():
                logger.error("Recovery failed. Please check system status.")
                return
        
        self.trading_thread = threading.Thread(target=self.trading_loop)
        self.trading_thread.daemon = True
        self.trading_thread.start()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        logger.info(f"Auto Trading Watcher started. Interval: {AUTO_TRADING_INTERVAL}s")
        
    def stop(self):
        """Stop the auto trading watcher"""
        logger.info("Stopping Auto Trading Watcher...")
        self.running = False
        if hasattr(self, 'trading_thread'):
            self.trading_thread.join(timeout=5.0)
        logger.info("Auto Trading Watcher stopped.")
        
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received shutdown signal {signum}")
        self.stop()

if __name__ == "__main__":
    if not ENABLE_AUTO_TRADING:
        logger.warning("Auto trading is disabled in configuration.")
        sys.exit(0)
        
    watcher = AutoTradingWatcher()
    watcher.start()
    
    try:
        # Keep main thread alive
        while watcher.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    finally:
        watcher.stop()
