from django.db import models
from django.utils import timezone


class EconomicNews(models.Model):
    """Model to track economic news events for confluence checking"""
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low Impact'),
        ('MEDIUM', 'Medium Impact'),
        ('HIGH', 'High Impact'),
        ('CRITICAL', 'Critical Impact'),
    ]
    
    TIER_CHOICES = [
        ('TIER1', 'Tier 1 (FOMC, CPI, NFP)'),
        ('OTHER', 'Other High Impact'),
    ]
    
    event_name = models.CharField(max_length=100)
    currency = models.CharField(max_length=10, default='USD')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, null=True, blank=True)
    release_time = models.DateTimeField()
    actual_value = models.CharField(max_length=50, null=True, blank=True)
    forecast_value = models.CharField(max_length=50, null=True, blank=True)
    previous_value = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'economic_news'
        ordering = ['-release_time']
        indexes = [
            models.Index(fields=['release_time', 'severity']),
            models.Index(fields=['currency', 'tier']),
        ]
    
    def __str__(self):
        return f"{self.event_name} ({self.severity}) - {self.release_time}"
    
    @classmethod
    def get_tier1_events(cls):
        """Get list of Tier 1 event names"""
        return ['FOMC', 'CPI', 'NFP', 'INTEREST_RATE_DECISION', 'EMPLOYMENT_CHANGE']
    
    def is_tier1(self):
        """Check if this is a Tier 1 event"""
        tier1_events = self.get_tier1_events()
        return any(event.upper() in self.event_name.upper() for event in tier1_events)
    
    def get_required_buffer_minutes(self):
        """Get required buffer minutes based on tier"""
        if self.is_tier1():
            return 60  # Tier 1 events need ≥60 minutes
        elif self.severity in ['HIGH', 'CRITICAL']:
            return 30  # Other high impact events need ≥30 minutes
        else:
            return 15  # Low/medium impact events