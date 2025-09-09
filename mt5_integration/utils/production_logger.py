"""
Production-Grade Structured Logging Utility
Mission-Critical Trading Bot - Complete Decision Traceability
"""

import logging
import json
import traceback
import sys
import codecs
import os
import threading
from typing import Dict, Any, Optional
from django.utils import timezone

# JSON-per-day array writer
class _JsonDailyArrayWriter:
    def __init__(self, base_logs_dir: str):
        self.base_logs_dir = base_logs_dir
        os.makedirs(self.base_logs_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _file_path_for_today(self) -> str:
        date_str = timezone.now().date().isoformat()  # e.g., 2025-09-09
        return os.path.join(self.base_logs_dir, f"{date_str}.json")

    def append(self, obj: Dict[str, Any]):
        path = self._file_path_for_today()
        with self._lock:
            try:
                if not os.path.exists(path):
                    # Create new JSON array with first entry
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump([obj], f, ensure_ascii=False, indent=2)
                        f.write("\n")
                    return

                # Read, append, write back (pretty-printed)
                with open(path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    except Exception:
                        data = []
                data.append(obj)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write("\n")
            except Exception:
                # Fail-safe: ignore file logging errors to not break execution
                pass

# Derive logs directory at project root
# utils/production_logger.py -> mt5_integration/utils -> project root is two levels up
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_DAILY_LOGS_DIR = os.path.join(_PROJECT_ROOT, 'logs')
_daily_writer = _JsonDailyArrayWriter(_DAILY_LOGS_DIR)

class JsonDailyArrayHandler(logging.Handler):
    """Logging handler that appends records to a pretty-printed daily JSON array."""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                'timestamp': timezone.now().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'event': getattr(record, 'event', None),
                'session_id': getattr(record, 'session_id', None),
                'reason': getattr(record, 'reason', None),
                'message': record.getMessage(),
                'context': getattr(record, 'context', None),
            }
            old_state = getattr(record, 'old_state', None)
            new_state = getattr(record, 'new_state', None)
            if old_state is not None or new_state is not None:
                entry['state_transition'] = {
                    'old_state': old_state,
                    'new_state': new_state,
                }
            _daily_writer.append(entry)
        except Exception:
            # Never break app flow due to logging I/O issues
            pass

class ProductionLogger:
    """
    Production-grade structured logger for trading decisions and system events
    Provides complete traceability for all trading decisions and system operations
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Ensure handlers are not duplicated
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Configure console handler for UTF-8 output
            console_handler.setStream(sys.stdout)
            
            # Custom formatter for handling emojis
            class EmojiFormatter(logging.Formatter):
                def format(self, record):
                    try:
                        record.msg = str(record.msg)
                    except UnicodeEncodeError:
                        record.msg = record.msg.encode('utf-8').decode('utf-8')
                    return super().format(record)
            
            # File handler for legacy human-readable log
            file_handler = logging.FileHandler('trading_decisions.log')
            file_handler.setLevel(logging.INFO)
            
            # Formatter for structured logging
            console_formatter = EmojiFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            
            console_handler.setFormatter(console_formatter)
            file_handler.setFormatter(file_formatter)
            
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
    
    def _build_daily_json_entry(self, level: str, event_type: str, data: Dict[str, Any], message: Optional[str]):
        # Flatten common fields while preserving full context
        entry = {
            'timestamp': timezone.now().isoformat(),
            'level': level,
            'event': event_type,             # primary event name
            'event_type': event_type,        # keep legacy key for compatibility
            'message': message,
            'session_id': data.get('session_id'),
            'reason': data.get('reason'),
            'context': data,                 # full original payload
        }
        # State transition shape if available
        old_state = data.get('old_state')
        new_state = data.get('new_state')
        if old_state is not None or new_state is not None:
            entry['state_transition'] = {
                'old_state': old_state,
                'new_state': new_state,
            }
        return entry

    def log_structured(self, level: str, event_type: str, data: Dict[str, Any], 
                      message: str = None):
        """Log structured data with complete context and write JSON to daily file"""
        # Build display message for console/file handlers
        display_entry = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'level': level,
            'data': data
        }
        if message:
            display_entry['message'] = message
        log_message = json.dumps(display_entry, default=str, indent=2)

        # Emit to standard handlers
        level_up = level.upper()
        if level_up == 'ERROR':
            self.logger.error(log_message)
        elif level_up == 'WARNING':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

        # Append to daily JSON array (pretty-printed)
        try:
            json_entry = self._build_daily_json_entry(level_up, event_type, data, message)
            _daily_writer.append(json_entry)
        except Exception:
            # Never fail due to logging I/O issues
            pass
    
    def log_state_transition(self, session_id: str, old_state: str, new_state: str, 
                           reason: str, context: Dict[str, Any] = None):
        """Log state machine transitions with full context. Ensures a meaningful reason is present."""
        ctx = context or {}
        auto_reason = (reason or '').strip()
        if not auto_reason:
            # Try to derive a useful reason based on states and context
            if old_state == new_state:
                # Maintained state
                if new_state == 'SWEPT':
                    inner = ctx if isinstance(ctx, dict) else {}
                    # Some callers put details inside ctx['context']
                    if 'context' in inner and isinstance(inner['context'], dict):
                        inner = {**inner, **inner.get('context', {})}
                    direction = inner.get('sweep_direction') or 'UNKNOWN'
                    sweep_price = inner.get('sweep_price')
                    threshold = inner.get('threshold_pips')
                    side_word = 'above' if str(direction).upper() == 'UP' else 'below' if str(direction).upper() == 'DOWN' else 'beyond'
                    price_txt = f" @ {sweep_price}" if sweep_price is not None else ''
                    thr_txt = f" (threshold {threshold} pips)" if threshold is not None else ''
                    auto_reason = f"Sweep persists: price remains {side_word}{thr_txt}{price_txt}"
                else:
                    auto_reason = f"State maintained: {new_state}"
            elif new_state == 'IDLE':
                auto_reason = "Reset to IDLE: conditions cleared or confirmation timeout"
            else:
                auto_reason = f"Transitioned to {new_state}"
        
        self.log_structured('INFO', 'STATE_TRANSITION', {
            'session_id': session_id,
            'old_state': old_state,
            'new_state': new_state,
            'reason': auto_reason,
            'context': ctx
        }, f"State transition: {old_state} -> {new_state}")
    
    def log_trading_decision(self, decision_type: str, decision: bool, 
                           reason: str, context: Dict[str, Any]):
        """Log trading decisions with complete reasoning"""
        self.log_structured('INFO', 'TRADING_DECISION', {
            'decision_type': decision_type,
            'decision': 'EXECUTE' if decision else 'SKIP',
            'reason': reason,
            'context': context
        }, f"Trading decision: {decision_type} = {'EXECUTE' if decision else 'SKIP'}")
    
    def log_gpt_call(self, prompt: str, response: Dict[str, Any], 
                    tokens_used: int = None, cost: float = None):
        """Log GPT API calls with usage metrics"""
        self.log_structured('INFO', 'GPT_CALL', {
            'prompt_preview': prompt[:100] + '...' if len(prompt) > 100 else prompt,
            'response': response,
            'tokens_used': tokens_used,
            'estimated_cost': cost,
            'model': response.get('model', 'unknown')
        }, "GPT API call executed")
    
    def log_risk_check(self, check_type: str, passed: bool, 
                      current_value: float, limit: float, context: Dict[str, Any]):
        """Log risk management checks"""
        self.log_structured('INFO', 'RISK_CHECK', {
            'check_type': check_type,
            'passed': passed,
            'current_value': current_value,
            'limit': limit,
            'context': context
        }, f"Risk check: {check_type} = {'PASS' if passed else 'FAIL'}")
    
    def log_market_data(self, symbol: str, data_type: str, data: Dict[str, Any]):
        """Log market data events"""
        self.log_structured('INFO', 'MARKET_DATA', {
            'symbol': symbol,
            'data_type': data_type,
            'data': data
        }, f"Market data: {symbol} {data_type}")
    
    def log_trade_execution(self, action: str, symbol: str, volume: float,
                          price: float, order_type: str, result: Dict[str, Any]):
        """Log trade execution attempts and results"""
        self.log_structured('INFO', 'TRADE_EXECUTION', {
            'action': action,
            'symbol': symbol,
            'volume': volume,
            'price': price,
            'order_type': order_type,
            'result': result
        }, f"Trade execution: {action} {volume} {symbol} @ {price}")
    
    def log_error(self, error_type: str, error_message: str, 
                 context: Dict[str, Any] = None, exception: Exception = None):
        """Log errors with full context and stack trace"""
        error_data = {
            'error_type': error_type,
            'error_message': error_message,
            'context': context or {}
        }
        
        if exception:
            error_data['exception_type'] = type(exception).__name__
            error_data['stack_trace'] = traceback.format_exc()
            
        self.log_structured('ERROR', 'SYSTEM_ERROR', error_data, 
                          f"Error: {error_type}")
    
    def log_performance_metric(self, metric_name: str, value: float, 
                             unit: str, context: Dict[str, Any] = None):
        """Log performance metrics"""
        self.log_structured('INFO', 'PERFORMANCE_METRIC', {
            'metric_name': metric_name,
            'value': value,
            'unit': unit,
            'context': context or {}
        }, f"Performance: {metric_name} = {value} {unit}")
    
    def log_confluence_check(self, checks: Dict[str, Any], overall_result: bool):
        """Log confluence check results with all factors"""
        self.log_structured('INFO', 'CONFLUENCE_CHECK', {
            'checks': checks,
            'overall_result': overall_result,
            'passed_checks': [k for k, v in checks.items() if v.get('passed', False)],
            'failed_checks': [k for k, v in checks.items() if not v.get('passed', True)]
        }, f"Confluence check: {'PASS' if overall_result else 'FAIL'}")
    
    def log_session_summary(self, session_data: Dict[str, Any]):
        """Log session summary with complete statistics"""
        self.log_structured('INFO', 'SESSION_SUMMARY', session_data, 
                          "Trading session summary")

# Global logger instances
trading_logger = ProductionLogger('TRADING')
system_logger = ProductionLogger('SYSTEM')
api_logger = ProductionLogger('API')
gpt_logger = ProductionLogger('GPT')
risk_logger = ProductionLogger('RISK')

def get_logger(name: str) -> ProductionLogger:
    """Get a production logger instance"""
    return ProductionLogger(name)
