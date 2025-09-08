from django.db import models
from django.utils import timezone


class MarketData(models.Model):
    """Model to store market data for analysis"""
    symbol = models.CharField(max_length=20)
    timeframe = models.CharField(max_length=10)
    timestamp = models.DateTimeField()
    open_price = models.DecimalField(max_digits=10, decimal_places=5)
    high_price = models.DecimalField(max_digits=10, decimal_places=5)
    low_price = models.DecimalField(max_digits=10, decimal_places=5)
    close_price = models.DecimalField(max_digits=10, decimal_places=5)
    volume = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    atr_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    adx_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    spread = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'market_data'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['symbol', 'timeframe', 'timestamp']),
        ]


