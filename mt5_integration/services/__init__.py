from .mt5_service import MT5Service
from .mock_mt5_service import MockMT5Service
from .asian_range_service import AsianRangeService
from .signal_detection_service import SignalDetectionService
import os
import logging

# Configure logging
logger = logging.getLogger('api_requests')

# Determine whether to use real or mock MT5 service
# Changed default to False to use REAL MT5 service for trading
USE_MOCK = os.environ.get('USE_MOCK_MT5', 'False').lower() in ('true', '1', 't')

# Create shared instances
if USE_MOCK:
    logger.info("Using MOCK MT5 Service for development")
    mt5_service = MockMT5Service()
    # Auto-connect the mock service
    mt5_service.connect(12345678, "password", "Demo-Server")
else:
    logger.info("Using REAL MT5 Service for production trading")
    mt5_service = MT5Service()
    # Initialize and connect to real MT5
    success = mt5_service.initialize_mt5()
    if success:
        # Connect to account using environment variables with validation
        try:
            login_str = os.environ.get('MT5_LOGIN', '0')
            # Validate login is numeric and not placeholder
            if login_str.isdigit():
                login = int(login_str)
            else:
                logger.error(f"Invalid MT5_LOGIN format: {login_str}. Must be numeric account number.")
                login = 0

            password = os.environ.get('MT5_PASSWORD', '')
            server = os.environ.get('MT5_SERVER', 'MetaQuotes-Demo')

            # Check for placeholder values
            if login > 0 and password and not password.startswith('YOUR_'):
                connected, error = mt5_service.connect(login, password, server)
                if connected:
                    logger.info(f"Connected to MT5 account {login} on {server}")
                else:
                    logger.error(f"Failed to connect to MT5 account: {error}")
            else:
                logger.warning("MT5 credentials not configured or contain placeholder values")
                logger.warning("Set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER in .env for production")

        except ValueError as e:
            logger.error(f"Error parsing MT5 credentials: {e}")

        logger.info("Real MT5 Service initialized successfully")
    else:
        logger.error("Failed to initialize Real MT5 Service")

asian_range_service = AsianRangeService(mt5_service)
signal_detection_service = SignalDetectionService(mt5_service)

__all__ = [
    'mt5_service',
    'asian_range_service',
    'signal_detection_service',
    'MT5Service',
    'MockMT5Service',
    'AsianRangeService',
    'SignalDetectionService'
]