---
description: Repository Information Overview
alwaysApply: true
---

# MT5 Asian Liquidity Sweep Strategy Information

## Summary
This project implements the Asian Liquidity Sweep → Reversal trading strategy for MetaTrader 5 (MT5). It covers Phase 1 (Strategy Mapping & System Architecture) and Phase 2 (Core Detection & State Machine Logic) of the trading system. The project provides a Django-based REST API that integrates with MT5 to detect trading opportunities based on Asian session liquidity sweeps.

## Structure
- **mt5_drf_project/**: Django project configuration files
- **mt5_integration/**: Main application with trading logic and MT5 integration
  - **models/**: Database models for trading sessions, market data, etc.
  - **services/**: Core trading strategy services (Asian range, BOS/CHOCH, etc.)
  - **views/**: API endpoints for MT5 connection and trading operations
  - **tests/**: Unit tests for trading logic components
- **.env/.env.production**: Environment configuration files
- **manage.py**: Django management script

## Language & Runtime
**Language**: Python
**Version**: 3.8+ (as specified in README)
**Framework**: Django 5.2.5
**Build System**: pip (Python package installer)
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- Django 5.2.5: Web framework
- djangorestframework 3.16.1: REST API framework
- channels 4.3.1: WebSocket support
- MetaTrader5 5.0.5200: MT5 integration library
- numpy 2.3.2 & pandas 2.3.1: Data analysis
- openai 1.102.0: GPT integration for trading analysis
- python-dotenv 1.0.0: Environment variable management

**Development Dependencies**:
- Django test framework for unit testing

## Build & Installation
```bash
# Setup virtual environment
python -m venv env
.\env\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Run development server
python manage.py runserver
```

## Configuration
**Environment Variables**:
- MT5_LOGIN: MetaTrader 5 account login
- MT5_PASSWORD: MetaTrader 5 account password
- MT5_SERVER: MetaTrader 5 server name
- USE_MOCK_MT5: Set to "True" to use mock MT5 service for testing
- DEBUG: Enable/disable debug mode
- SECRET_KEY: Django secret key
- ALLOWED_HOSTS: Comma-separated list of allowed hosts

## Main Files
**Entry Points**:
- manage.py: Django management script
- mt5_drf_project/asgi.py: ASGI application entry point
- mt5_drf_project/wsgi.py: WSGI application entry point
- auto_trading_watcher.py: Automated trading script
- bot_monitor.py: Trading bot monitoring script

**Core Components**:
- mt5_integration/services/asian_range_service.py: Asian session range detection
- mt5_integration/services/bos_choch_service.py: Break of structure detection
- mt5_integration/services/mt5_service.py: MT5 integration service
- mt5_integration/services/signal_detection_service.py: Trading signal detection

## Testing
**Framework**: Django test framework
**Test Location**: mt5_integration/tests/
**Naming Convention**: test_*.py
**Test Files**:
- test_trading_session.py
- test_liquidity_sweep.py
- test_confluence_check.py
- test_implementation_completeness.py (root directory)

**Run Command**:
```bash
python manage.py test mt5_integration
```