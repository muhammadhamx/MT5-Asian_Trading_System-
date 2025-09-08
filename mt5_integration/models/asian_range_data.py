from django.db import models
from django.utils import timezone


class AsianRangeData(models.Model):
    """Model to store Asian session range data"""
    symbol = models.CharField(max_length=20)
    high = models.DecimalField(max_digits=10, decimal_places=5)
    low = models.DecimalField(max_digits=10, decimal_places=5)
    midpoint = models.DecimalField(max_digits=10, decimal_places=5)
    range_pips = models.DecimalField(max_digits=8, decimal_places=2)
    grade = models.CharField(max_length=20)
    risk_multiplier = models.DecimalField(max_digits=3, decimal_places=2)
    session_date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'asian_range_data'
        ordering = ['-session_date', '-created_at']


