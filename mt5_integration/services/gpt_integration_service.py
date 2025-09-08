"""
GPT Integration Service - PRODUCTION READY Implementation
Client Requirement: Minimal GPT usage, only called at specific event edges
"""
import os
import json
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from ..utils.error_handler import gpt_error
from ..utils.production_logger import gpt_logger

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

# Import OpenAI for production use
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. Install with: pip install openai")

class GPTIntegrationService:
    """PRODUCTION READY GPT service for minimal trade decisions at event edges"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_GPT_INTEGRATION', 'False').lower() == 'true'
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.model = os.getenv('GPT_MODEL', 'gpt-4o-mini')  # Cost-effective model
        self.cooldown_seconds = int(os.getenv('GPT_COOLDOWN_SECONDS', '300'))  # 5 min cooldown
        self.last_call_time = {}
        self.client = None
        
        # Initialize OpenAI client for production
        if self.enabled:
            if not self.api_key:
                logger.error("GPT integration enabled but no OPENAI_API_KEY provided")
                self.enabled = False
            elif not OPENAI_AVAILABLE:
                logger.error("GPT integration enabled but openai package not installed")
                self.enabled = False
            else:
                try:
                    self.client = openai.OpenAI(api_key=self.api_key)
                    logger.info(f"OpenAI client initialized with model: {self.model}")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    self.enabled = False
    
    @gpt_error
    def get_risk_adjustment(self, session, market_conditions: Dict) -> float:
        """GPT call for risk adjustment based on market conditions"""
        if not self.enabled:
            return 1.0  # No adjustment if GPT disabled
        
        if not self._check_cooldown('risk_adjustment'):
            return 1.0  # No adjustment if in cooldown
        
        # Extract essential data only
        asian_grade = session.asian_range_grade
        high_volatility = market_conditions.get('high_volatility', False)
        major_news = market_conditions.get('major_news', False)
        
        # Create minimal prompt
        prompt = f"""
        XAU/USD Risk Adjustment:
        Asian Grade: {asian_grade}
        High Volatility: {high_volatility}
        Major News: {major_news}
        
        Recommend risk adjustment multiplier (0.5-1.5):
        Respond with only a number between 0.5 and 1.5
        """
        
        # Make minimal GPT call
        response = self._call_gpt_minimal(prompt)
        
        # Log the GPT response for debugging
        logger.info(f"GPT RISK ADJUSTMENT RESPONSE: {response}")
        
        if response and response.get('success'):
            gpt_response = response.get('gpt_response', '')
            try:
                adjustment = float(gpt_response)
                # Ensure adjustment is within valid range
                adjustment = max(0.5, min(1.5, adjustment))
                
                logger.info(f"GPT Risk Adjustment: {adjustment} - {session.symbol}")
                logger.info(f"GPT Raw Response: '{gpt_response}'")
                
                return adjustment
            except ValueError:
                logger.warning(f"Invalid GPT risk adjustment response: {gpt_response}")
                return 1.0
        else:
            # GPT failed - use no adjustment
            logger.warning(f"GPT Risk Adjustment failed: {response}")
            return 1.0
    
    @gpt_error
    def evaluate_sweep(self, session, sweep_data: Dict, market_data: Dict) -> Dict:
        """GPT call at SWEPT state - evaluate if sweep is valid for reversal"""
        if not self.enabled:
            return {'valid': True, 'reason': 'GPT disabled', 'confidence': 0.8}
        
        if not self._check_cooldown('sweep_evaluation'):
            return {'valid': True, 'reason': 'GPT cooldown', 'confidence': 0.7}
        
        # Extract essential data only
        asian_range = float(session.asian_range_size)
        sweep_direction = sweep_data.get('direction')
        threshold_pips = float(sweep_data.get('threshold', 0))
        atr_h1 = market_data.get('atr_h1', 0)
        spread = market_data.get('spread', 0)
        adx = market_data.get('adx', 0)
        
        # Create minimal prompt
        prompt = f"""
        XAU/USD Sweep Evaluation:
        Asian Range: {asian_range} pips
        Sweep: {sweep_direction} beyond threshold ({threshold_pips} pips)
        ATR(H1): {atr_h1:.2f} pips
        Spread: {spread:.1f} pips
        ADX: {adx:.1f}
        
        Is this a valid liquidity sweep for reversal? Respond with only: true or false
        """
        
        # Make minimal GPT call
        response = self._call_gpt_minimal(prompt)
        
        # Log the GPT response for debugging
        logger.info(f"GPT SWEEP EVALUATION RESPONSE: {response}")
        
        if response and response.get('success'):
            gpt_response = response.get('gpt_response', '')
            valid = gpt_response.lower() == 'true'
            confidence = 0.9 if valid else 0.7
            
            logger.info(f"GPT Sweep Evaluation: {'VALID' if valid else 'INVALID'} - {session.symbol}")
            logger.info(f"GPT Raw Response: '{gpt_response}'")
            
            return {
                'valid': valid,
                'reason': 'GPT evaluation',
                'confidence': confidence,
                'gpt_used': True,
                'gpt_response': gpt_response,
                'tokens_used': response.get('tokens_used', 0)
            }
        else:
            # GPT failed - default to valid (conservative)
            logger.warning(f"GPT Sweep Evaluation failed: {response}")
            return {'valid': True, 'reason': 'GPT failed - default valid', 'confidence': 0.6}
    
    @gpt_error
    def refine_entry_levels(self, session, sweep_data: Dict, confirmation_data: Dict) -> Dict:
        """GPT call at CONFIRMED state - refine entry, SL, TP levels"""
        if not self.enabled:
            return {
                'entry_method': 'LIMIT',
                'entry_zone': 'CONFIRM_BODY',
                'sl_buffer_pips': 3,
                'tp1_method': 'MIDPOINT',
                'tp2_method': 'OPPOSITE_EXTREME',
                'reason': 'GPT disabled'
            }
        
        if not self._check_cooldown('entry_refinement'):
            return {
                'entry_method': 'LIMIT',
                'entry_zone': 'CONFIRM_BODY',
                'sl_buffer_pips': 3,
                'tp1_method': 'MIDPOINT',
                'tp2_method': 'OPPOSITE_EXTREME',
                'reason': 'GPT cooldown'
            }
        
        # Extract essential data only
        asian_grade = session.asian_range_grade
        sweep_direction = sweep_data.get('direction')
        displacement_ratio = confirmation_data.get('displacement_ratio', 0)
        atr_m5 = confirmation_data.get('atr_m5', 0)
        
        # Create minimal prompt
        prompt = f"""
        XAU/USD Entry Refinement:
        Asian Grade: {asian_grade}
        Sweep: {sweep_direction}
        Displacement Ratio: {displacement_ratio:.2f}
        ATR(M5): {atr_m5:.2f} pips
        
        Recommend:
        1. Entry method: LIMIT or MARKET
        2. SL buffer in pips (2-5)
        3. TP1 method: MIDPOINT or FIXED_R
        4. TP2 method: OPPOSITE_EXTREME or FIXED_R
        
        Respond with JSON only:
        {{"entry_method": "LIMIT", "sl_buffer_pips": 3, "tp1_method": "MIDPOINT", "tp2_method": "OPPOSITE_EXTREME"}}
        """
        
        # Make minimal GPT call
        response = self._call_gpt_minimal(prompt, json_response=True)
        
        # Log the GPT response for debugging
        logger.info(f"GPT ENTRY REFINEMENT RESPONSE: {response}")
        
        if response and response.get('success'):
            result = response.get('result', {})
            gpt_response = response.get('gpt_response', '')
            
            logger.info(f"GPT Entry Refinement: {result} - {session.symbol}")
            logger.info(f"GPT Raw Response: '{gpt_response}'")
            
            return {
                'entry_method': result.get('entry_method', 'LIMIT'),
                'entry_zone': 'CONFIRM_BODY',
                'sl_buffer_pips': max(2, min(5, int(result.get('sl_buffer_pips', 3)))),
                'tp1_method': result.get('tp1_method', 'MIDPOINT'),
                'tp2_method': result.get('tp2_method', 'OPPOSITE_EXTREME'),
                'reason': 'GPT refinement',
                'gpt_used': True,
                'gpt_response': gpt_response,
                'tokens_used': response.get('tokens_used', 0)
            }
        else:
            # GPT failed - use defaults
            logger.warning(f"GPT Entry Refinement failed: {response}")
            return {
                'entry_method': 'LIMIT',
                'entry_zone': 'CONFIRM_BODY',
                'sl_buffer_pips': 3,
                'tp1_method': 'MIDPOINT',
                'tp2_method': 'OPPOSITE_EXTREME',
                'reason': 'GPT failed - using defaults'
            }
    
    @gpt_error
    def evaluate_no_trade(self, session, state: str, failure_data: Dict) -> Dict:
        """GPT call at ARMED expiration/failure - provide NO_TRADE reasoning"""
        if not self.enabled:
            return {'reason': 'GPT disabled', 'severity': 'MEDIUM'}
        
        if not self._check_cooldown('no_trade_evaluation'):
            return {'reason': 'GPT cooldown', 'severity': 'MEDIUM'}
        
        # Extract essential data only
        asian_grade = session.asian_range_grade
        failure_reason = failure_data.get('reason', 'Unknown')
        time_in_state = failure_data.get('time_in_state', 0)
        
        # Create minimal prompt
        prompt = f"""
        XAU/USD NO-TRADE Evaluation:
        Asian Grade: {asian_grade}
        State: {state}
        Failure Reason: {failure_reason}
        Time in State: {time_in_state} minutes
        
        Rate severity: LOW, MEDIUM, or HIGH
        Respond with only one word: LOW, MEDIUM, or HIGH
        """
        
        # Make minimal GPT call
        response = self._call_gpt_minimal(prompt)
        
        # Log the GPT response for debugging
        logger.info(f"GPT NO-TRADE EVALUATION RESPONSE: {response}")
        
        if response and response.get('success'):
            gpt_response = response.get('gpt_response', '').upper()
            severity = gpt_response if gpt_response in ['LOW', 'MEDIUM', 'HIGH'] else 'MEDIUM'
            
            logger.info(f"GPT NO-TRADE Evaluation: {severity} - {session.symbol}")
            logger.info(f"GPT Raw Response: '{gpt_response}'")
            
            return {
                'reason': f'GPT evaluation: {severity} severity',
                'severity': severity,
                'gpt_used': True,
                'gpt_response': gpt_response,
                'tokens_used': response.get('tokens_used', 0)
            }
        else:
            # GPT failed - use medium severity
            logger.warning(f"GPT NO-TRADE Evaluation failed: {response}")
            return {'reason': 'GPT failed - default MEDIUM severity', 'severity': 'MEDIUM'}
    
    @gpt_error
    def evaluate_trade_management(self, session, trade_data: Dict) -> Dict:
        """GPT call at IN_TRADE state - evaluate trade management actions"""
        if not self.enabled:
            return {'action': 'HOLD', 'reason': 'GPT disabled'}
        
        if not self._check_cooldown('trade_management'):
            return {'action': 'HOLD', 'reason': 'GPT cooldown'}
        
        # Extract essential data only
        unrealized_pnl = trade_data.get('unrealized_pnl', 0)
        risk_reward = trade_data.get('risk_reward', 0)
        time_in_trade = trade_data.get('time_in_trade', 0)
        distance_to_be = trade_data.get('distance_to_be', 0)
        
        # Create minimal prompt
        prompt = f"""
        XAU/USD Trade Management:
        Unrealized PnL: {unrealized_pnl:.2f}R
        R:R Ratio: {risk_reward:.2f}
        Time in Trade: {time_in_trade} minutes
        Distance to BE: {distance_to_be:.2f}R
        
        Recommend action: HOLD, MOVE_BE, or TRAIL
        Respond with only one word: HOLD, MOVE_BE, or TRAIL
        """
        
        # Make minimal GPT call
        response = self._call_gpt_minimal(prompt)
        
        # Log the GPT response for debugging
        logger.info(f"GPT TRADE MANAGEMENT RESPONSE: {response}")
        
        if response and response.get('success'):
            gpt_response = response.get('gpt_response', '').upper()
            action = gpt_response if gpt_response in ['HOLD', 'MOVE_BE', 'TRAIL'] else 'HOLD'
            
            logger.info(f"GPT Trade Management: {action} - {session.symbol}")
            logger.info(f"GPT Raw Response: '{gpt_response}'")
            
            return {
                'action': action,
                'reason': 'GPT evaluation',
                'gpt_used': True,
                'gpt_response': gpt_response,
                'tokens_used': response.get('tokens_used', 0)
            }
        else:
            # GPT failed - hold position
            logger.warning(f"GPT Trade Management failed: {response}")
            return {'action': 'HOLD', 'reason': 'GPT failed - default HOLD'}
    
    def decide_trade_go_no_go(self, payload: Dict) -> Dict:
        """Single GPT decision gate before execution using client's strict prompt."""
        try:
            if not self.enabled or not self.client:
                return {'proceed': True, 'reason': 'GPT disabled'}

            system_role = (
                "SYSTEM ROLE — REAL-TIME INTRADAY ANALYST (XAUUSD)"
                "\nMission: Using the incoming MT5 data packet, decide if an Asian-session liquidity sweep in XAUUSD occurred and, if so, formulate a 1–3h reversal trade for the upcoming [LONDON OPEN / NEW YORK OPEN]. Obey the rules and format below exactly."
            )
            user_content = (
                "INPUT (single JSON object per call)\n" + json.dumps(payload, ensure_ascii=False)
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_completion_tokens=700,
                timeout=40,
            )

            content = response.choices[0].message.content.strip()
            tokens_used = getattr(response, 'usage', None).total_tokens if getattr(response, 'usage', None) else 0

            # Decision: if response contains NO-TRADE => block; otherwise proceed
            proceed = 'NO-TRADE' not in content.upper()
            return {
                'proceed': proceed,
                'response': content,
                'tokens_used': tokens_used,
                'model': self.model,
            }
        except Exception as e:
            logger.error(f"GPT decision gate error: {e}")
            # Fail-open to avoid blocking trading if GPT fails
            return {'proceed': True, 'reason': 'GPT error - default proceed'}

    def _check_cooldown(self, call_type: str) -> bool:
        """Check if enough time has passed since last GPT call - MINIMAL usage"""
        now = timezone.now()
        last_call = self.last_call_time.get(call_type)
        if last_call and (now - last_call).total_seconds() < self.cooldown_seconds:
            logger.info(f"GPT cooldown active for {call_type}")
            return False
        self.last_call_time[call_type] = now
        return True
    
    def _call_gpt_minimal(self, prompt: str, json_response: bool = False) -> Optional[Dict]:
        """PRODUCTION READY GPT call - Real OpenAI API integration"""
        try:
            if not self.enabled or not self.client:
                return {'success': True, 'execute': True, 'reason': 'GPT disabled'}
            
            # Log minimal GPT usage
            logger.info(f"GPT API call: {prompt[:100]}...")
            
            # Set up response format if JSON is expected
            response_format = {"type": "json_object"} if json_response else None
            
            # Make actual OpenAI API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert XAU/USD trader. Respond concisely with only the requested information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=50,  # Minimal tokens for response
                temperature=1,  # Default temperature
                timeout=30,  # 30 second timeout
                response_format=response_format
            )
            
            # Parse response
            gpt_response = response.choices[0].message.content.strip()
            
            # Try to parse as JSON if requested
            if json_response:
                try:
                    result = json.loads(gpt_response)
                    logger.info(f"GPT JSON Response: {result}")
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse GPT JSON response: {gpt_response}")
                    result = {}
            else:
                logger.info(f"GPT Response: {gpt_response}")
                result = {}
            
            logger.info(f"Tokens used: {response.usage.total_tokens}")
            
            return {
                'success': True,
                'execute': gpt_response.lower() == 'true' if not json_response else True,
                'gpt_response': gpt_response,
                'result': result if json_response else None,
                'tokens_used': response.usage.total_tokens,
                'model': self.model
            }
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            return {'success': False, 'execute': True, 'reason': 'Rate limit - default execute'}
        except openai.APITimeoutError as e:
            logger.error(f"OpenAI API timeout: {e}")
            return {'success': False, 'execute': True, 'reason': 'Timeout - default execute'}
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return {'success': False, 'execute': True, 'reason': 'API error - default execute'}
        except Exception as e:
            logger.error(f"Unexpected GPT call error: {e}")
            return {'success': False, 'execute': True, 'reason': 'Unexpected error - default execute'}