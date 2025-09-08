import os
import threading
import time
import logging
from mt5_integration.services.mt5_service import MT5Service
from mt5_integration.services.signal_detection_service import SignalDetectionService

# Configure logger
logger = logging.getLogger('trading_bot')

AUTO_TRADING_INTERVAL = int(os.getenv('AUTO_TRADING_INTERVAL', '30'))
ENABLE_AUTO_TRADING = os.getenv('ENABLE_AUTO_TRADING', 'True').lower() == 'true'
SYMBOL = os.getenv('DEFAULT_SYMBOL', 'XAUUSD')

mt5_service = MT5Service()
signal_service = SignalDetectionService(mt5_service)

def auto_trade_main_loop():
    """Main trading bot loop that runs continuously when enabled"""
    logger.info(f"[AutoTrade] Main auto mode loop started. Interval: {AUTO_TRADING_INTERVAL}s")
    
    while ENABLE_AUTO_TRADING:
        try:
            # Main auto mode logic: let bot decide its own state
            session_result = signal_service.initialize_session(SYMBOL)
            current_state = signal_service.current_session.current_state if signal_service.current_session else 'IDLE'
            logger.info(f"[AutoTrade] Current state: {current_state}")
            
            if current_state == 'IDLE':
                sweep_result = signal_service.detect_sweep(SYMBOL)
                logger.info(f"[AutoTrade] Sweep: {sweep_result}")

                if sweep_result.get('sweep_detected'):
                    current_state = 'SWEPT'
            if current_state == 'SWEPT':
                reversal_result = signal_service.confirm_reversal(SYMBOL)
                logger.info(f"[AutoTrade] Reversal: {reversal_result}")
                if reversal_result.get('confirmed'):
                    current_state = 'CONFIRMED'
            if current_state == 'CONFIRMED':
                confluence_result = signal_service.check_confluence(SYMBOL)
                logger.info(f"[AutoTrade] Confluence: {confluence_result}")

                if confluence_result.get('confluence_passed'):
                    signal_result = signal_service.generate_trade_signal(SYMBOL)
                    logger.info(f"[AutoTrade] Trade Signal: {signal_result}")
                    current_state = 'ARMED'
                    # Immediately attempt execution after arming (state machine will enforce all gates and single GPT)
                    exec_result = signal_service.execute_trade(SYMBOL)
                    logger.info(f"[AutoTrade] Execution Attempt: {exec_result}")
                    current_state = exec_result.get('session_state', current_state) if exec_result.get('success') else 'COOLDOWN'
            # If in trade or cooldown, just log and wait
            if current_state in ['ARMED', 'IN_TRADE', 'COOLDOWN']:
                if current_state == 'COOLDOWN' and signal_service.current_session:
                    reason = getattr(signal_service.current_session, 'cooldown_reason', None)
                    until = getattr(signal_service.current_session, 'cooldown_until', None)
                    logger.info(f"[AutoTrade] State: COOLDOWN - reason={reason}, until={until}")
                else:
                    logger.info(f"[AutoTrade] State: {current_state} - Monitoring...")
            time.sleep(AUTO_TRADING_INTERVAL)
        except Exception as e:
            logger.error(f"[AutoTrade] Error: {str(e)}", exc_info=True)
            time.sleep(5)

# Start auto mode in a background thread when module is imported
if ENABLE_AUTO_TRADING:
    auto_thread = threading.Thread(target=auto_trade_main_loop, daemon=True)
    auto_thread.start()
    logger.info("[AutoTrade] Auto mode is running in background thread.")
