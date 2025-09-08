"""
Production-Grade Error Handling Utility
Mission-Critical Trading Bot - Zero Silent Failures
"""

import logging
import traceback
import functools
import time
from datetime import datetime, timedelta
from typing import Callable, Any, Dict
from django.http import JsonResponse
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from .production_logger import system_logger

class ProductionErrorHandler:
    """
    Production-grade error handler that ensures no silent failures.
    All exceptions are logged with full stack traces and context.
    Includes retry mechanisms and state recovery.
    """
    
    def __init__(self):
        self.error_counts = {}
        self.last_errors = {}
        self.cooldown_until = {}
        
    def handle_trading_error(self, func: Callable) -> Callable:
        """Decorator for trading functions with advanced error handling"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Check if in cooldown
            if self.is_in_cooldown(func_name):
                return {
                    'success': False,
                    'error': f'Function {func_name} is in cooldown due to repeated errors',
                    'cooldown_until': self.cooldown_until[func_name].isoformat()
                }
            
            try:
                with transaction.atomic():
                    result = func(*args, **kwargs)
                self.reset_error_count(func_name)
                return result
                
            except Exception as e:
                error_context = {
                    'function': func_name,
                    'args': str(args)[:500],
                    'kwargs': str(kwargs)[:500],
                    'error_count': self.get_error_count(func_name)
                }
                
                # Update error tracking
                self.increment_error_count(func_name)
                
                # Log error with full context
                system_logger.log_error(
                    error_type='TRADING_ERROR',
                    error_message=str(e),
                    context=error_context,
                    exception=e
                )
                
                # Check if should enter cooldown
                if self.should_enter_cooldown(func_name):
                    self.set_cooldown(func_name)
                    system_logger.log_error(
                        error_type='COOLDOWN_TRIGGERED',
                        error_message=f'Function {func_name} entered cooldown',
                        context=error_context
                    )
                
                # Return safe error response
                return {
                    'success': False,
                    'error': f'Trading error in {func_name}: {str(e)}',
                    'error_type': 'TRADING_ERROR',
                    'function': func_name,
                    'error_count': self.get_error_count(func_name)
                }
        return wrapper
        
    def get_error_count(self, func_name: str) -> int:
        """Get current error count for a function"""
        return self.error_counts.get(func_name, 0)
        
    def increment_error_count(self, func_name: str):
        """Increment error count for a function"""
        now = datetime.now()
        self.last_errors[func_name] = now
        self.error_counts[func_name] = self.error_counts.get(func_name, 0) + 1
        
    def reset_error_count(self, func_name: str):
        """Reset error count for a function on successful execution"""
        self.error_counts[func_name] = 0
        self.last_errors.pop(func_name, None)
        self.cooldown_until.pop(func_name, None)
        
    def should_enter_cooldown(self, func_name: str) -> bool:
        """Determine if function should enter cooldown based on error pattern"""
        error_count = self.get_error_count(func_name)
        if error_count >= 5:  # 5 consecutive errors
            return True
            
        last_error = self.last_errors.get(func_name)
        if last_error and error_count >= 3:  # 3 errors in 5 minutes
            five_min_ago = datetime.now() - timedelta(minutes=5)
            return last_error >= five_min_ago
            
        return False
        
    def set_cooldown(self, func_name: str, duration: int = 300):
        """Put function in cooldown for specified duration (seconds)"""
        self.cooldown_until[func_name] = datetime.now() + timedelta(seconds=duration)
        
    def is_in_cooldown(self, func_name: str) -> bool:
        """Check if function is in cooldown period"""
        cooldown_time = self.cooldown_until.get(func_name)
        if cooldown_time and datetime.now() < cooldown_time:
            return True
        return False
    
    @staticmethod
    def handle_api_error(func: Callable) -> Callable:
        """Decorator for API endpoints - ensures proper error responses"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error with full context
                system_logger.log_error(
                    error_type='API_ERROR',
                    error_message=str(e),
                    context={
                        'endpoint': func.__name__,
                        'args': str(args)[:500],
                        'kwargs': str(kwargs)[:500]
                    },
                    exception=e
                )
                
                # Return proper HTTP error response
                return Response({
                    'status': 'error',
                    'message': f'API error: {str(e)}',
                    'error_type': 'API_ERROR',
                    'endpoint': func.__name__
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return wrapper
        
    @staticmethod
    def handle_mt5_error(func: Callable) -> Callable:
        """Decorator for MT5 functions with retry logic"""
        MAX_RETRIES = 3
        RETRY_DELAY = 5  # seconds
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(MAX_RETRIES):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Log retry attempt
                    system_logger.log_error(
                        error_type='MT5_ERROR',
                        error_message=f'Attempt {attempt + 1}/{MAX_RETRIES}: {str(e)}',
                        context={
                            'function': func.__name__,
                            'args': str(args)[:500],
                            'kwargs': str(kwargs)[:500],
                            'attempt': attempt + 1
                        },
                        exception=e
                    )
                    
                    if attempt == MAX_RETRIES - 1:
                        # Last attempt failed
                        return {
                            'success': False,
                            'error': f'MT5 error in {func.__name__} after {MAX_RETRIES} attempts: {str(e)}',
                            'error_type': 'MT5_ERROR',
                            'connected': False
                        }
                    
                    time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
            
            return {'success': False, 'error': 'Unexpected error in MT5 retry logic'}
        return wrapper
    
    @staticmethod
    def handle_state_transition(old_state: str, new_state: str, allowed_transitions: Dict[str, list]) -> bool:
        """
        Validate and handle trading state transitions
        Returns True if transition is valid, False otherwise
        """
        if old_state not in allowed_transitions:
            system_logger.log_error(
                error_type='STATE_ERROR',
                error_message=f'Invalid current state: {old_state}',
                context={'old_state': old_state, 'new_state': new_state}
            )
            return False
            
        if new_state not in allowed_transitions[old_state]:
            system_logger.log_error(
                error_type='STATE_ERROR',
                error_message=f'Invalid transition: {old_state} -> {new_state}',
                context={'old_state': old_state, 'new_state': new_state}
            )
            return False
            
        return True
    
    @staticmethod
    def handle_gpt_error(func: Callable) -> Callable:
        """Decorator for GPT functions with graceful fallback"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error
                system_logger.log_error(
                    error_type='GPT_ERROR',
                    error_message=str(e),
                    context={
                        'function': func.__name__,
                        'args': str(args)[:500],
                        'kwargs': str(kwargs)[:500]
                    },
                    exception=e
                )
                
                # Return fail-safe response - default to execute trades
                return {
                    'success': False,
                    'execute': True,  # Fail-safe: execute trade if GPT fails
                    'reason': f'GPT service unavailable: {str(e)}',
                    'error_type': 'GPT_ERROR',
                    'gpt_used': False
                }
        return wrapper
    
    @staticmethod
    def recover_state(func: Callable) -> Callable:
        """
        Decorator that attempts to recover state after failures.
        Uses transaction savepoints and state verification.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from mt5_integration.models import TradingSession
            savepoint_name = None
            
            try:
                # Create transaction savepoint
                with transaction.atomic():
                    savepoint_name = transaction.savepoint()
                    
                    # Get current state before execution
                    current_session = None
                    if hasattr(args[0], 'current_session'):
                        current_session = args[0].current_session
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Verify state consistency
                    if current_session:
                        updated_session = TradingSession.objects.get(id=current_session.id)
                        if not ProductionErrorHandler.verify_state_consistency(current_session, updated_session):
                            # State inconsistency detected
                            transaction.savepoint_rollback(savepoint_name)
                            raise StateError("State consistency check failed")
                    
                    # Commit transaction
                    transaction.savepoint_commit(savepoint_name)
                    return result
                    
            except Exception as e:
                # Handle failure and attempt recovery
                if savepoint_name:
                    transaction.savepoint_rollback(savepoint_name)
                
                system_logger.log_error(
                    error_type='STATE_ERROR',
                    error_message=f'State recovery triggered: {str(e)}',
                    context={'function': func.__name__},
                    exception=e
                )
                
                # Attempt state recovery
                if current_session:
                    try:
                        recovered_session = ProductionErrorHandler.recover_session_state(current_session)
                        return {
                            'success': False,
                            'error': f'Operation failed but state recovered: {str(e)}',
                            'recovered_state': recovered_session.current_state
                        }
                    except Exception as recovery_error:
                        system_logger.log_error(
                            error_type='RECOVERY_ERROR',
                            error_message=f'State recovery failed: {str(recovery_error)}',
                            context={'original_error': str(e)},
                            exception=recovery_error
                        )
                
                raise
        return wrapper
    
    @staticmethod
    def verify_state_consistency(old_session, new_session) -> bool:
        """
        Verify trading session state consistency
        Returns True if state transition is valid
        """
        # Verify state machine rules
        allowed_transitions = {
            'IDLE': ['SWEPT', 'COOLDOWN'],
            'SWEPT': ['CONFIRMED', 'IDLE', 'COOLDOWN'],
            'CONFIRMED': ['ARMED', 'IDLE', 'COOLDOWN'],
            'ARMED': ['IN_TRADE', 'IDLE', 'COOLDOWN'],
            'IN_TRADE': ['IDLE', 'COOLDOWN'],
            'COOLDOWN': ['IDLE']
        }
        
        if old_session.current_state != new_session.current_state:
            if not ProductionErrorHandler.handle_state_transition(
                old_session.current_state,
                new_session.current_state,
                allowed_transitions
            ):
                return False
        
        # Verify risk limits
        if new_session.current_daily_loss > new_session.daily_loss_limit:
            return False
            
        return True
    
    @staticmethod
    def recover_session_state(session):
        """
        Attempt to recover session state from database and MT5
        """
        from mt5_integration.models import TradingSession, TradeSignal
        
        try:
            # Get latest trade signal
            latest_signal = TradeSignal.objects.filter(
                session=session
            ).order_by('-created_at').first()
            
            # Analyze current state
            if latest_signal:
                if latest_signal.exit_time:
                    # Trade was closed
                    session.current_state = 'IDLE'
                elif latest_signal.entry_time:
                    # Trade is active
                    session.current_state = 'IN_TRADE'
                else:
                    # Signal generated but not executed
                    session.current_state = 'ARMED'
            else:
                # No signals - reset to IDLE
                session.current_state = 'IDLE'
            
            session.save()
            return session
            
        except Exception as e:
            system_logger.log_error(
                error_type='RECOVERY_ERROR',
                error_message=f'Failed to recover session state: {str(e)}',
                context={'session_id': session.id},
                exception=e
            )
            raise
    
    @staticmethod
    def log_and_continue(error_type: str, context: Dict[str, Any] = None):
        """Log error and continue execution - for non-critical errors"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Log the error but continue
                    system_logger.log_error(
                        error_type=error_type,
                        error_message=str(e),
                        context={
                            'function': func.__name__,
                            'context': context or {},
                            'args': str(args)[:500],
                            'kwargs': str(kwargs)[:500]
                        },
                        exception=e
                    )
                    
                    # Return None or empty result to continue
                    return None
            return wrapper
        return decorator

class StateError(Exception):
    """Exception raised for state consistency errors"""
    pass

# Global error handler instance
error_handler = ProductionErrorHandler()

# Convenience decorators
trading_error = error_handler.handle_trading_error
api_error = error_handler.handle_api_error
mt5_error = error_handler.handle_mt5_error
gpt_error = error_handler.handle_gpt_error
recover_state = error_handler.recover_state
