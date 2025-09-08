from django.db import models
from django.utils import timezone
from .trading_session import TradingSession
from .liquidity_sweep import LiquiditySweep


class TradeSignal(models.Model):
    """Enhanced model to store trade signals with Phase 3 client spec compliance"""
    
    ENTRY_METHOD_CHOICES = [
        ('MARKET', 'Market Order'),
        ('LIMIT', 'Limit Order'),
        ('CONFIRM_ON_TRIGGER', 'Confirm on Trigger'),
    ]
    
    ENTRY_ZONE_CHOICES = [
        ('CONFIRM_BODY', 'Confirmation Candle Body'),
        ('OB_FVG', 'Order Block / Fair Value Gap'),
        ('ASIAN_MIDPOINT', 'Asian Midpoint'),
    ]
    
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE, null=True, blank=True)
    sweep = models.ForeignKey(LiquiditySweep, on_delete=models.CASCADE, null=True, blank=True)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    signal_type = models.CharField(max_length=10, choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    entry_price = models.DecimalField(max_digits=10, decimal_places=5)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=5)
    take_profit_1 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    take_profit_2 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    volume = models.DecimalField(max_digits=10, decimal_places=2)
    risk_percentage = models.DecimalField(max_digits=4, decimal_places=2, default=0.5)
    risk_reward_ratio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=20, choices=TradingSession.STATE_CHOICES, default='IDLE')
    gpt_opinion = models.TextField(null=True, blank=True)
    gpt_tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Phase 3 Client Spec Fields
    entry_method = models.CharField(max_length=20, choices=ENTRY_METHOD_CHOICES, default='LIMIT')
    entry_zone_reference = models.CharField(max_length=20, choices=ENTRY_ZONE_CHOICES, default='CONFIRM_BODY')
    sl_pips = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tp1_pips = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tp2_pips = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    calculated_r = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)  # Realized R value
    micro_trigger_satisfied = models.BooleanField(default=False)
    retest_expiry_time = models.DateTimeField(null=True, blank=True)
    
    # Trade Management Fields
    breakeven_moved = models.BooleanField(default=False)
    trailing_active = models.BooleanField(default=False)
    exit_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    exit_reason = models.CharField(max_length=50, null=True, blank=True)  # 'SL', 'TP1', 'TP2', 'MANUAL', 'TIMEOUT'

    class Meta:
        db_table = 'trade_signal'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'state']),
            models.Index(fields=['symbol', 'created_at']),
            models.Index(fields=['state', 'retest_expiry_time']),
        ]
    
    def __str__(self):
        return f"{self.signal_type} {self.symbol} @ {self.entry_price} ({self.state})"
    
    def is_expired(self):
        """Check if retest window has expired"""
        if not self.retest_expiry_time:
            return False
        return timezone.now() > self.retest_expiry_time
    
    def calculate_actual_r(self):
        """Calculate actual R based on exit price"""
        if not self.exit_price or not self.entry_price or not self.stop_loss:
            return 0.0
        
        # Calculate risk distance (entry to SL)
        risk_distance = abs(float(self.entry_price) - float(self.stop_loss))
        if risk_distance == 0:
            return 0.0
        
        # Calculate actual P&L distance
        pnl_distance = float(self.exit_price) - float(self.entry_price)
        
        # Adjust for trade direction
        if self.signal_type == 'SELL':
            pnl_distance = -pnl_distance
        
        # Calculate R
        r_value = pnl_distance / risk_distance
        return round(r_value, 2)
    
    def update_calculated_r(self):
        """Update the calculated_r field"""
        self.calculated_r = self.calculate_actual_r()
        self.save()
    
    def get_pip_distances(self):
        """Get SL/TP distances in pips"""
        return {
            'sl_pips': float(self.sl_pips or 0),
            'tp1_pips': float(self.tp1_pips or 0),
            'tp2_pips': float(self.tp2_pips or 0)
        }


