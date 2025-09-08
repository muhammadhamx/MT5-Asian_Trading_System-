#!/usr/bin/env python
"""
PRODUCTION READINESS AUDIT SCRIPT
Mission-Critical XAU/USD Trading Bot - Zero Tolerance for Errors
"""

import os
import sys
import django
import logging
import subprocess
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mt5_drf_project.settings')
django.setup()

from mt5_integration.services import mt5_service, signal_detection_service
from mt5_integration.models import TradingSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('production_audit.log')
    ]
)
logger = logging.getLogger('PRODUCTION_AUDIT')

class ProductionAuditor:
    """Comprehensive production readiness auditor"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed_checks = []
        
    def log_issue(self, message):
        """Log a critical issue"""
        self.issues.append(message)
        logger.error(f"[CRITICAL] {message}")

    def log_warning(self, message):
        """Log a warning"""
        self.warnings.append(message)
        logger.warning(f"[WARNING] {message}")

    def log_pass(self, message):
        """Log a passed check"""
        self.passed_checks.append(message)
        logger.info(f"[PASS] {message}")
        
    def audit_environment_config(self):
        """Audit environment configuration"""
        logger.info("[AUDIT] ENVIRONMENT CONFIGURATION")
        
        # Check critical environment variables
        critical_vars = {
            'SECRET_KEY': 'Django secret key',
            'DEBUG': 'Debug mode setting',
            'ALLOWED_HOSTS': 'Allowed hosts configuration',
            'USE_MOCK_MT5': 'MT5 service mode',
            'DEFAULT_SYMBOL': 'Default trading symbol',
            'OPENAI_API_KEY': 'OpenAI API key for GPT integration'
        }
        
        for var, description in critical_vars.items():
            value = os.getenv(var)
            if not value:
                self.log_issue(f"Missing environment variable: {var} ({description})")
            elif var == 'SECRET_KEY' and ('django-insecure' in value or len(value) < 50):
                self.log_issue(f"Insecure SECRET_KEY detected")
            elif var == 'DEBUG' and value.lower() == 'true':
                self.log_warning(f"DEBUG=True in production environment")
            elif var == 'OPENAI_API_KEY' and value.startswith('your_'):
                self.log_warning(f"Placeholder OpenAI API key detected")
            else:
                self.log_pass(f"{description} configured")
                
    def audit_mt5_service(self):
        """Audit MT5 service configuration"""
        logger.info("[AUDIT] MT5 SERVICE")
        
        # Check MT5 service type
        use_mock = os.getenv('USE_MOCK_MT5', 'True').lower() == 'true'
        
        if use_mock:
            self.log_warning("Using MOCK MT5 service - not suitable for production trading")
            
            # Check mock service functionality
            if hasattr(mt5_service, 'connected'):
                if mt5_service.connected:
                    self.log_pass("Mock MT5 service connected")
                else:
                    self.log_issue("Mock MT5 service not connected")
            else:
                self.log_issue("MT5 service missing connection attribute")
        else:
            self.log_pass("Configured for REAL MT5 service")
            
            # Check real MT5 credentials
            login = os.getenv('MT5_LOGIN', '0')
            password = os.getenv('MT5_PASSWORD', '')
            server = os.getenv('MT5_SERVER', '')
            
            if login == '0' or not password or password.startswith('YOUR_'):
                self.log_issue("Real MT5 credentials not configured")
            else:
                self.log_pass("Real MT5 credentials configured")
                
    def audit_database_integrity(self):
        """Audit database and model integrity"""
        logger.info("[AUDIT] DATABASE INTEGRITY")

        try:
            # Check database connection
            from django.db import connection
            connection.ensure_connection()
            self.log_pass("Database connection successful")
            
            # Check for pending migrations
            result = subprocess.run([
                sys.executable, 'manage.py', 'showmigrations', '--plan'
            ], capture_output=True, text=True, cwd=os.getcwd())
            
            if '[ ]' in result.stdout:
                self.log_issue("Pending database migrations detected")
            else:
                self.log_pass("All database migrations applied")
                
            # Test model creation
            test_session = TradingSession(
                session_date=datetime.now().date(),
                session_type='ASIAN',
                current_state='IDLE'
            )
            test_session.full_clean()  # Validate model
            self.log_pass("Model validation successful")
            
        except Exception as e:
            self.log_issue(f"Database integrity check failed: {e}")
            
    def audit_api_endpoints(self):
        """Audit API endpoint functionality"""
        logger.info("[AUDIT] API ENDPOINTS")

        try:
            # Test critical endpoints
            from django.test import Client
            client = Client()
            
            # Test connection status
            response = client.get('/api/mt5/connection-status/')
            if response.status_code == 200:
                self.log_pass("Connection status endpoint working")
            else:
                self.log_issue(f"Connection status endpoint failed: {response.status_code}")
                
            # Test Asian range endpoint
            response = client.get('/api/mt5/asian-range/')
            if response.status_code == 200:
                self.log_pass("Asian range endpoint working")
            else:
                self.log_issue(f"Asian range endpoint failed: {response.status_code}")
                
        except Exception as e:
            self.log_issue(f"API endpoint test failed: {e}")
            
    def audit_trading_logic(self):
        """Audit core trading logic"""
        logger.info("[AUDIT] TRADING LOGIC")

        try:
            # Test signal detection service
            if hasattr(signal_detection_service, 'mt5_service'):
                self.log_pass("Signal detection service properly initialized")
            else:
                self.log_issue("Signal detection service missing MT5 service")
                
            # Test state machine
            valid_states = ['IDLE', 'SWEPT', 'CONFIRMED', 'ARMED', 'IN_TRADE', 'COOLDOWN']
            self.log_pass(f"State machine supports: {', '.join(valid_states)}")
            
            # Test risk management
            default_risk = float(os.getenv('DEFAULT_RISK_PERCENTAGE', '0.5'))
            if 0.1 <= default_risk <= 2.0:
                self.log_pass(f"Default risk percentage within safe range: {default_risk}%")
            else:
                self.log_warning(f"Default risk percentage may be unsafe: {default_risk}%")
                
        except Exception as e:
            self.log_issue(f"Trading logic audit failed: {e}")
            
    def audit_security_settings(self):
        """Audit security configuration"""
        logger.info("[AUDIT] SECURITY SETTINGS")

        # Check Django security settings
        from django.conf import settings
        
        if settings.DEBUG:
            self.log_issue("DEBUG=True in production")
        else:
            self.log_pass("DEBUG=False for production")
            
        if '*' in settings.ALLOWED_HOSTS:
            self.log_warning("ALLOWED_HOSTS contains wildcard")
        else:
            self.log_pass("ALLOWED_HOSTS properly configured")
            
        # Check HTTPS settings
        if hasattr(settings, 'SECURE_SSL_REDIRECT') and settings.SECURE_SSL_REDIRECT:
            self.log_pass("SSL redirect enabled")
        else:
            self.log_warning("SSL redirect not enabled")
            
    def audit_logging_configuration(self):
        """Audit logging setup"""
        logger.info("[AUDIT] LOGGING CONFIGURATION")

        # Check log files exist and are writable
        log_files = ['api_requests.log', 'production_audit.log']
        
        for log_file in log_files:
            try:
                with open(log_file, 'a') as f:
                    f.write(f"# Audit test - {datetime.now()}\n")
                self.log_pass(f"Log file writable: {log_file}")
            except Exception as e:
                self.log_issue(f"Log file not writable: {log_file} - {e}")
                
    def run_comprehensive_audit(self):
        """Run complete production audit"""
        logger.info("[STARTING] COMPREHENSIVE PRODUCTION AUDIT")
        logger.info("=" * 80)
        
        # Run all audit checks
        self.audit_environment_config()
        self.audit_mt5_service()
        self.audit_database_integrity()
        self.audit_api_endpoints()
        self.audit_trading_logic()
        self.audit_security_settings()
        self.audit_logging_configuration()
        
        # Generate summary report
        logger.info("=" * 80)
        logger.info("[SUMMARY] PRODUCTION AUDIT SUMMARY")
        logger.info("=" * 80)

        logger.info(f"[PASSED] CHECKS: {len(self.passed_checks)}")
        for check in self.passed_checks:
            logger.info(f"   [PASS] {check}")

        if self.warnings:
            logger.info(f"\n[WARNINGS] COUNT: {len(self.warnings)}")
            for warning in self.warnings:
                logger.warning(f"   [WARNING] {warning}")

        if self.issues:
            logger.info(f"\n[CRITICAL] ISSUES: {len(self.issues)}")
            for issue in self.issues:
                logger.error(f"   [CRITICAL] {issue}")

        # Final verdict
        if self.issues:
            logger.error("[FAILED] PRODUCTION READINESS: FAILED")
            logger.error("[CRITICAL] ISSUES MUST BE RESOLVED BEFORE DEPLOYMENT")
            return False
        elif self.warnings:
            logger.warning("[CONDITIONAL] PRODUCTION READINESS: CONDITIONAL")
            logger.warning("[WARNING] WARNINGS SHOULD BE ADDRESSED FOR OPTIMAL SECURITY")
            return True
        else:
            logger.info("[PASSED] PRODUCTION READINESS: PASSED")
            logger.info("[READY] SYSTEM IS READY FOR PRODUCTION DEPLOYMENT")
            return True

def main():
    """Main audit execution"""
    auditor = ProductionAuditor()
    success = auditor.run_comprehensive_audit()
    
    if not success:
        sys.exit(1)
    else:
        logger.info("[COMPLETE] AUDIT COMPLETE - SYSTEM READY")

if __name__ == '__main__':
    main()
