from django.db import models
from django.utils import timezone
from .trading_session import TradingSession


class ConfluenceCheck(models.Model):
    """Enhanced model to track confluence checks - Client Spec Compliant"""
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=10)
    bias = models.CharField(max_length=20)
    trend_strength = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    atr_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    adx_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    adx_timeframe = models.CharField(max_length=10, default='15m')  # Client spec: ADX(15m)
    spread = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    spread_threshold = models.DecimalField(max_digits=8, decimal_places=2, default=2.0)  # Client spec: Y=2.0 pips
    velocity_spike = models.BooleanField(default=False)
    velocity_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # Client spec: ratio for audit
    news_risk = models.BooleanField(default=False)
    news_tier = models.CharField(max_length=10, null=True, blank=True)  # Client spec: TIER1/OTHER
    news_buffer_minutes = models.IntegerField(default=0)
    
    # Client spec: LBMA auction blackout
    auction_blackout = models.BooleanField(default=False)
    
    # Client spec: Trend day detection
    trend_day_high_adx = models.BooleanField(default=False)
    h1_band_walk = models.BooleanField(default=False)
    
    # Client spec: NY participation rule
    london_traversed_asia = models.BooleanField(default=False)
    ny_requires_fresh_sweep = models.BooleanField(default=False)
    
    # Client spec: Participation filter
    participation_filter_active = models.BooleanField(default=False)
    
    # Client spec: Explainable NO_TRADE
    failure_reasons = models.TextField(null=True, blank=True)
    
    passed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'confluence_check'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'passed']),
            models.Index(fields=['created_at', 'timeframe']),
        ]
    
    def __str__(self):
        return f"Confluence Check - Session {self.session.id} ({'PASSED' if self.passed else 'FAILED'})"
    
    def get_failure_reasons_list(self):
        """Get failure reasons as a list"""
        if not self.failure_reasons:
            return []
        return [reason.strip() for reason in self.failure_reasons.split(';') if reason.strip()]
    
    def add_failure_reason(self, reason: str):
        """Add a failure reason"""
        if not self.failure_reasons:
            self.failure_reasons = reason
        else:
            self.failure_reasons += f"; {reason}"


