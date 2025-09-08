from django.db import models
from django.utils import timezone
from .trading_session import TradingSession


class LiquiditySweep(models.Model):
    """Enhanced model to track liquidity sweeps - Client Spec Compliant"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    sweep_direction = models.CharField(max_length=10)
    sweep_price = models.DecimalField(max_digits=10, decimal_places=5)
    sweep_threshold = models.DecimalField(max_digits=8, decimal_places=2)
    sweep_time = models.DateTimeField()
    confirmation_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    confirmation_time = models.DateTimeField(null=True, blank=True)
    displacement_atr = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    displacement_multiplier = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='DETECTED')
    created_at = models.DateTimeField(default=timezone.now)
    
    # Retest zone fields for audit
    retest_zone_bottom = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    retest_zone_top = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    
    # Client spec: Dynamic sweep threshold components for audit
    threshold_from_floor = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    threshold_from_pct = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    threshold_from_atr = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    chosen_threshold_component = models.CharField(max_length=20, null=True, blank=True)  # 'floor', 'percentage', 'atr'
    atr_h1_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Client spec: Breakout/whipsaw veto flags
    acceptance_outside = models.BooleanField(default=False)
    both_sides_swept_flag = models.BooleanField(default=False)
    
    # Client spec: Confirmation timeout tracking
    confirm_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'liquidity_sweep'
        ordering = ['-sweep_time']
        indexes = [
            models.Index(fields=['session', 'sweep_direction']),
            models.Index(fields=['sweep_time', 'status']),
            models.Index(fields=['symbol', 'created_at']),
        ]
    
    def __str__(self):
        return f"Sweep {self.sweep_direction} - {self.symbol} @ {self.sweep_price} ({self.status})"
    
    def is_confirmed(self):
        """Check if sweep has been confirmed"""
        return self.confirmation_time is not None
    
    def is_expired(self):
        """Check if confirmation deadline has passed"""
        if not self.confirm_deadline:
            return False
        return timezone.now() > self.confirm_deadline
    
    def get_threshold_breakdown(self):
        """Get breakdown of threshold calculation"""
        return {
            'floor_pips': float(self.threshold_from_floor or 0),
            'percentage_pips': float(self.threshold_from_pct or 0),
            'atr_pips': float(self.threshold_from_atr or 0),
            'chosen_component': self.chosen_threshold_component,
            'final_threshold': float(self.sweep_threshold)
        }


