"""
Production-Grade Structured Logging Utility
Mission-Critical Trading Bot - Complete Decision Traceability
"""

import logging
import json
import traceback
import sys
import codecs
from datetime import datetime
from typing import Dict, Any, Optional
from django.utils import timezone

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
            
            # File handler for structured logs
            file_handler = logging.FileHandler('trading_decisions.log')
            file_handler.setLevel(logging.INFO)
            
            # Formatter for structured logging
            console_formatter = EmojiFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            
            console_handler.setFormatter(console_formatter)
            file_handler.setFormatter(file_formatter)
            
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
    
    def log_structured(self, level: str, event_type: str, data: Dict[str, Any], 
                      message: str = None):
        """Log structured data with complete context"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'level': level,
            'data': data
        }
        
        if message:
            log_entry['message'] = message
            
        log_message = json.dumps(log_entry, default=str, indent=2)
        
        if level.upper() == 'ERROR':
            self.logger.error(log_message)
        elif level.upper() == 'WARNING':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_state_transition(self, session_id: str, old_state: str, new_state: str, 
                           reason: str, context: Dict[str, Any] = None):
        """Log state machine transitions with full context"""
        self.log_structured('INFO', 'STATE_TRANSITION', {
            'session_id': session_id,
            'old_state': old_state,
            'new_state': new_state,
            'reason': reason,
            'context': context or {}
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
