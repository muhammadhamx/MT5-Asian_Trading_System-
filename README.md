# MT5 Asian Liquidity Sweep Strategy - Phase 1 & 2

This project implements the Asian Liquidity Sweep → Reversal trading strategy for MT5, covering Phase 1 (Strategy Mapping & System Architecture) and Phase 2 (Core Detection & State Machine Logic).

## Project Scope

### Phase 1 - Strategy Mapping & System Architecture ✅
- Precise pseudo-code for Asian Liquidity Sweep → Reversal rules
- Session timing, sweep thresholds, BOS/CHOCH confirmation, and confluence checks
- Architecture: MT5 ↔ Python State Machine ↔ Detection Layer
- Backtesting methodology and historical data requirements for Asian–London–NY sessions

### Phase 2 - Core Detection & State Machine Logic ✅
- Asian Range Detection module (00:00–06:00 UTC highs, lows, midpoint, range validation)
- Sweep Detection (threshold pips breach post-06:00 UTC)
- Reversal Confirmation logic (M5 close back inside, displacement test, micro BOS/CHOCH on M1)
- State machine: IDLE → SWEPT → CONFIRMED → ARMED → IN_TRADE → COOLDOWN
- Unit testing with synthetic MT5 data under different volatility conditions

## Features Included

### Core Components
- Asian Range Detection: Calculate Asian session range (00:00-06:00 UTC)
- Sweep Detection: Detect liquidity sweeps beyond Asian range
- Reversal Confirmation**: Confirm reversals with displacement and BOS/CHOCH
- State Machine: Complete trading lifecycle state management
- MT5 Integration: Real and mock MT5 service for development/testing

### API Endpoints
- Connection management (`/connect/`, `/disconnect/`, `/connection-status/`)
- Market data (`/symbols/`, `/rates/`, `/current-price/`)
- Asian range analysis (`/asian-range/`, `/test-asian-range/`)
- Signal detection (`/signal/detect-sweep/`, `/signal/confirm-reversal/`)
- Session management (`/signal/initialize-session/`, `/signal/session-status/`)

## Setup Instructions

### Prerequisites
- Python 3.8+
- MetaTrader 5 terminal (for live trading)
- Windows OS (required for MT5 integration)

### Installation
1. **Setup virtual environment:**
```bash
python -m venv env
.\env\Scripts\Activate.ps1
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Setup database:**
```bash
python manage.py migrate
```

4. **Configure MT5 connection (optional for testing):**
   - Set environment variables for live MT5:
     - `MT5_LOGIN`: Your MT5 account login
     - `MT5_PASSWORD`: Your MT5 account password
     - `MT5_SERVER`: Your MT5 server name
   - Or use mock service by setting `USE_MOCK_MT5=True`

5. **Run the development server:**
```bash
python manage.py runserver
```

## Usage

### Testing with Mock Data
The system includes a mock MT5 service for development and testing:
- Set `USE_MOCK_MT5=True` in environment variables
- Mock service provides realistic Asian session data
- Test all endpoints without requiring live MT5 connection

### API Testing
1. Initialize a trading session
   ```
   POST /signal/initialize-session/
   {"symbol": "XAUUSD"}
   ```

2. **Get Asian range data:**
   ```
   GET /asian-range/?symbol=XAUUSD
   ```

3. **Detect sweep:**
   ```
   POST /signal/detect-sweep/
   {"symbol": "XAUUSD"}
   ```

4. **Confirm reversal:**
   ```
   POST /signal/confirm-reversal/
   {"symbol": "XAUUSD"}
   ```

5. **Run complete analysis:**
   ```
   POST /signal/run-analysis/
   {"symbol": "XAUUSD"}
   ```

## Architecture

```
MT5 Terminal ↔ Python Django API ↔ State Machine ↔ Detection Services
                     ↓
              Database (Session State)
                     ↓
              REST API Endpoints
```

## State Machine Flow

```
IDLE → SWEPT → CONFIRMED → ARMED → IN_TRADE → COOLDOWN
  ↑                                              ↓
  ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

## Testing

Run the test suite:
```bash
python manage.py test mt5_integration
```

